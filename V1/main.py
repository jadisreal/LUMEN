import sys
import asyncio
import os
import time
import threading
import traceback

from dotenv import load_dotenv
load_dotenv()

from core.logger import get_logger
log = get_logger("main")

# ── Global crash handlers so nothing dies silently ────────────
import logging as _logging

def _flush_all_logs():
    """Force-flush every handler so crash info reaches disk."""
    for h in _logging.root.handlers:
        try:
            h.flush()
        except Exception:
            pass
    for name in list(_logging.Logger.manager.loggerDict):
        lgr = _logging.getLogger(name)
        for h in lgr.handlers:
            try:
                h.flush()
            except Exception:
                pass

def _global_excepthook(exc_type, exc_value, exc_tb):
    if exc_type is KeyboardInterrupt:
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    log.critical("Unhandled exception (main thread):",
                 exc_info=(exc_type, exc_value, exc_tb))
    _flush_all_logs()

def _thread_excepthook(args):
    log.critical(f"Unhandled exception in thread '{args.thread.name}':",
                 exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    _flush_all_logs()

sys.excepthook = _global_excepthook
threading.excepthook = _thread_excepthook

from core.conversation_log import (
    log_user_input, log_llm_raw, log_spoken,
    log_action, log_event
)
from core.sanitizer import sanitize_for_tts

from speech_to_text import record_voice, stop_listening_flag
from llm import get_llm_output
from tts import speak, stop_speaking
from ui import LumenUI

from actions.open_app import open_app
from actions.web_search import web_search
from actions.weather_report import weather_action
from actions.send_message import send_message
from actions.open_folder import open_folder
from actions.date_logic import date_query

from memory.memory_manager import load_memory, update_memory
from memory.temporary_memory import TemporaryMemory

from skills import registry

# ── Skill registry ────────────────────────────────────────────────
registry.register("open_app",       open_app,       "Open Application")
registry.register("search",         web_search,     "Web Search")
registry.register("weather_report", weather_action,  "Weather Report")
registry.register("open_folder",    open_folder,    "Open Folder")
registry.register("date_query",     date_query,     "Date Query")

interrupt_commands = ["mute", "quit", "exit", "stop"]
sleep_commands = ["lumen go to sleep", "go to sleep", "lumen sleep"]

WAKE_PHRASE = os.getenv("WAKE_PHRASE", "lumen wake up").lower().strip()
SLEEP_TIMEOUT = int(os.getenv("SLEEP_TIMEOUT_SECONDS", "120"))

temp_memory = TemporaryMemory()


class WakeState:
    def __init__(self):
        self.awake = False
        self.last_interaction = 0.0

    def wake_up(self):
        self.awake = True
        self.last_interaction = time.time()

    def touch(self):
        self.last_interaction = time.time()

    def check_sleep(self):
        if self.awake and (time.time() - self.last_interaction > SLEEP_TIMEOUT):
            self.awake = False
            return True
        return False

    def is_awake(self):
        return self.awake


wake_state = WakeState()


def _safe_thread(name: str, target, **kwargs):
    """Launch a daemon thread that catches and logs any exception."""
    def _wrapper():
        try:
            target(**kwargs)
        except Exception as e:
            log.error(f"Action thread '{name}' crashed: {e}", exc_info=True)

    threading.Thread(target=_wrapper, name=name, daemon=True).start()


async def get_voice_input():
    return await asyncio.to_thread(record_voice)


async def ai_loop(ui: LumenUI):
    ui.write_log("System: Say '" + WAKE_PHRASE + "' to wake me up.")
    log.info(f"AI loop started. Wake phrase: '{WAKE_PHRASE}', timeout: {SLEEP_TIMEOUT}s")
    log_event(f"LUMEN started. Wake phrase: '{WAKE_PHRASE}'")

    while True:
        try:
            stop_listening_flag.clear()
            user_text = await get_voice_input()

            if not user_text:
                continue

            # Check if we fell asleep
            if wake_state.check_sleep():
                ui.write_log("System: I've gone to sleep. Say '" + WAKE_PHRASE + "' to wake me.")
                speak("I've gone to sleep due to inactivity. Say " + WAKE_PHRASE + " when you need me.", ui)
                log.info("Sleep timeout reached.")
                log_event("Sleep timeout — went to sleep.")

            # If asleep, listen only for wake phrase
            if not wake_state.is_awake():
                if WAKE_PHRASE in user_text.lower().strip():
                    wake_state.wake_up()
                    ui.write_log("System: I'm awake, Chart.")
                    speak("I'm awake. How can I help you, Chart?", ui)
                    log.info("Woke up via wake phrase.")
                    log_event("Woke up via wake phrase.")
                continue

            # We're awake - check for sleep timeout on each interaction
            wake_state.touch()

            # ── Explicit sleep command ────────────────────────
            if any(cmd in user_text.lower().strip() for cmd in sleep_commands):
                stop_speaking()
                temp_memory.reset()
                wake_state.awake = False
                ui.write_log("System: Going to sleep. Say '" + WAKE_PHRASE + "' to wake me.")
                speak("Going to sleep, Chart. Wake me when you need me.", ui)
                log.info("Explicit sleep command.")
                log_event(f"Explicit sleep: '{user_text}'")
                continue

            # Handle interrupt commands
            if any(cmd in user_text.lower() for cmd in interrupt_commands):
                stop_speaking()
                temp_memory.reset()
                log.debug(f"Interrupt command: '{user_text}'")
                log_event(f"Interrupt: '{user_text}'")
                continue

            ui.write_log(f"You: {user_text}")
            log.info(f"User: {user_text}")
            log_user_input(user_text)

            if temp_memory.get_current_question():
                param = temp_memory.get_current_question()
                temp_memory.update_parameters({param: user_text})
                temp_memory.clear_current_question()
                user_text = temp_memory.get_last_user_text()

            temp_memory.set_last_user_text(user_text)

            long_term_memory = load_memory()

            def minimal_memory_for_prompt(memory: dict) -> dict:
                result = {}
                identity = memory.get("identity", {})
                preferences = memory.get("preferences", {})
                relationships = memory.get("relationships", {})
                emotional_state = memory.get("emotional_state", {})

                if "name" in identity:
                    result["user_name"] = identity["name"].get("value")

                for k in ["favorite_color", "favorite_food", "favorite_music"]:
                    if k in preferences:
                        val = preferences[k].get("value")
                        if isinstance(val, dict) and "value" in val:
                            val = val["value"]
                        result[k] = val

                for rel, info in relationships.items():
                    if isinstance(info, dict) and "name" in info and "value" in info["name"]:
                        result[f"{rel}_name"] = info["name"]["value"]

                for event, info in emotional_state.items():
                    if isinstance(info, dict) and "value" in info:
                        result[f"emotion_{event}"] = info["value"]

                return {k: v for k, v in result.items() if v}

            memory_for_prompt = minimal_memory_for_prompt(long_term_memory)

            history_lines = temp_memory.get_history_for_prompt()
            recent_history = "\n".join(history_lines.split("\n")[-5:])
            if recent_history:
                memory_for_prompt["recent_conversation"] = recent_history

            if temp_memory.has_pending_intent():
                memory_for_prompt["_pending_intent"] = temp_memory.pending_intent
                memory_for_prompt["_collected_params"] = str(temp_memory.get_parameters())

            try:
                llm_output = get_llm_output(
                    user_text=user_text,
                    memory_block=memory_for_prompt
                )
            except Exception as e:
                log.error(f"LLM call failed: {e}", exc_info=True)
                ui.write_log(f"System: LLM error — {e}")
                continue

            # Reset sleep timer after successful LLM response
            wake_state.touch()

            intent = llm_output.get("intent", "chat")
            parameters = llm_output.get("parameters", {})
            response = llm_output.get("text")
            memory_update = llm_output.get("memory_update")

            log.info(f"LLM → intent={intent}, params={parameters}")
            log.debug(f"LLM response: {response}")
            log_llm_raw(intent, parameters, response or "", memory_update)

            # ── LLM offline check ──────────────────────────────────────
            if llm_output.get("offline"):
                msg = response or "LLM is offline."
                ui.write_log(f"System: {msg}")
                speak(msg, ui)
                log.warning("LLM is offline.")
                log_event("LLM offline detected.")
                continue

            if memory_update and isinstance(memory_update, dict):
                try:
                    update_memory(memory_update)
                    log.debug(f"Memory updated: {memory_update}")
                except Exception as e:
                    log.error(f"Memory update failed: {e}", exc_info=True)

            temp_memory.set_last_ai_response(response)

            # ── Dispatch via skill registry ───────────────────
            if intent == "send_message":
                # Multi-step: may need clarification for missing params
                temp_memory.set_pending_intent("send_message")
                temp_memory.update_parameters(parameters)

                all_params_ready = all(
                    temp_memory.get_parameter(p)
                    for p in ["receiver", "message_text", "platform"]
                )
                if all_params_ready:
                    log_action("send_message", str(temp_memory.get_parameters()))
                    _safe_thread("send_message", send_message,
                        parameters=temp_memory.get_parameters(),
                        response=response,
                        player=ui,
                        session_memory=temp_memory
                    )
                else:
                    # Mark which param we're waiting for
                    for p in ["receiver", "message_text", "platform"]:
                        if not temp_memory.get_parameter(p):
                            temp_memory.set_current_question(p)
                            break
                    if response:
                        clean = sanitize_for_tts(response)
                        ui.write_log(f"Lumen: {clean or response}")
                        log_spoken(clean or response)
                        speak(response, ui)

            elif registry.has(intent):
                skill = registry.get(intent)
                log_action(intent, str(parameters))
                _safe_thread(skill.name, skill.handler,
                    parameters=parameters,
                    response=response,
                    player=ui,
                    session_memory=temp_memory
                )

            else:
                if response:
                    clean = sanitize_for_tts(response)
                    ui.write_log(f"Lumen: {clean or response}")
                    log_spoken(clean or response)
                    speak(response, ui)

            await asyncio.sleep(0.01)

        except Exception as e:
            log.critical(f"AI loop iteration error: {e}", exc_info=True)
            _flush_all_logs()
            await asyncio.sleep(1)  # Prevent tight crash loop


def main():
    log.info("=" * 50)
    log.info("LUMEN starting up")
    log.info("=" * 50)

    try:
        ui = LumenUI("face.png", size=(900, 900))
    except Exception as e:
        log.critical(f"UI failed to start: {e}", exc_info=True)
        print(f"\n[FATAL] UI failed to start: {e}")
        return

    def runner():
        try:
            asyncio.run(ai_loop(ui))
        except Exception as e:
            log.critical(f"AI loop crashed fatally: {e}", exc_info=True)
            _flush_all_logs()

    threading.Thread(target=runner, name="ai-loop", daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()

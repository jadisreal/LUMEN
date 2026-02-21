import time
import pyautogui
import pyperclip
from tts import speak
from core.logger import get_logger

log = get_logger("action.message")


def _clipboard_type(text: str):
    """Copy *text* to clipboard, paste with Ctrl+V, then clear clipboard."""
    pyperclip.copy(text)
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.1)

REQUIRED_PARAMS = ["receiver", "message_text", "platform"]

def send_message(parameters=None, response=None, player=None, session_memory=None, **kwargs) -> bool:
    """
    Send a message via Windows app (WhatsApp, Telegram, etc.)

    Multi-step support: asks for missing parameters using temporary memory.

    Expected parameters:
        - receiver (str)
        - message_text (str)
        - platform (str, default: "WhatsApp")
    """

    if session_memory is None:
        msg = "Session memory missing, cannot proceed."
        if player:
            player.write_log(msg)
        speak(msg, player)
        return False

    if parameters:
        session_memory.update_parameters(parameters)

    for param in REQUIRED_PARAMS:
        value = session_memory.get_parameter(param)
        if not value:
        
            session_memory.set_current_question(param)
            question_text = ""
            if param == "receiver":
                question_text = "Sir, who should I send the message to?"
            elif param == "message_text":
                question_text = "Sir, what should I say?"
            elif param == "platform":
                question_text = "Sir, which platform should I use? (WhatsApp, Telegram, etc.)"
            else:
                question_text = f"Sir, please provide {param}."

            if player:
                player.write_log("AI :", question_text)
            speak(question_text, player)
            return False  

    receiver = session_memory.get_parameter("receiver").strip()
    platform = session_memory.get_parameter("platform").strip() or "WhatsApp"
    message_text = session_memory.get_parameter("message_text").strip()

    if response:
        if player:
            player.write_log(response)
        speak(response, player)

    try:
        pyautogui.PAUSE = 0.1

        # Open the platform via Windows Search
        pyautogui.press("win")
        time.sleep(0.3)
        _clipboard_type(platform)
        time.sleep(0.2)
        pyautogui.press("enter")

        # Platform-specific contact search
        if platform.lower() == "discord":
            time.sleep(1.5)  # Discord takes longer to load/focus
            pyautogui.hotkey("ctrl", "k")  # Quick Switcher
            time.sleep(0.4)
            _clipboard_type(receiver)
            time.sleep(0.6)
            pyautogui.press("enter")
            time.sleep(0.5)
        elif platform.lower() == "telegram":
            time.sleep(1.0)
            pyautogui.hotkey("ctrl", "f")  # Search
            time.sleep(0.3)
            _clipboard_type(receiver)
            time.sleep(0.4)
            pyautogui.press("enter")
            time.sleep(0.3)
        else:
            # WhatsApp / generic flow
            time.sleep(0.6)
            pyautogui.hotkey("ctrl", "f")
            time.sleep(0.2)
            _clipboard_type(receiver)
            time.sleep(0.2)
            pyautogui.press("enter")
            time.sleep(0.2)

        _clipboard_type(message_text)
        time.sleep(0.1)
        pyautogui.press("enter")

        session_memory.clear_current_question()
        session_memory.clear_pending_intent()
        session_memory.update_parameters({})  

        # -----------------------------
        # Log success
        # -----------------------------
        success_msg = f"Sir, message sent to {receiver} via {platform}."
        if player:
            player.write_log(success_msg)
        speak(success_msg, player)

        return True

    except Exception as e:
        log.error(f"Message send failed: {e}", exc_info=True)
        msg = f"Sir, I failed to send the message. ({e})"
        if player:
            player.write_log(msg)
        speak(msg, player)
        return False

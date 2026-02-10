# llm.py - LM Studio Local API (OpenAI-compatible)

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# LM Studio runs an OpenAI-compatible server at localhost:1234
LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1/chat/completions")

# Leave empty to use whatever model is loaded in LM Studio
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "")

PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core", "prompt.txt")


def load_system_prompt() -> str:
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Warning: prompt.txt not found: {e}")
        return "You are Lumen, a helpful AI assistant."


SYSTEM_PROMPT = load_system_prompt()


def safe_json_parse(text: str) -> dict | None:
    if not text:
        return None

    text = text.strip()

    # Strip markdown code fences if present
    if "```json" in text:
        try:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        except ValueError:
            pass
    elif "```" in text:
        try:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()
        except ValueError:
            pass

    # If text starts with a quote (missing opening brace), wrap it
    if text.startswith('"') and '{' not in text[:5]:
        text = '{' + text

    # If text doesn't end with } (truncated), try to close it
    if '{' in text and '}' not in text:
        text = text + '}'

    # Find outermost { ... } block
    try:
        start = text.index("{")
        # Find matching closing brace by counting depth
        depth = 0
        end = start
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if end <= start:
            # No matching close found, take everything from { and close it
            json_str = text[start:] + '}'
        else:
            json_str = text[start:end]

        return json.loads(json_str)
    except Exception as e:
        print(f"Warning: JSON parse error: {e}")
        print(f"Text: {text[:300]}")
        return None


def get_llm_output(user_text: str, memory_block: dict = None) -> dict:

    if not user_text or not user_text.strip():
        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": "I didn't catch that, Chart.",
            "memory_update": None
        }

    # Build memory string
    memory_str = ""
    if memory_block:
        memory_str = "\n".join(f"{k}: {v}" for k, v in memory_block.items())

    user_prompt = f"""User message: "{user_text}"

Known user memory:
{memory_str if memory_str else "No memory available"}"""

    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 500,
        "stream": False
    }

    # Only include model field if explicitly set
    if LMSTUDIO_MODEL:
        payload["model"] = LMSTUDIO_MODEL

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            LMSTUDIO_URL,
            headers=headers,
            json=payload,
            timeout=90
        )

        if response.status_code != 200:
            print(f"LM Studio API Error: {response.text}")
            return {
                "intent": "chat",
                "parameters": {},
                "text": f"LM Studio returned error {response.status_code}.",
                "needs_clarification": False,
                "memory_update": None
            }

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        parsed = safe_json_parse(content)
        if parsed:
            return {
                "intent": parsed.get("intent", "chat"),
                "parameters": parsed.get("parameters", {}),
                "needs_clarification": parsed.get("needs_clarification", False),
                "text": parsed.get("text"),
                "memory_update": parsed.get("memory_update")
            }

        return {
            "intent": "chat",
            "parameters": {},
            "needs_clarification": False,
            "text": content,
            "memory_update": None
        }

    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to LM Studio. Is it running at localhost:1234?")
        return {
            "intent": "chat",
            "text": "I can't reach LM Studio. Please make sure it's running.",
            "parameters": {},
            "needs_clarification": False,
            "memory_update": None
        }

    except requests.exceptions.Timeout:
        print("LM Studio timeout!")
        return {
            "intent": "chat",
            "text": "The model took too long to respond, Chart.",
            "parameters": {},
            "needs_clarification": False,
            "memory_update": None
        }

    except Exception as e:
        print(f"LLM ERROR: {e}")
        return {
            "intent": "chat",
            "text": "I encountered a system error.",
            "parameters": {},
            "needs_clarification": False,
            "memory_update": None
        }

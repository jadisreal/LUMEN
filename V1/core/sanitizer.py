# core/sanitizer.py - Clean LLM output before TTS speaks it
#
# Strips JSON fragments, code blocks, OAI role markers, markdown,
# and other artifacts so the user only hears natural speech.

import re
from core.logger import get_logger

log = get_logger("sanitizer")


def sanitize_for_tts(text: str) -> str:
    """
    Clean raw LLM output into natural speech text.
    Returns empty string if nothing speakable remains.
    """
    if not text:
        return ""

    original = text

    # ── Strip full JSON objects ────────────────────────────────
    # If the entire text is a JSON blob, extract "text" field
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            import json
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and "text" in parsed:
                text = parsed["text"] or ""
        except (json.JSONDecodeError, ValueError):
            pass

    # ── Strip markdown code fences ────────────────────────────
    # ```json ... ``` or ``` ... ```
    text = re.sub(r"```[\s\S]*?```", "", text)

    # ── Strip inline code `...` ───────────────────────────────
    text = re.sub(r"`[^`]+`", "", text)

    # ── Strip OAI role markers ────────────────────────────────
    # "Assistant:", "System:", "User:", "AI:" at line start
    text = re.sub(r"^(assistant|system|user|ai|lumen)\s*:\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)

    # ── Strip JSON key-value fragments ────────────────────────
    # "intent": "chat", "parameters": {}, etc.
    text = re.sub(r'"[\w_]+":\s*"[^"]*"', "", text)
    text = re.sub(r'"[\w_]+":\s*\{[^}]*\}', "", text)
    text = re.sub(r'"[\w_]+":\s*(true|false|null|\d+)', "", text)

    # ── Strip stray braces and brackets ───────────────────────
    text = re.sub(r"[{}\[\]]", "", text)

    # ── Strip markdown formatting ─────────────────────────────
    # Bold **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    # Italic *text* or _text_
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Headers # ## ###
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Bullet points - or *
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)

    # ── Strip URLs ────────────────────────────────────────────
    text = re.sub(r"https?://\S+", "", text)

    # ── Strip escaped quotes and leftover punctuation noise ───
    text = text.replace('\\"', '"')
    text = re.sub(r'"{2,}', '', text)  # multiple quotes

    # ── Collapse whitespace ───────────────────────────────────
    text = re.sub(r"\s+", " ", text).strip()

    # ── Strip leading/trailing commas, colons, semicolons ─────
    text = text.strip(",:;")

    if text != original:
        log.debug(f"Sanitized: '{original[:80]}' → '{text[:80]}'")

    return text

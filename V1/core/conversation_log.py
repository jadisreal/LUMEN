# core/conversation_log.py - Structured conversation log for debugging
#
# Logs every input/output exchange to V1/logs/conversation.log
# Format: timestamped, easy to grep and review.

import os
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

CONV_LOG_FILE = os.path.join(LOG_DIR, "conversation.log")

# ── Dedicated conversation logger ─────────────────────────────
_conv_logger = logging.getLogger("conversation")
_conv_logger.setLevel(logging.DEBUG)
_conv_logger.propagate = False  # Don't pollute main log

_fmt = logging.Formatter(
    fmt="%(asctime)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

_file_handler = RotatingFileHandler(
    CONV_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(_fmt)
_conv_logger.addHandler(_file_handler)


def log_user_input(text: str):
    """Log what the user said."""
    _conv_logger.info(f"USER     │ {text}")


def log_llm_raw(intent: str, parameters: dict, raw_text: str, memory_update=None):
    """Log the raw LLM output (intent, params, full text)."""
    _conv_logger.info(f"LLM RAW  │ intent={intent} params={parameters}")
    _conv_logger.info(f"LLM TEXT │ {raw_text}")
    if memory_update:
        _conv_logger.info(f"LLM MEM  │ {memory_update}")


def log_spoken(text: str):
    """Log what was actually spoken by TTS after sanitization."""
    _conv_logger.info(f"SPOKEN   │ {text}")


def log_action(action_name: str, details: str):
    """Log an action dispatch."""
    _conv_logger.info(f"ACTION   │ [{action_name}] {details}")


def log_event(event: str):
    """Log a system event (wake, sleep, interrupt, etc.)."""
    _conv_logger.info(f"EVENT    │ {event}")

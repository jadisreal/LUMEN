# core/logger.py - Centralized logging for LUMEN
#
# Every module imports:  from core.logger import log
# Writes to console AND V1/logs/lumen.log (auto-rotated at 2MB)

import os
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "lumen.log")

# ── Formatter ──────────────────────────────────────────────────
_fmt = logging.Formatter(
    fmt="%(asctime)s │ %(levelname)-7s │ %(name)-14s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ── File handler (rotated, 2MB × 3 backups) ───────────────────
_file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_fmt)
_file_handler.setLevel(logging.DEBUG)

# ── Console handler ───────────────────────────────────────────
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)
_console_handler.setLevel(logging.INFO)

# ── Root config ───────────────────────────────────────────────
logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])

# Silence noisy third-party loggers
for _name in ("urllib3", "httpx", "httpcore", "faster_whisper", "ctranslate2", "huggingface_hub"):
    logging.getLogger(_name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Usage: log = get_logger(__name__)"""
    return logging.getLogger(name)

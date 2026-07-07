import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Ensure stdout and stderr support UTF-8 encoding on Windows
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

LOG_DIR = "logs"
LOG_FILE = "agent.log"

os.makedirs(LOG_DIR, exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger shared across the system.
    - Console output: human-friendly logs (INFO+)
    - File output: detailed logs with rotation (DEBUG+)
    - Prevents duplicate handlers for repeated imports
    """

    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "[%(levelname)s] %(name)s -> %(message)s"
    )
    console_handler.setFormatter(console_format)

    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, LOG_FILE),
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# 🔥 Add simple `log()` helper so imports don't break
_default_logger = get_logger("UnifiedAgent")

def log(message: str, level: str = "info"):
    """Simple global log function compatible with earlier imports."""
    level = level.lower()

    if level == "debug":
        _default_logger.debug(message)
    elif level == "warning":
        _default_logger.warning(message)
    elif level == "error":
        _default_logger.error(message)
    else:
        _default_logger.info(message)

import logging
from .log_config import LOG_FLAGS

def log(category: str, message: str, *args, **kwargs) -> None:
    """Log a message if the category is enabled."""
    if LOG_FLAGS.get(category, True):
        logging.info(f"[{category}] {message}", *args, **kwargs)

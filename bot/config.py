import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env if it exists
load_dotenv()

# Centralized configuration for tokens and database
API_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "DATABASE_URL")
ADMIN_COMMAND = os.getenv("ADMIN_COMMAND", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ADMIN_PASSWORD")
YOOKASSA_TOKEN = os.getenv("YOOKASSA_TOKEN", "YOOKASSA_TOKEN")
# Optional second bot for alerts
ALERT_BOT_TOKEN = os.getenv("ALERT_BOT_TOKEN")
# Comma-separated list of chat IDs for alerts
ALERT_CHAT_IDS = [int(x) for x in os.getenv("ALERT_CHAT_IDS", "").split(",") if x]
# Interval in seconds for checking subscription status.
# Defaults to 10 minutes if the environment variable is missing.
SUBSCRIPTION_CHECK_INTERVAL = int(os.getenv("SUBSCRIPTION_CHECK_INTERVAL", "1800"))

def _resolve_path(path: str) -> str:
    """Return an absolute path for directories configured via environment."""

    resolved = Path(path).expanduser()
    if resolved.is_absolute():
        return str(resolved)

    project_root = Path(__file__).resolve().parent.parent
    return str(project_root / resolved)


LOG_DIR = _resolve_path(os.getenv("LOG_DIR", "logs"))

import os
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
ALERT_CHAT_ID = int(os.getenv("ALERT_CHAT_ID", "0"))
# Interval in seconds for checking subscription status.
# Defaults to 10 minutes if the environment variable is missing.
SUBSCRIPTION_CHECK_INTERVAL = int(os.getenv("SUBSCRIPTION_CHECK_INTERVAL", "1800"))
LOG_DIR = os.getenv("LOG_DIR", "logs")

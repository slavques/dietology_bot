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
# Interval in seconds for checking subscription status.
# Defaults to 10 minutes if the environment variable is missing.
SUBSCRIPTION_CHECK_INTERVAL = int(os.getenv("SUBSCRIPTION_CHECK_INTERVAL", "600"))
LOG_DIR = os.getenv("LOG_DIR", "logs")

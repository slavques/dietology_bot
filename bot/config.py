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
SUBSCRIPTION_CHECK_INTERVAL = os.getenv("SUBSCRIPTION_CHECK_INTERVAL", "SUBSCRIPTION_CHECK_INTERVAL")
LOG_DIR = os.getenv("LOG_DIR", "logs")

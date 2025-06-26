import os
from dotenv import load_dotenv

# Load environment variables from .env if it exists
load_dotenv()

# Centralized configuration for tokens and database
API_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "DATABASE_URL")
ADMIN_COMMAND = os.getenv("ADMIN_COMMAND", "ADMIN_COMMAND")
YOOKASSA_TOKEN = os.getenv("YOOKASSA_TOKEN", "YOOKASSA_TOKEN")
SUBSCRIPTION_CHECK_INTERVAL = int(os.getenv("SUBSCRIPTION_CHECK_INTERVAL", "1800"))

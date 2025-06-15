import os

# Centralized configuration for tokens and database

API_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")

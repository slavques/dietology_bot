# Dietology Bot

Telegram bot for tracking meals and calculating macros. Built with `aiogram` and SQLite using SQLAlchemy.

## Setup

1. Install dependencies (Python 3.10+ recommended):
   ```bash
   pip install -r requirements.txt
   ```
2. Set environment variables `BOT_TOKEN` (Telegram token) and optionally `OPENAI_API_KEY` for OpenAI integration. These values are read in `bot/config.py`.

3. Run the bot:
   ```bash
   python -m bot.main
   ```

The database is stored in `bot.db` in the project root by default. You can change this by setting `DATABASE_URL`.
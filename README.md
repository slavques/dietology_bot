# Dietology Bot

Telegram bot for tracking meals and calculating macros. Built with `aiogram` and SQLite using SQLAlchemy.

## Setup

1. Install dependencies (Python 3.10+ recommended):
   ```bash
   pip install -r requirements.txt
   ```
2. Set the environment variable `BOT_TOKEN` with your Telegram bot token.
3. (Optional) Set `OPENAI_API_KEY` to enable food detection and macro calculation.

4. Run the bot:
   ```bash
   python -m bot.main
   ```

The database is stored in `bot.db` in the project root by default. You can change this by setting `DATABASE_URL`.

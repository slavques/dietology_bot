# Dietology Bot

Telegram bot for tracking meals and calculating macros. Built with `aiogram` and SQLite using SQLAlchemy.

## Setup

1. Install dependencies (Python 3.10+ recommended):
   ```bash
   pip install -r requirements.txt
   ```
2. Set environment variables `BOT_TOKEN` (Telegram token) and optionally `OPENAI_API_KEY` for OpenAI integration. These values are read in `bot/config.py`. To change the admin login command, set `ADMIN_COMMAND` (default `admin1467`).


3. Run the bot (package version):
   ```bash
   python -m bot.main
   ```
   Or run the standalone file:
   ```bash
   python bot.py
   ```

The database is stored in `bot.db` in the project root by default. You can change this by setting `DATABASE_URL`.

When the OpenAI API rejects requests with **429 Too Many Requests**, the bot will retry a few times with exponential backoff. If the limit persists, it replies that the recognition service is unavailable. Similar handling applies to **400 Bad Request** errors, which typically mean your OpenAI account lacks quota. In that case, update your billing and try again later.

# Dietology Bot

d0q9pz-codex/разработать-telegram-бота-для-учета-еды-и-кбжу
Simple aiogram bot for tracking meals and calculating macros.

## Setup
1. Install dependencies:
   ```bash
   pip install aiogram SQLAlchemy
   ```
2. Set your Telegram bot token in the environment variable `BOT_TOKEN`.
3. Run the bot:
   ```bash
   python main.py
   ```
Telegram bot for tracking meals and calculating macros. Built with `aiogram` and SQLite using SQLAlchemy.

## Setup

1. Install dependencies (Python 3.10+ recommended):
   ```bash
   pip install aiogram sqlalchemy
   ```
2. Set the environment variable `BOT_TOKEN` with your Telegram bot token.

3. Run the bot:
   ```bash
   python -m bot.main
   ```

The database is stored in `bot.db` in the project root by default. You can change this by setting `DATABASE_URL`.
main

# Dietology Bot

Telegram bot for tracking meals and calculating macros. Built with `aiogram` and SQLite using SQLAlchemy.

## Setup

1. Install dependencies (Python 3.10+ recommended):
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file with `BOT_TOKEN` (Telegram token) and optionally
   `OPENAI_API_KEY` for OpenAI integration. These values are loaded in
   `bot/config.py`. You can also set `ADMIN_COMMAND` (default `admin1467`),
   `DATABASE_URL`, and `YOOKASSA_TOKEN` for payments here. For testing, the
   `SUBSCRIPTION_CHECK_INTERVAL` (in seconds) controls how often subscription
   statuses are checked (default `3600`).

3. Run the bot (package version):
   ```bash
   python -m bot.main
   ```
   Or run the standalone file:
   ```bash
   python bot.py
   ```

The database is stored in `bot.db` in the project root by default. You can change
this by setting `DATABASE_URL`.

### Manual database access

The default SQLite database can be inspected and edited directly. Install the
`sqlite3` command line tool or any graphical client such as **DB Browser for
SQLite**, then open `bot.db`:

```bash
sqlite3 bot.db
```

Within the shell you can list tables with `.tables`, show table schemas with
`.schema users` or `.schema meals` and execute regular SQL statements. For
example, granting a user paid status:

```sql
UPDATE users SET grade='paid' WHERE telegram_id = 12345;
```

Exit the shell with `.quit` once your changes are complete. If you configured a
different `DATABASE_URL`, open that file instead.

### Subscription testing

Two helper commands imitate payment results:

```
/success1467  # activate or extend paid plan
/refused1467  # simulate payment refusal
/notify1467  # force sending pending subscription reminders
```

Paid users receive 800 GPT requests per month. Free users get 20 requests that renew every month from the account start date. Daily checks send reminders 7 and 3 days before expiry and on the last day.

When the OpenAI API rejects requests with **429 Too Many Requests**, the bot will retry a few times with exponential backoff. If the limit persists, it replies that the recognition service is unavailable. Similar handling applies to **400 Bad Request** errors, which typically mean your OpenAI account lacks quota. In that case, update your billing and try again later.

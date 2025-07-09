# Dietology Bot

Telegram bot for tracking meals and calculating macros. Built with `aiogram` and SQLAlchemy. Uses SQLite by default but also works with PostgreSQL.
The bot relies on OpenAI's `gpt-4o` model for food recognition.

## Setup

1. Install dependencies (Python 3.10+ recommended):
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file with `BOT_TOKEN` (Telegram token) and optionally
   `OPENAI_API_KEY` for OpenAI integration. These values are loaded in
   `bot/config.py`. You can also set `ADMIN_COMMAND` (default `admin1467`),
   `DATABASE_URL` (defaults to `sqlite:///bot.db`), and `YOOKASSA_TOKEN` for payments here. For testing, the
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

The database is stored in `bot.db` in the project root by default (connection
string `sqlite:///bot.db`). You can change this by setting `DATABASE_URL`.
To use PostgreSQL instead of SQLite, install `psycopg2-binary` and set

`DATABASE_URL` to a PostgreSQL connection string, e.g.
`postgresql+psycopg2://user:password@host:5432/dbname`.
The bot automatically adds any missing columns on startup,
so upgrades work without manual migrations on both SQLite and PostgreSQL.


### Logging

Log files are written to `logs/bot.log` by default (configurable via `LOG_DIR`).
Each entry starts with the timestamp `YYYY-MM-DD HH:MM:SS`. The handler rotates
daily and keeps the three most recent log files. Token usage for each OpenAI
request is logged under the `tokens` category, showing input, output and total
token counts.

### Prompt sandbox

To quickly test how the recognition prompts behave, run the helper script:

```bash
python scripts/prompt_sandbox.py path/to/photo.jpg
python scripts/prompt_sandbox.py "описание блюда" --text
```

Add `--hint "ваше уточнение"` to simulate clarification requests. The script
prints the JSON response from the OpenAI API.

### Custom prompts

All GPT prompts are stored in `bot/prompts.py`. There are separate constants
for PRO and free tiers, currently containing the same text. Edit these strings
manually to tweak recognition behavior.

The hint prompts use placeholders:

- `{context}` — previous JSON response if available.
- `{hint}` — the latest user clarification.

These placeholders are filled automatically when the bot calls the OpenAI API.

### Manual database access

The default SQLite database can be inspected and edited directly. Install the
`sqlite3` command line tool or any graphical client such as **DB Browser for
SQLite**, then open `bot.db`:

```bash
sqlite3 bot.db
```

Within the shell you can list tables with `.tables`, show table schemas with
`.schema users`, `.schema meals` or `.schema payments` and execute regular SQL
statements. For example, granting a user paid status:

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

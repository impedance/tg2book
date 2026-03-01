# Analysis & Logging Expansion Plan

## 1. Brief Analysis of the Problem
The bot successfully initializes in Docker (logs show "Bot client запущен", "Pyrogram userbot запущен", and background tasks start) but fails to react to any Telegram messages or commands. 

**Possible causes:**
1. **Silenced Networking / Database Errors**: Pyrogram and `aiosqlite` loggers are clamped to `WARNING`. If there are permission issues with the mounted `data/` volume (e.g., SQLite WAL files being locked or unwritable by the `botuser`), Pyrogram might silently drop updates because it cannot save the new `pts`/`qts` states to its local session database.
2. **Missing Bot Identity Checks**: The code never fetches and logs `bot_client.get_me()`. If the bot session file picked up an old/incorrect token, it might be connected, but to the *wrong bot*. 
3. **Pyrogram Dispatcher Issues**: The bot utilizes `asyncio.Event().wait()` instead of Pyrogram's native `idle()`. While technically valid, if there are unexpected signals in Docker, Pyrogram's dispatcher might silently pause or fail to dispatch updates.
4. **Handler Registration Order**: For the `userbot`, handlers are dynamically attached via decorators *after* `userbot_client.start()` is called. While Pyrogram supports this, it can lead to race conditions where the dispatcher misses the first few updates or doesn't bind correctly. However, since the `bot_client` also fails (and its handlers are added *before* start), this is likely a secondary issue.

## 2. Plan to Expand Logging
To pinpoint the root cause without guessing, we need to temporarily increase visibility into Pyrogram's internal MTProto machinery and the database layer.

### [MODIFY] `bot.py`

#### A. Unsilence Core Libraries
Change the logger levels for `pyrogram` and `aiosqlite` from `WARNING` to `INFO` (and selectively `DEBUG` if needed) to expose networking and database I/O issues.

#### B. Catch Raw MTProto Updates
Add a `RawUpdateHandler` to `bot_client`. This will log *every* incoming MTProto payload before Pyrogram's filters process it. If we see raw updates but no handler triggers, the issue is in the filters/dispatcher. If we see *no* raw updates, the issue is at the network/session level.

#### C. Log Bot Identity
Add a call to `await bot_client.get_me()` right after `bot_client.start()` and log the bot's username and ID to ensure we are connected to the correct bot token.

## 3. Verification & Logical Validation of the Plan
- **Are there logical errors?** 
  - *Risk*: `RawUpdateHandler` might flood the logs. 
  - *Mitigation*: We will log only the `type(update)` and not the raw JSON, or we will only add it to `bot_client` (which has low traffic) rather than `userbot_client` (which might see every channel update).
- **Does it match the codebase?** 
  - Yes. The silencing happens at lines 48-51 in `bot.py`. The `bot_client` starts at line 678, making it an easy place to inject the identity check.
- **Verification strategy**: Apply the logging edits, rebuild the Docker container (`make prod-build` or `make build`), run it, and send a `/start` message. The new logs will instantly reveal whether updates are arriving at the network layer and whether database locks are happening. 

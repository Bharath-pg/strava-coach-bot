# Strava Coach Bot

An agentic Telegram running coach powered by Strava, LLM tool-calling, and MCP. The bot autonomously decides which tools to invoke, chains multiple calls, and composes natural responses -- no hardcoded intent routing.

## Features

- **Agentic LLM** -- Groq (llama-3.3-70b) with native tool-calling; the model decides what to do, not if/else routing
- **Strava Integration** -- live activity data, pace/distance comparisons, weekly check-ins
- **Training Plan** -- 7-week sub-60 10K plan with daily session lookup
- **Reminders** -- set one-time or recurring reminders that the bot delivers on schedule
- **MCP Server** -- expose all 7 tools via Model Context Protocol for external LLM integrations (Cursor, Claude Desktop)

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ (or use Docker)
- A [Telegram Bot Token](https://core.telegram.org/bots#botfather)
- A [Groq API Key](https://console.groq.com/keys) (free tier)
- [Strava API credentials](https://www.strava.com/settings/api)

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your tokens

docker compose up --build
```

### Local Development

```bash
git clone <your-repo-url>
cd strava-coach-bot

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Edit .env with your tokens

alembic upgrade head
python -m src.main
```

## Usage

Just talk to the bot naturally:

- "What should I run today?"
- "How was my run yesterday?"
- "How is my training going this week?"
- "Show me my runs from last week"
- "Remind me to stretch at 7am daily"

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Usage guide |
| `/remind` | Set a reminder |
| `/reminders` | List active reminders |
| `/cancel <id>` | Cancel a reminder |

## MCP Server

Exposes 7 tools via stdio transport for external LLM clients:

```bash
python -m src.mcp.server
```

**Strava tools**: `get_strava_activities`, `get_run_details`, `get_training_plan`, `get_training_status`
**Reminder tools**: `set_reminder`, `list_reminders`, `cancel_reminder`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from BotFather |
| `GROQ_API_KEY` | Yes | Groq API key |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `STRAVA_CLIENT_ID` | Yes | Strava API app client ID |
| `STRAVA_CLIENT_SECRET` | Yes | Strava API app client secret |
| `STRAVA_REFRESH_TOKEN` | Yes | Strava OAuth refresh token (with `activity:read_all` scope) |
| `ALLOWED_USER_IDS` | No | Comma-separated Telegram user IDs to restrict access |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

## Project Structure

```
src/
├── main.py              # Bot entrypoint
├── config.py            # Settings from environment
├── bot/handlers/        # Telegram command handlers
├── bot/conversation.py  # NL catch-all → agent loop
├── llm/tools.py         # 7 tool schemas + executor
├── llm/groq_llm.py      # Agent loop with tool-calling
├── services/strava.py   # Strava API client
├── services/training_plan.py  # 10K training plan
├── services/weekly_checkin.py # Plan vs actual comparison
├── services/reminder.py # Reminder CRUD
├── mcp/server.py        # MCP server (stdio)
└── db/                  # Database session management
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a full technical deep dive covering the agentic design, tool-calling flow, Strava integration, and every design decision.

## License

MIT

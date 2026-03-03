# Personal Assistant Telegram Bot

A Telegram bot for expense tracking and reminders, powered by Google Gemini for natural language understanding. Includes an MCP server for tool integration.

## Features

- **Expense Tracking** -- add, query, and summarize expenses via natural language or commands
- **Reminders** -- set one-time or recurring reminders that the bot delivers on schedule
- **Natural Language** -- speak naturally; Gemini parses your intent ("I spent $30 on lunch" just works)
- **MCP Server** -- expose all tools via Model Context Protocol for external LLM integrations

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ (or use Docker)
- A [Telegram Bot Token](https://core.telegram.org/bots#botfather)
- A [Google Gemini API Key](https://aistudio.google.com/apikey) (free tier)

### Local Development

```bash
# Clone and enter
git clone <your-repo-url>
cd personal-assistant-bot

# Create virtualenv and install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your tokens

# Run database migrations
alembic upgrade head

# Start the bot
python -m src.main
```

### Docker

```bash
cp .env.example .env
# Edit .env with your tokens

docker compose up --build
```

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and quick guide |
| `/help` | List all commands |
| `/expense <description>` | Add an expense (e.g. `/expense $50 dinner`) |
| `/summary [period]` | Spending summary (today/week/month/all) |
| `/remind <message> at <time>` | Set a reminder |
| `/reminders` | List active reminders |
| `/cancel <id>` | Cancel a reminder |

### Natural Language

Just type naturally -- the bot understands:

- "I spent 45 dollars on groceries yesterday"
- "Remind me to call the dentist tomorrow at 3pm"
- "How much did I spend on food this week?"
- "Show my expenses for March"

## MCP Server

The bot exposes an MCP server for external tool integration:

```bash
python -m src.mcp.server
```

Available tools: `add_expense`, `query_expenses`, `expense_summary`, `set_reminder`, `list_reminders`, `cancel_reminder`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from BotFather |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `ALLOWED_USER_IDS` | No | Comma-separated Telegram user IDs to restrict access |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

## Project Structure

```
src/
├── main.py              # Bot entrypoint
├── config.py            # Settings from environment
├── bot/handlers/        # Telegram command & message handlers
├── llm/                 # LLM integration (Gemini)
├── models/              # SQLAlchemy ORM models
├── services/            # Business logic
├── mcp/                 # MCP server
└── db/                  # Database session management
```

## License

MIT

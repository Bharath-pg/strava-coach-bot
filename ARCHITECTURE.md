# Architecture & Technical Deep Dive

A comprehensive breakdown of every component, design decision, and technology used in this project.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Project Structure](#project-structure)
4. [Tech Stack](#tech-stack)
5. [Component Deep Dive](#component-deep-dive)
   - [Configuration Layer](#1-configuration-layer)
   - [Database Layer](#2-database-layer)
   - [ORM Models](#3-orm-models)
   - [Service Layer](#4-service-layer)
   - [Agentic LLM Layer](#5-agentic-llm-layer)
   - [Telegram Bot Handlers](#6-telegram-bot-handlers)
   - [Reminder Scheduler](#7-reminder-scheduler)
   - [MCP Server](#8-mcp-server)
6. [Infrastructure](#infrastructure)
   - [Docker](#docker)
   - [CI/CD](#cicd)
   - [Database Migrations](#database-migrations)
7. [Data Flow Examples](#data-flow-examples)
8. [Testing Strategy](#testing-strategy)
9. [Design Decisions & Trade-offs](#design-decisions--trade-offs)

---

## System Overview

This is a Telegram running coach bot with two domains: Strava/running and reminders. What makes it more than a simple bot:

- **Agentic tool-calling** -- the LLM autonomously decides which tools to invoke, observes results, chains multiple calls, and composes a natural response. No hardcoded intent routing.
- **DB-backed training plans** -- users create full training plans via natural language. The LLM generates a periodized plan and stores it in PostgreSQL. Individual sessions can be added, edited, or deleted.
- **Pluggable LLM backend** -- abstract interface with Groq and Gemini implementations; swap providers by changing one env var
- **MCP server** -- exposes 11 tools (reminders, Strava, training plans) via Model Context Protocol, allowing external AI systems (Cursor, Claude Desktop) to query your data
- **Strava integration** -- fetches running activities, compares against a training plan, generates weekly check-in reports
- **Production-ready infrastructure** -- async Python, PostgreSQL, Docker, database migrations, CI/CD

---

## Architecture Diagram

```
┌─────────────────┐     ┌──────────────────────────────────────────┐
│  Telegram User   │────▶│            Telegram Bot                  │
│  (mobile/desktop)│◀────│         (python-tg-bot)                  │
└─────────────────┘     └───────────────┬──────────────────────────┘
                                        │
                                        ▼
                        ┌──────────────────────────────┐
                        │       Agent Loop (LLM)        │
                        │   Groq llama-3.3-70b-versatile│
                        │                              │
                        │  User msg → tool_calls[] →   │
                        │  execute → observe → repeat  │
                        │  → final text response       │
                        └───────────┬──────────────────┘
                                    │ tool calls
                   ┌────────────────┼────────────────┐
                   ▼                ▼                ▼
            ┌──────────┐    ┌──────────┐    ┌──────────┐
            │ Training  │    │ Reminder │    │  Strava  │
            │ Plan Svc  │    │ Service  │    │ Service  │
            └─────┬─────┘    └────┬─────┘    └────┬─────┘
                  │               │               │
                  ▼               ▼               ▼
           ┌────────────────┐           ┌────────────────┐
           │   PostgreSQL    │           │   Strava API   │
           │  (plans +       │           │  (OAuth2 +     │
           │   reminders)    │           │   REST)        │
           └────────────────┘           └────────────────┘

┌──────────────────┐     ┌──────────────────┐
│   MCP Client      │────▶│   MCP Server     │──── Same services
│ (Cursor/Claude)   │◀────│  (stdio transport)│
└──────────────────┘     └──────────────────┘
```

---

## Project Structure

```
strava-coach-bot/
├── src/
│   ├── main.py                    # Bot entrypoint: wires handlers, starts scheduler
│   ├── __main__.py                # Allows `python -m src.main`
│   ├── config.py                  # Pydantic settings loaded from .env
│   │
│   ├── db/
│   │   └── session.py             # Async SQLAlchemy engine + session factory
│   │
│   ├── models/
│   │   ├── reminder.py            # Reminder ORM model
│   │   └── training_plan.py       # TrainingPlan + TrainingSession ORM models
│   │
│   ├── services/
│   │   ├── reminder.py            # CRUD + due detection + recurrence logic
│   │   ├── strava.py              # Strava API client (OAuth2 token refresh)
│   │   ├── training_plan.py       # DB-backed training plan CRUD
│   │   └── weekly_checkin.py      # Compares Strava data against training plan
│   │
│   ├── llm/
│   │   ├── base.py                # Abstract BaseLLM interface
│   │   ├── prompts.py             # Agent system prompt
│   │   ├── tools.py               # 11 tool schemas + execute_tool() dispatcher
│   │   ├── groq_llm.py            # Groq implementation with tool-calling agent loop
│   │   ├── gemini.py              # Google Gemini implementation
│   │   └── parser.py              # Provider selection + run_agent()
│   │
│   ├── bot/
│   │   ├── handlers/
│   │   │   ├── start.py           # /start, /help
│   │   │   └── reminder.py        # /remind, /reminders, /cancel
│   │   └── conversation.py        # NL catch-all → agent loop
│   │
│   └── mcp/
│       └── server.py              # MCP server with 11 tools (stdio transport)
│
├── alembic/
│   ├── env.py                     # Async migration runner
│   └── versions/
│       ├── 001_initial_schema.py  # Creates reminders table
│       └── 002_training_plans.py  # Creates training_plans + training_sessions + seed data
│
├── tests/
│   ├── conftest.py                # In-memory SQLite fixtures for testing
│   ├── test_reminder.py           # Reminder service tests
│   └── test_llm.py                # LLM parser tests (mocked)
│
├── Dockerfile                     # Multi-stage: bot + mcp-server targets
├── docker-compose.yml             # PostgreSQL + bot services
├── .github/workflows/ci.yml       # Lint + test + Docker build
├── pyproject.toml                 # Project config, deps, tool settings
├── requirements.txt               # Flat dependency list for Docker
├── alembic.ini                    # Alembic configuration
├── .env.example                   # Template for environment variables
└── .gitignore
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Language | Python 3.12 | Async-first, rich ecosystem for bots and ML |
| Bot Framework | python-telegram-bot v21+ | Async, well-maintained, handles updates/polling |
| LLM (primary) | Groq (llama-3.3-70b) | Free tier, fast inference (<500ms), native tool calling |
| LLM (alternate) | Google Gemini | Pluggable fallback, free tier |
| Database | PostgreSQL 16 | Production-grade, async via asyncpg |
| ORM | SQLAlchemy 2.0 (async) | Type-safe models, async session management |
| Migrations | Alembic | Version-controlled schema changes |
| Scheduler | APScheduler v3 | In-process async cron for reminder polling |
| MCP | mcp[cli] SDK | Standard protocol for LLM tool integration |
| Strava | REST API v3 | OAuth2 token refresh, activity fetch |
| Containerization | Docker + Compose | Reproducible multi-service deployment |
| CI/CD | GitHub Actions | Automated lint, test, build on push |
| Linter | Ruff | Fast Python linter + formatter |
| Testing | Pytest + pytest-asyncio | Async test support, in-memory SQLite |

---

## Component Deep Dive

### 1. Configuration Layer

**File**: `src/config.py`

Uses `pydantic-settings` to load configuration from environment variables and `.env` files with type validation.

```python
class Settings(BaseSettings):
    telegram_bot_token: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""
    llm_provider: str = "groq"       # Switch LLM by changing this
    database_url: str = "postgresql+asyncpg://..."
    allowed_user_ids: str = ""        # Comma-separated, empty = allow all
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_refresh_token: str = ""
```

Key design choices:
- **Defaults for non-critical fields** so the app doesn't crash during testing (tokens default to empty string)
- **`@lru_cache`** on `get_settings()` for singleton behavior
- **`allowed_users` property** parses the comma-separated string into a `set[int]` for O(1) auth checks
- **`async_database_url` property** normalizes Railway's `postgres://` URLs to `postgresql+asyncpg://` for SQLAlchemy

### 2. Database Layer

**File**: `src/db/session.py`

```python
engine = create_async_engine(settings.async_database_url)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
```

- **Fully async** via `asyncpg` driver -- non-blocking DB calls don't stall the Telegram event loop
- **`expire_on_commit=False`** lets us access ORM attributes after commit without extra queries
- **`DeclarativeBase`** is the SQLAlchemy 2.0 pattern (replaces the old `declarative_base()`)

### 3. ORM Models

**TrainingPlan** (`src/models/training_plan.py`):
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| user_id | BigInteger | Telegram user ID, indexed |
| name | String(200) | Plan name (e.g. "Sub-60 10K Plan") |
| goal | String(500) | Goal description |
| start_date | Date | Plan start date |
| end_date | Date | Plan end / race date |
| is_active | Boolean | Only one active plan per user |
| created_at | DateTime(tz) | Server-side `now()` |

**TrainingSession** (`src/models/training_plan.py`):
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| plan_id | Integer FK | References training_plans.id, CASCADE delete |
| date | Date | Session date |
| session_type | String(50) | easy/rest/tempo/intervals/strides/long/race |
| distance_km | Float | Target distance |
| pace_target | String(50) | Target pace (e.g. "6:00/km") |
| description | String(500) | Human-readable description |

**Reminder** (`src/models/reminder.py`):
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| user_id | BigInteger | Telegram user ID, indexed |
| message | String(1000) | Reminder text |
| remind_at | DateTime(tz) | When to fire |
| recurrence | String(20) | none/daily/weekly/monthly |
| is_active | Boolean | Soft-delete pattern |
| created_at | DateTime(tz) | Server-side `now()` |

Design notes:
- **`BigInteger` for user_id** because Telegram IDs can exceed 32-bit range
- **Soft-delete on reminders** (`is_active`) instead of hard delete, so recurring reminders can be deactivated without losing history
- **One-to-many relationship** between TrainingPlan and TrainingSession with CASCADE delete
- **`is_active` on plans** ensures only one active plan per user; creating a new plan deactivates the old one

### 4. Service Layer

The service layer sits between handlers and the database. This separation means:
- Bot handlers and MCP tools share the same business logic
- Services are independently testable (no Telegram dependency)
- Database queries are encapsulated in one place

**Training Plan Service** (`src/services/training_plan.py`):
- `create_plan()` -- create a full plan with all sessions; deactivates any existing active plan
- `get_active_plan()` -- fetch the user's active plan with eager-loaded sessions
- `get_session()` -- planned workout for a specific date
- `get_week_sessions()` -- all sessions for a given week
- `add_session_to_plan()` -- add a single session to the active plan
- `update_session()` -- partial update (date, type, distance, pace, description)
- `delete_session()` -- remove a session with ownership validation
- `get_week_number()` -- 1-based training week number relative to plan start

**Reminder Service** (`src/services/reminder.py`):
- `set_reminder()` -- create with recurrence validation
- `list_reminders()` -- active reminders sorted by time
- `cancel_reminder()` -- soft-delete with ownership check
- `get_due_reminders()` -- finds all active reminders where `remind_at <= now`
- `advance_or_deactivate()` -- after firing, either schedules next occurrence (recurring) or deactivates (one-time)

**Strava Service** (`src/services/strava.py`):
- OAuth2 token refresh with caching (avoids unnecessary token refreshes)
- `get_activities()` -- fetch activities with date range and type filter
- `get_week_activities()` -- convenience wrapper for current week
- `get_day_activities()` -- convenience wrapper for a single day
- Returns `ActivitySummary` dataclass with computed properties (pace, formatted time)

**Weekly Check-in** (`src/services/weekly_checkin.py`):
- Compares actual Strava activities against the user's active training plan from the DB
- Produces a formatted report with completion percentages, pace comparisons, and next week preview
- Scheduled as a cron job (Sunday 7PM IST) and available on-demand via tool call

### 5. Agentic LLM Layer

This is the most architecturally interesting component. Instead of the LLM acting as a classifier (outputting intent JSON that Python code routes), it acts as an **autonomous agent** that decides which tools to call.

**How it works (ReAct-style agent loop)**:

```
User: "Create a 5K plan for sub-25 starting next Monday"
  │
  ▼
Agent Loop (max 8 iterations):
  │
  ├─ Iteration 1: LLM sees user message + 11 tool schemas
  │   LLM decides: call create_training_plan(name="Sub-25 5K Plan", goal="...", sessions=[...42 sessions...])
  │   Result: "Training plan 'Sub-25 5K Plan' created with 42 sessions (30 runs, 199 km)"
  │
  └─ Iteration 2: LLM sees result, no more tool calls needed
      Returns: "Your new training plan is ready! 42 sessions across 6 weeks..."
```

**Tool schemas** (`src/llm/tools.py`):
- 11 tools defined in OpenAI function-calling format
- `user_id` is deliberately excluded from schemas -- injected server-side to prevent the LLM from accessing other users' data
- `execute_tool(name, args, user_id)` dispatches to service-layer functions
- Training plan creation: the LLM generates the full `sessions` array (dates, types, distances, paces, descriptions) in a single tool call

**Agent loop** (`src/llm/groq_llm.py`):
```python
async def run_agent(self, user_message: str, user_id: int) -> str:
    messages = [system_prompt, user_message]
    for _ in range(MAX_ITERATIONS):
        response = await groq.chat.completions.create(
            tools=TOOL_SCHEMAS, tool_choice="auto"
        )
        if no tool_calls:
            return response.content  # final answer
        for tool_call in tool_calls:
            result = await execute_tool(tool_call.name, tool_call.args, user_id)
            messages.append(tool_result)
```

**Key design decisions**:
- **`tool_choice="auto"`** lets the LLM decide when to call tools vs respond directly (casual chat gets no tool calls)
- **Max 8 iterations** prevents runaway loops
- **Plan generation in one shot** -- the LLM outputs the entire `sessions` array in a single `create_training_plan` call rather than making 40+ individual `add_training_session` calls
- **Groq's native tool-calling** via `tools` parameter -- no prompt hacking or JSON-mode workarounds

### 6. Telegram Bot Handlers

**Command handlers** handle explicit `/commands`:
- `/start`, `/help` -- welcome text with usage examples
- `/remind` -- usage instructions
- `/reminders` -- list active reminders
- `/cancel 3` -- deactivate reminder by ID

**Conversation handler** (`src/bot/conversation.py`) catches all non-command text and routes it through the agent loop. The agent handles everything -- training plan creation/editing, reminders, Strava queries, and casual chat.

### 7. Reminder Scheduler

**Problem**: Reminders need to fire at specific times, but the bot is event-driven (responds to messages).

**Solution**: APScheduler runs an async interval job every 30 seconds inside the bot's event loop:
1. Query all active reminders where `remind_at <= now`
2. Send a Telegram message to each user
3. For recurring reminders: advance `remind_at` by the recurrence delta
4. For one-time reminders: set `is_active = False`

The scheduler is started in `post_init` (after the event loop is running), not in `main()` (before the loop exists).

A weekly cron job (Sunday 7PM IST) sends an automated Strava training check-in to all configured users.

### 8. MCP Server

**File**: `src/mcp/server.py`

Exposes 11 tools via Model Context Protocol using stdio transport:

**Training plan tools**: `create_training_plan`, `add_training_session`, `update_training_session`, `delete_training_session`, `get_training_plan`, `get_training_status`
**Strava tools**: `get_strava_activities`, `get_run_details`
**Reminder tools**: `set_reminder`, `list_reminders`, `cancel_reminder`

Each tool is a thin wrapper around the service layer -- the same business logic the Telegram bot uses.

**Why MCP?** It makes the bot's capabilities available to any MCP-compatible client. For example, from Cursor you could ask "What should I run today?" and it would call `get_training_plan` directly. Or "Create a half marathon plan" would call `create_training_plan`.

**Transport**: stdio (not HTTP). The MCP client spawns the server as a subprocess and communicates via stdin/stdout. This is why it's not a persistent Docker service -- it's invoked on-demand.

---

## Infrastructure

### Docker

**Multi-stage Dockerfile**:
```dockerfile
FROM python:3.12-slim AS base
# Install deps, copy code

FROM base AS bot          # CMD: python -m src.main
FROM base AS mcp-server   # CMD: python -m src.mcp.server
```

Two build targets from the same image -- shared base layer, different entrypoints.

**docker-compose.yml** runs 2 services:
- `postgres` -- PostgreSQL 16 with health checks and persistent volume
- `bot` -- waits for healthy postgres, runs migrations, starts bot

The MCP server is behind a `profiles: [mcp]` flag so it only starts when explicitly requested.

### CI/CD

**GitHub Actions** (`.github/workflows/ci.yml`):

On every push/PR to `main`:
1. **Lint job**: `ruff check` + `ruff format --check`
2. **Test job**: spins up a PostgreSQL service container, installs deps, runs migrations, runs pytest
3. **Docker build job** (only on main, after lint+test pass): builds the image with BuildKit caching

### Database Migrations

**Alembic** with async support:
- `alembic/env.py` uses `async_engine_from_config` and `asyncio.run()` to run migrations async
- Migration files in `alembic/versions/` are version-controlled
- `001_initial_schema.py` creates the reminders table
- `002_training_plans.py` creates training_plans + training_sessions tables and seeds the initial hardcoded plan

---

## Data Flow Examples

### "Create a 5K plan for sub-25 starting next Monday" (Plan Generation)

```
User message
    │
    ▼
conversation_handler()
    │ run_agent("Create a 5K plan for sub-25 starting next Monday", user_id=123456789)
    ▼
GroqLLM.run_agent()  ─── Agent Loop ───
    │
    ├─ Iter 1: LLM generates full plan and calls create_training_plan(
    │     name="Sub-25 5K Plan", goal="Run 5K in under 25 minutes",
    │     start_date="2026-03-17", end_date="2026-04-27",
    │     sessions=[{date: "2026-03-17", session_type: "easy", ...}, ...42 sessions]
    │   )
    │   Service: deactivates old plan → creates TrainingPlan → bulk inserts TrainingSessions
    │   Tool result: "Training plan 'Sub-25 5K Plan' created with 42 sessions (30 runs, 199 km)"
    │
    └─ Iter 2: LLM produces final text (no tool calls)
        "Your new training plan is ready! 42 sessions across 6 weeks..."
    │
    ▼
msg.reply_text("Your new training plan is ready! ...")
```

### "How was my run today?" (Multi-tool chain)

```
User message
    │
    ▼
Agent Loop:
    ├─ Iter 1: LLM calls get_run_details(date="2026-03-10")
    │   Tool result: "Morning Run: 3.95 km in 25m 7s | 6:21/km"
    │
    ├─ Iter 2: LLM calls get_training_plan(date="2026-03-10")
    │   Tool result: "Tue Mar 10 (Week 1): Easy 4 km run, Pace: 7:00+/km"
    │
    └─ Iter 3: Final text response
        "Nice run! You covered 3.95 km at 6:21/km -- faster than the 7:00+/km target."
```

### Reminder firing

```
Every 30 seconds:
    │
    ▼
check_reminders()
    │ SELECT * FROM reminders WHERE is_active AND remind_at <= now()
    ▼
Found reminder: "Call dentist" at 15:00
    │ bot.send_message(user_id, "Reminder: Call dentist")
    ▼
advance_or_deactivate()
    │ recurrence == "none" → is_active = False
    │ recurrence == "daily" → remind_at += 1 day
```

---

## Testing Strategy

Tests use **in-memory SQLite** via `aiosqlite` -- no PostgreSQL needed to run tests.

`conftest.py` creates a fresh database for each test:
1. Create async engine with `sqlite+aiosqlite:///:memory:`
2. Run `Base.metadata.create_all` to create tables
3. Yield a session
4. Drop all tables + dispose engine

**Test coverage**:
- **Reminder service**: create, cancel, ownership checks, due detection, recurrence advancement, one-time deactivation
- **LLM parser**: mocked LLM to test intent routing without API calls

---

## Design Decisions & Trade-offs

| Decision | Alternative | Why this way |
|----------|------------|-------------|
| Agentic tool-calling | Intent classification + routing | LLM autonomously chains tools, handles edge cases, and composes natural responses. No need to hardcode every interaction flow. |
| user_id injected server-side | Include user_id in tool schemas | Prevents the LLM from fabricating or guessing user IDs. Security by design. |
| DB-backed training plans | Hardcoded in Python | Users can create, edit, and delete plans via the bot. Multiple plans, plan history. |
| Full plan in one tool call | Session-by-session tool calls | One `create_training_plan` call with 40+ sessions is vastly more efficient than 40+ individual `add_training_session` calls. |
| Max 8 agent iterations | 5 or unlimited | 8 allows for plan generation + summary. Prevents runaway loops and excessive API calls. |
| Polling (not webhooks) | Webhooks | Simpler for development; no public URL/SSL needed. Can switch later. |
| APScheduler in-process | Celery + Redis | One fewer service to run. Fine for single-instance bot. |
| Soft-delete reminders | Hard delete | Preserves history; recurring reminders need state. |
| SQLite for tests | Testcontainers (Postgres) | Fast (0.1s), no Docker dependency in CI, good enough for service-level tests. |
| stdio MCP transport | HTTP/SSE | Standard for local MCP clients (Cursor, Claude Desktop). No server to keep running. |
| Groq over Gemini | Gemini only | Gemini free tier had quota issues; Groq is reliable with generous limits + native tool calling. |

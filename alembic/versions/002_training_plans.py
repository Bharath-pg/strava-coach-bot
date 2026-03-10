"""Training plans and sessions tables + seed hardcoded plan

Revision ID: 002
Revises: 001
Create Date: 2026-03-03
"""
from __future__ import annotations

import os
from datetime import date
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _seed_user_id() -> int | None:
    raw = os.environ.get("ALLOWED_USER_IDS", "")
    ids = [uid.strip() for uid in raw.split(",") if uid.strip()]
    return int(ids[0]) if ids else None


def _hardcoded_sessions() -> list[dict]:
    """The original 7-week sub-60 10K plan (Mar 10 - Apr 27, 2026)."""
    sessions = []

    def add(d: date, stype: str, km: float, pace: str, desc: str) -> None:
        sessions.append({"date": d, "session_type": stype, "distance_km": km, "pace_target": pace, "description": desc})

    # Week 1
    add(date(2026, 3, 10), "easy", 3.95, "7:00+/km", "Morning run (done)")
    add(date(2026, 3, 11), "rest", 0, "", "Rest day")
    add(date(2026, 3, 12), "easy", 4, "7:00+/km", "4 km easy run")
    add(date(2026, 3, 13), "rest", 0, "", "Rest day")
    add(date(2026, 3, 14), "easy", 5, "7:00+/km", "5 km easy run")
    add(date(2026, 3, 15), "long", 6, "7:00+/km", "6 km long run")
    # Week 2
    add(date(2026, 3, 16), "easy", 4, "7:00+/km", "4 km easy run")
    add(date(2026, 3, 17), "rest", 0, "", "Rest day")
    add(date(2026, 3, 18), "strides", 4, "7:00+/km", "4 km easy + 4x100m strides")
    add(date(2026, 3, 19), "rest", 0, "", "Rest day")
    add(date(2026, 3, 20), "easy", 4, "7:00+/km", "4 km easy run")
    add(date(2026, 3, 21), "rest", 0, "", "Rest day")
    add(date(2026, 3, 22), "long", 7, "7:00+/km", "7 km long run")
    # Week 3
    add(date(2026, 3, 23), "easy", 4, "7:00+/km", "4 km easy run")
    add(date(2026, 3, 24), "rest", 0, "", "Rest day")
    add(date(2026, 3, 25), "intervals", 4.5, "5:30/km", "1.5 km WU + 5x400m @ 5:30/km (90s rest) + 1 km CD")
    add(date(2026, 3, 26), "rest", 0, "", "Rest day")
    add(date(2026, 3, 27), "easy", 5, "7:00+/km", "5 km easy run")
    add(date(2026, 3, 28), "rest", 0, "", "Rest day")
    add(date(2026, 3, 29), "long", 8, "7:00+/km", "8 km long run")
    # Week 4
    add(date(2026, 3, 30), "easy", 4, "7:00+/km", "4 km easy run")
    add(date(2026, 3, 31), "rest", 0, "", "Rest day")
    add(date(2026, 4, 1), "tempo", 5, "6:00/km", "1.5 km WU + 2 km @ 6:00/km + 1.5 km CD")
    add(date(2026, 4, 2), "rest", 0, "", "Rest day")
    add(date(2026, 4, 3), "easy", 5, "7:00+/km", "5 km easy run")
    add(date(2026, 4, 4), "rest", 0, "", "Rest day")
    add(date(2026, 4, 5), "long", 9, "7:00+/km", "9 km long run")
    # Week 5
    add(date(2026, 4, 6), "easy", 5, "7:00+/km", "5 km easy run")
    add(date(2026, 4, 7), "rest", 0, "", "Rest day")
    add(date(2026, 4, 8), "tempo", 6, "6:00/km", "1.5 km WU + 3 km @ 6:00/km + 1.5 km CD")
    add(date(2026, 4, 9), "rest", 0, "", "Rest day")
    add(date(2026, 4, 10), "easy", 5, "7:00+/km", "5 km easy run")
    add(date(2026, 4, 11), "rest", 0, "", "Rest day")
    add(date(2026, 4, 12), "long", 10, "7:00+/km", "10 km (middle 3 km @ 6:15/km)")
    # Week 6
    add(date(2026, 4, 13), "easy", 4, "7:00+/km", "4 km easy run")
    add(date(2026, 4, 14), "rest", 0, "", "Rest day")
    add(date(2026, 4, 15), "tempo", 6.5, "6:00/km", "1.5 km WU + 4 km @ 6:00/km + 1 km CD")
    add(date(2026, 4, 16), "rest", 0, "", "Rest day")
    add(date(2026, 4, 17), "easy", 4, "7:00+/km", "4 km easy run")
    add(date(2026, 4, 18), "rest", 0, "", "Rest day")
    add(date(2026, 4, 19), "long", 8, "7:00+/km", "8 km easy long run")
    # Week 7 (Taper + Race)
    add(date(2026, 4, 20), "easy", 3, "7:00+/km", "3 km easy run")
    add(date(2026, 4, 21), "rest", 0, "", "Rest day")
    add(date(2026, 4, 22), "strides", 3, "7:00+/km", "3 km easy + 4x100m strides")
    add(date(2026, 4, 23), "rest", 0, "", "Rest day")
    add(date(2026, 4, 24), "easy", 2, "7:00+/km", "2 km shakeout jog")
    add(date(2026, 4, 25), "rest", 0, "", "Full rest — lay out race gear")
    add(date(2026, 4, 26), "rest", 0, "", "Rest — light food, hydrate, sleep early")
    add(date(2026, 4, 27), "race", 10, "6:00/km", "10K RACE DAY — Sub-60 target!")

    return sessions


def upgrade() -> None:
    plans_table = op.create_table(
        "training_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("goal", sa.String(500), nullable=False, server_default=""),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_plans_user_id", "training_plans", ["user_id"])

    sessions_table = op.create_table(
        "training_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("training_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("session_type", sa.String(50), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pace_target", sa.String(50), nullable=False, server_default=""),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_sessions_plan_id", "training_sessions", ["plan_id"])

    user_id = _seed_user_id()
    if user_id is None:
        return

    op.bulk_insert(plans_table, [{
        "id": 1,
        "user_id": user_id,
        "name": "Sub-60 10K Plan",
        "goal": "Run a 10K in under 60 minutes",
        "start_date": date(2026, 3, 10),
        "end_date": date(2026, 4, 27),
        "is_active": True,
    }])

    rows = [{"plan_id": 1, **s} for s in _hardcoded_sessions()]
    op.bulk_insert(sessions_table, rows)

    op.execute("SELECT setval('training_plans_id_seq', (SELECT MAX(id) FROM training_plans))")
    op.execute("SELECT setval('training_sessions_id_seq', (SELECT MAX(id) FROM training_sessions))")


def downgrade() -> None:
    op.drop_index("ix_training_sessions_plan_id", table_name="training_sessions")
    op.drop_table("training_sessions")
    op.drop_index("ix_training_plans_user_id", table_name="training_plans")
    op.drop_table("training_plans")

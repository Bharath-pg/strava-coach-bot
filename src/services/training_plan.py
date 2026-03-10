from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class PlannedSession:
    date: date
    session_type: str
    distance_km: float
    pace_target: str
    description: str


def _build_plan() -> list[PlannedSession]:
    """Build the 7-week sub-60 10K training plan (Mar 10 – Apr 27, 2026)."""
    sessions: list[PlannedSession] = []

    def _add(d: date, stype: str, km: float, pace: str, desc: str) -> None:
        sessions.append(PlannedSession(d, stype, km, pace, desc))

    # Week 1: Mar 10-15 (Build frequency)
    _add(date(2026, 3, 10), "easy", 3.95, "7:00+/km", "Morning run (done)")
    _add(date(2026, 3, 11), "rest", 0, "", "Rest day")
    _add(date(2026, 3, 12), "easy", 4, "7:00+/km", "4 km easy run")
    _add(date(2026, 3, 13), "rest", 0, "", "Rest day")
    _add(date(2026, 3, 14), "easy", 5, "7:00+/km", "5 km easy run")
    _add(date(2026, 3, 15), "long", 6, "7:00+/km", "6 km long run")

    # Week 2: Mar 16-22 (Introduce strides)
    _add(date(2026, 3, 16), "easy", 4, "7:00+/km", "4 km easy run")
    _add(date(2026, 3, 17), "rest", 0, "", "Rest day")
    _add(date(2026, 3, 18), "strides", 4, "7:00+/km", "4 km easy + 4x100m strides")
    _add(date(2026, 3, 19), "rest", 0, "", "Rest day")
    _add(date(2026, 3, 20), "easy", 4, "7:00+/km", "4 km easy run")
    _add(date(2026, 3, 21), "rest", 0, "", "Rest day")
    _add(date(2026, 3, 22), "long", 7, "7:00+/km", "7 km long run")

    # Week 3: Mar 23-29 (First speed work)
    _add(date(2026, 3, 23), "easy", 4, "7:00+/km", "4 km easy run")
    _add(date(2026, 3, 24), "rest", 0, "", "Rest day")
    _add(date(2026, 3, 25), "intervals", 4.5, "5:30/km", "1.5 km WU + 5x400m @ 5:30/km (90s rest) + 1 km CD")
    _add(date(2026, 3, 26), "rest", 0, "", "Rest day")
    _add(date(2026, 3, 27), "easy", 5, "7:00+/km", "5 km easy run")
    _add(date(2026, 3, 28), "rest", 0, "", "Rest day")
    _add(date(2026, 3, 29), "long", 8, "7:00+/km", "8 km long run")

    # Week 4: Mar 30 – Apr 5 (Introduce tempo)
    _add(date(2026, 3, 30), "easy", 4, "7:00+/km", "4 km easy run")
    _add(date(2026, 3, 31), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 1), "tempo", 5, "6:00/km", "1.5 km WU + 2 km @ 6:00/km + 1.5 km CD")
    _add(date(2026, 4, 2), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 3), "easy", 5, "7:00+/km", "5 km easy run")
    _add(date(2026, 4, 4), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 5), "long", 9, "7:00+/km", "9 km long run")

    # Week 5: Apr 6-12 (Peak tempo)
    _add(date(2026, 4, 6), "easy", 5, "7:00+/km", "5 km easy run")
    _add(date(2026, 4, 7), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 8), "tempo", 6, "6:00/km", "1.5 km WU + 3 km @ 6:00/km + 1.5 km CD")
    _add(date(2026, 4, 9), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 10), "easy", 5, "7:00+/km", "5 km easy run")
    _add(date(2026, 4, 11), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 12), "long", 10, "7:00+/km", "10 km (middle 3 km @ 6:15/km)")

    # Week 6: Apr 13-19 (Race-pace confidence)
    _add(date(2026, 4, 13), "easy", 4, "7:00+/km", "4 km easy run")
    _add(date(2026, 4, 14), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 15), "tempo", 6.5, "6:00/km", "1.5 km WU + 4 km @ 6:00/km + 1 km CD")
    _add(date(2026, 4, 16), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 17), "easy", 4, "7:00+/km", "4 km easy run")
    _add(date(2026, 4, 18), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 19), "long", 8, "7:00+/km", "8 km easy long run")

    # Week 7: Apr 20-27 (Taper + Race)
    _add(date(2026, 4, 20), "easy", 3, "7:00+/km", "3 km easy run")
    _add(date(2026, 4, 21), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 22), "strides", 3, "7:00+/km", "3 km easy + 4x100m strides")
    _add(date(2026, 4, 23), "rest", 0, "", "Rest day")
    _add(date(2026, 4, 24), "easy", 2, "7:00+/km", "2 km shakeout jog")
    _add(date(2026, 4, 25), "rest", 0, "", "Full rest — lay out race gear")
    _add(date(2026, 4, 26), "rest", 0, "", "Rest — light food, hydrate, sleep early")
    _add(date(2026, 4, 27), "race", 10, "6:00/km", "10K RACE DAY — Sub-60 target!")

    return sessions


TRAINING_PLAN: list[PlannedSession] = _build_plan()
_PLAN_BY_DATE: dict[date, PlannedSession] = {s.date: s for s in TRAINING_PLAN}

PLAN_START = TRAINING_PLAN[0].date
PLAN_END = TRAINING_PLAN[-1].date


def get_session(d: date) -> PlannedSession | None:
    return _PLAN_BY_DATE.get(d)


def get_week_sessions(reference_date: date) -> list[PlannedSession]:
    """Return all planned sessions for the ISO week containing *reference_date*."""
    monday = reference_date - timedelta(days=reference_date.weekday())
    return [s for s in TRAINING_PLAN if monday <= s.date < monday + timedelta(days=7)]


def get_week_number(d: date) -> int:
    """1-based training week number (Week 1 starts Mar 9, 2026 — the Monday of plan start)."""
    plan_monday = PLAN_START - timedelta(days=PLAN_START.weekday())
    delta = (d - plan_monday).days
    if delta < 0:
        return 0
    return delta // 7 + 1


def get_planned_distance(sessions: list[PlannedSession]) -> float:
    return sum(s.distance_km for s in sessions if s.session_type != "rest")


def get_planned_run_count(sessions: list[PlannedSession]) -> int:
    return sum(1 for s in sessions if s.session_type != "rest")

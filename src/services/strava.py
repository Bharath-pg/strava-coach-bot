from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

_cached_access_token: str = ""
_token_expires_at: int = 0


@dataclass
class ActivitySummary:
    activity_id: int
    name: str
    activity_type: str
    distance_km: float
    moving_time_seconds: int
    elapsed_time_seconds: int
    start_date: datetime.datetime
    average_speed_mps: float

    @property
    def pace_per_km(self) -> str:
        if self.distance_km <= 0:
            return "N/A"
        total_seconds = self.moving_time_seconds / self.distance_km
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        return f"{minutes}:{seconds:02d}/km"

    @property
    def moving_time_formatted(self) -> str:
        m, s = divmod(self.moving_time_seconds, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h {m}m {s}s"
        return f"{m}m {s}s"


async def _refresh_access_token() -> str:
    global _cached_access_token, _token_expires_at

    now_epoch = int(datetime.datetime.now(datetime.UTC).timestamp())
    if _cached_access_token and _token_expires_at > now_epoch + 60:
        return _cached_access_token

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "refresh_token": settings.strava_refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _cached_access_token = data["access_token"]
    _token_expires_at = data["expires_at"]
    logger.info("Strava token refreshed, expires at %s", _token_expires_at)
    return _cached_access_token


async def get_activities(
    *,
    after: datetime.date | None = None,
    before: datetime.date | None = None,
    activity_type: str = "Run",
) -> list[ActivitySummary]:
    token = await _refresh_access_token()

    params: dict[str, str | int] = {"per_page": 200}
    if after:
        after_dt = datetime.datetime.combine(after, datetime.time.min, tzinfo=datetime.UTC)
        params["after"] = int(after_dt.timestamp())
    if before:
        before_dt = datetime.datetime.combine(
            before + datetime.timedelta(days=1), datetime.time.min, tzinfo=datetime.UTC
        )
        params["before"] = int(before_dt.timestamp())

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        resp.raise_for_status()
        raw_activities = resp.json()

    results: list[ActivitySummary] = []
    for act in raw_activities:
        if activity_type and act.get("type") != activity_type:
            continue
        results.append(
            ActivitySummary(
                activity_id=act["id"],
                name=act.get("name", ""),
                activity_type=act.get("type", ""),
                distance_km=round(act.get("distance", 0) / 1000, 2),
                moving_time_seconds=act.get("moving_time", 0),
                elapsed_time_seconds=act.get("elapsed_time", 0),
                start_date=datetime.datetime.fromisoformat(
                    act["start_date_local"].replace("Z", "+00:00")
                ),
                average_speed_mps=act.get("average_speed", 0),
            )
        )

    results.sort(key=lambda a: a.start_date)
    return results


async def get_week_activities(reference_date: datetime.date) -> list[ActivitySummary]:
    monday = reference_date - datetime.timedelta(days=reference_date.weekday())
    sunday = monday + datetime.timedelta(days=6)
    return await get_activities(after=monday, before=sunday)


async def get_day_activities(d: datetime.date) -> list[ActivitySummary]:
    return await get_activities(after=d, before=d)

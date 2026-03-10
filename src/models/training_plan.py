from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(String(500), default="")
    start_date: Mapped[datetime.date] = mapped_column(Date)
    end_date: Mapped[datetime.date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sessions: Mapped[list[TrainingSession]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="TrainingSession.date"
    )

    def __repr__(self) -> str:
        return f"<TrainingPlan(id={self.id}, name={self.name!r}, active={self.is_active})>"


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id", ondelete="CASCADE"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    session_type: Mapped[str] = mapped_column(String(50))
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    pace_target: Mapped[str] = mapped_column(String(50), default="")
    description: Mapped[str] = mapped_column(String(500), default="")

    plan: Mapped[TrainingPlan] = relationship(back_populates="sessions")

    def __repr__(self) -> str:
        return f"<TrainingSession(id={self.id}, date={self.date}, type={self.session_type!r})>"

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.expense import Expense


async def add_expense(
    session: AsyncSession,
    *,
    user_id: int,
    amount: Decimal,
    currency: str = "USD",
    category: str = "other",
    description: str = "",
    date: datetime.date | None = None,
) -> Expense:
    expense = Expense(
        user_id=user_id,
        amount=amount,
        currency=currency.upper(),
        category=category.lower(),
        description=description,
        date=date or datetime.date.today(),
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense


async def query_expenses(
    session: AsyncSession,
    *,
    user_id: int,
    category: str | None = None,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    limit: int = 50,
) -> list[Expense]:
    stmt = select(Expense).where(Expense.user_id == user_id)
    if category:
        stmt = stmt.where(Expense.category == category.lower())
    if start_date:
        stmt = stmt.where(Expense.date >= start_date)
    if end_date:
        stmt = stmt.where(Expense.date <= end_date)
    stmt = stmt.order_by(Expense.date.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def expense_summary(
    session: AsyncSession,
    *,
    user_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> dict[str, object]:
    """Return per-category totals and a grand total for the given period."""
    stmt = select(
        Expense.category,
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("count"),
    ).where(Expense.user_id == user_id)

    if start_date:
        stmt = stmt.where(Expense.date >= start_date)
    if end_date:
        stmt = stmt.where(Expense.date <= end_date)

    stmt = stmt.group_by(Expense.category).order_by(func.sum(Expense.amount).desc())
    result = await session.execute(stmt)
    rows = result.all()

    categories = {row.category: {"total": float(row.total), "count": row.count} for row in rows}
    grand_total = sum(cat["total"] for cat in categories.values())

    return {
        "categories": categories,
        "grand_total": grand_total,
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }


def period_to_dates(period: str) -> tuple[datetime.date, datetime.date]:
    """Convert a human period name to (start_date, end_date)."""
    today = datetime.date.today()
    if period == "today":
        return today, today
    elif period == "week":
        start = today - datetime.timedelta(days=today.weekday())
        return start, today
    elif period == "month":
        start = today.replace(day=1)
        return start, today
    elif period == "year":
        start = today.replace(month=1, day=1)
        return start, today
    else:
        return today.replace(month=1, day=1), today

import uuid
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Invoice, Payment, Project


async def get_project_with_biweekly_records(
    session: AsyncSession,
    project_id: uuid.UUID,
    start_date: date,
    end_date: Optional[date] = None,
) -> Optional[Project]:
    """
    Fetch a Project by ID and eagerly load all associated Invoices and Payments
    within a specific two-week (14 days) date range.

    Uses `selectinload` with relationship-level filtering in SQLAlchemy 2.0.
    """
    if end_date is None:
        end_date = start_date + timedelta(days=14)

    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(
                Project.invoices.and_(
                    Invoice.date_issued >= start_date,
                    Invoice.date_issued <= end_date,
                )
            ).selectinload(Invoice.supplier),
            selectinload(
                Project.payments.and_(
                    Payment.date_paid >= start_date,
                    Payment.date_paid <= end_date,
                )
            ).selectinload(Payment.worker),
        )
    )

    result = await session.execute(stmt)
    return result.scalar_one_or_none()

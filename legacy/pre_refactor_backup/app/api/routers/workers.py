import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models import Payment, PaymentType, Worker
from app.schemas import (
    WorkerCreate,
    WorkerResponse,
    WorkerSummaryResponse,
    WorkerUpdate,
)

router = APIRouter(prefix="/workers", tags=["Trabajadores / Workers"])


@router.get(
    "/summary",
    response_model=List[WorkerSummaryResponse],
    summary="Listar plantilla de trabajadores con nómina acumulada a la fecha",
)
async def list_workers_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    Devuelve la lista de trabajadores con el total acumulado de nómina que se les ha pagado a la fecha,
    el conteo de pagos y la fecha de su último pago.
    """
    stmt = (
        select(
            Worker,
            func.coalesce(func.sum(Payment.amount), 0).label("total_payroll_accumulated"),
            func.count(Payment.id).label("total_payments_count"),
            func.max(Payment.date_paid).label("last_payment_date"),
        )
        .outerjoin(
            Payment,
            (Payment.worker_id == Worker.id) & (Payment.payment_type == PaymentType.PAYROLL),
        )
        .group_by(Worker.id)
        .order_by(Worker.full_name.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    workers_out = []
    for worker, total_payroll, count, last_date in rows:
        workers_out.append(
            WorkerSummaryResponse(
                id=worker.id,
                full_name=worker.full_name,
                role=worker.role,
                daily_rate=worker.daily_rate,
                total_payroll_accumulated=total_payroll,
                total_payments_count=count,
                last_payment_date=last_date,
                created_at=worker.created_at,
                updated_at=worker.updated_at,
            )
        )
    return workers_out


@router.get(
    "/",
    response_model=List[WorkerResponse],
    summary="Listar plantilla de trabajadores",
)
async def list_workers(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Worker)
        .offset(offset)
        .limit(limit)
        .order_by(Worker.full_name.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/",
    response_model=WorkerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dar de alta a un trabajador",
)
async def create_worker(
    payload: WorkerCreate,
    db: AsyncSession = Depends(get_db),
):
    worker = Worker(**payload.model_dump())
    db.add(worker)
    await db.flush()
    await db.refresh(worker)
    return worker


@router.get(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Obtener información de un trabajador por ID",
)
async def get_worker(
    worker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    worker = await db.get(Worker, worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado.",
        )
    return worker


@router.patch(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Actualizar información de un trabajador",
)
async def update_worker(
    worker_id: uuid.UUID,
    payload: WorkerUpdate,
    db: AsyncSession = Depends(get_db),
):
    worker = await db.get(Worker, worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado para actualizar.",
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(worker, key, value)

    await db.flush()
    await db.refresh(worker)
    return worker


@router.delete(
    "/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar trabajador del registro",
)
async def delete_worker(
    worker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    worker = await db.get(Worker, worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado para eliminar.",
        )
    await db.delete(worker)

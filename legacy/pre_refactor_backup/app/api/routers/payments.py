import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db
from app.models import Payment, PaymentType, Project, Worker
from app.schemas import PaymentCreate, PaymentResponse, PaymentUpdate

router = APIRouter(prefix="/payments", tags=["Pagos y Nómina / Payments"])


@router.get(
    "/search",
    response_model=List[PaymentResponse],
    summary="Buscar pagos con filtros de texto y proyectos",
)
async def search_payments(
    q: Optional[str] = Query(None, description="Búsqueda por texto en concepto, trabajador u obra"),
    exclude_project_id: Optional[uuid.UUID] = Query(None, description="Excluir pagos de este proyecto"),
    project_id: Optional[uuid.UUID] = Query(None, description="Filtrar por proyecto específico"),
    payment_type: Optional[PaymentType] = Query(None, description="Filtrar por tipo de pago"),
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Payment)
        .outerjoin(Payment.worker)
        .outerjoin(Payment.project)
        .options(selectinload(Payment.worker), selectinload(Payment.project))
        .order_by(Payment.date_paid.desc())
        .limit(limit)
    )
    if exclude_project_id:
        stmt = stmt.where(Payment.project_id != exclude_project_id)
    if project_id:
        stmt = stmt.where(Payment.project_id == project_id)
    if payment_type:
        stmt = stmt.where(Payment.payment_type == payment_type)
    if q and q.strip():
        search_pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            (Payment.description.ilike(search_pattern))
            | (Worker.full_name.ilike(search_pattern))
            | (Project.name.ilike(search_pattern))
        )

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/",
    response_model=List[PaymentResponse],
    summary="Listar pagos y dispersiones registradas",
)
async def list_payments(
    project_id: Optional[uuid.UUID] = None,
    worker_id: Optional[uuid.UUID] = None,
    payment_type: Optional[PaymentType] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Payment)
        .options(selectinload(Payment.worker), selectinload(Payment.project))
        .offset(offset)
        .limit(limit)
        .order_by(Payment.date_paid.desc())
    )
    if project_id:
        stmt = stmt.where(Payment.project_id == project_id)
    if worker_id:
        stmt = stmt.where(Payment.worker_id == worker_id)
    if payment_type:
        stmt = stmt.where(Payment.payment_type == payment_type)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un pago (nómina, transferencia o nota de gasto)",
)
async def create_payment(
    payload: PaymentCreate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, payload.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El proyecto con ID '{payload.project_id}' no fue encontrado.",
        )

    if payload.worker_id:
        worker = await db.get(Worker, payload.worker_id)
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El trabajador con ID '{payload.worker_id}' no fue encontrado.",
            )

    db_payment = Payment(**payload.model_dump())
    db.add(db_payment)
    await db.flush()
    await db.refresh(db_payment, attribute_names=["worker", "project"])
    return db_payment


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Obtener pago por ID",
)
async def get_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Payment)
        .where(Payment.id == payment_id)
        .options(selectinload(Payment.worker))
    )
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado.",
        )
    return payment


@router.patch(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Actualizar información de un pago",
)
async def update_payment(
    payment_id: uuid.UUID,
    payload: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
):
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado para actualizar.",
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(payment, key, value)

    await db.flush()
    await db.refresh(payment, attribute_names=["worker", "project"])
    return payment


@router.delete(
    "/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar registro de pago",
)
async def delete_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado para eliminar.",
        )
    await db.delete(payment)

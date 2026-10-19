import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models import Supplier
from app.schemas import SupplierCreate, SupplierResponse, SupplierUpdate

router = APIRouter(prefix="/suppliers", tags=["Proveedores / Suppliers"])


@router.get(
    "/",
    response_model=List[SupplierResponse],
    summary="Listar catálogo de proveedores",
)
async def list_suppliers(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Supplier)
        .offset(offset)
        .limit(limit)
        .order_by(Supplier.name.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo proveedor",
)
async def create_supplier(
    payload: SupplierCreate,
    db: AsyncSession = Depends(get_db),
):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    await db.flush()
    await db.refresh(supplier)
    return supplier


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Obtener proveedor por ID",
)
async def get_supplier(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado.",
        )
    return supplier


@router.patch(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Actualizar datos de un proveedor",
)
async def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado para actualizar.",
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, key, value)

    await db.flush()
    await db.refresh(supplier)
    return supplier


@router.delete(
    "/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar proveedor",
)
async def delete_supplier(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado para eliminar.",
        )
    await db.delete(supplier)

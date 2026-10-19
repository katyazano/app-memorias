"""Router para CRUD de Proveedores."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Gasto, Proveedor, TipoProveedor
from app.schemas import ProveedorCreate, ProveedorOut, ProveedorUpdate

router = APIRouter(prefix="/proveedores", tags=["Proveedores"])


@router.get("", response_model=List[ProveedorOut])
def listar_proveedores(
    q: Optional[str] = Query(None, description="Búsqueda por RFC, razón social o alias"),
    db: Session = Depends(get_db),
):
    query = db.query(Proveedor)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Proveedor.rfc.ilike(term),
                Proveedor.razon_social.ilike(term),
                Proveedor.alias.ilike(term),
            )
        )
    return query.order_by(Proveedor.razon_social.asc()).all()


@router.post("", response_model=ProveedorOut, status_code=status.HTTP_201_CREATED)
def crear_proveedor(data: ProveedorCreate, db: Session = Depends(get_db)):
    if data.rfc:
        existente = db.query(Proveedor).filter(Proveedor.rfc == data.rfc).first()
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un proveedor registrado con el RFC {data.rfc}.",
            )

    proveedor = Proveedor(
        tipo=data.tipo,
        rfc=data.rfc,
        razon_social=data.razon_social.strip(),
        alias=data.alias.strip() if data.alias else None,
    )
    db.add(proveedor)
    db.flush()
    return proveedor


@router.get("/{proveedor_id}", response_model=ProveedorOut)
def obtener_proveedor(proveedor_id: int, db: Session = Depends(get_db)):
    prov = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not prov:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")
    return prov


@router.patch("/{proveedor_id}", response_model=ProveedorOut)
def actualizar_proveedor(proveedor_id: int, data: ProveedorUpdate, db: Session = Depends(get_db)):
    prov = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not prov:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")

    datos = data.model_dump(exclude_unset=True)
    if "rfc" in datos and datos["rfc"]:
        existente = db.query(Proveedor).filter(Proveedor.rfc == datos["rfc"], Proveedor.id != prov.id).first()
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe otro proveedor con el RFC {datos['rfc']}.",
            )

    for campo, valor in datos.items():
        if campo in ("razon_social", "alias") and isinstance(valor, str):
            valor = valor.strip() if valor else None
        setattr(prov, campo, valor)

    # Si el tipo se cambia a con_factura, verificar que tenga RFC
    if prov.tipo == TipoProveedor.CON_FACTURA and not prov.rfc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Un proveedor con factura requiere un RFC válido.",
        )

    db.flush()
    return prov


@router.delete("/{proveedor_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proveedor(proveedor_id: int, db: Session = Depends(get_db)):
    prov = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not prov:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")

    tiene_gastos = db.query(Gasto).filter(Gasto.proveedor_id == proveedor_id).count() > 0
    if tiene_gastos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar el proveedor porque tiene gastos asociados.",
        )

    db.delete(prov)
    db.flush()
    return None

"""Router para CRUD de Trabajadores y consulta de sus pagos."""
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PagoRaya, Trabajador
from app.schemas import PagoRayaOut, TrabajadorCreate, TrabajadorOut, TrabajadorPagosOut, TrabajadorUpdate
from app.types import money

router = APIRouter(prefix="/trabajadores", tags=["Trabajadores"])


def raya_a_out(r: PagoRaya) -> PagoRayaOut:
    return PagoRayaOut(
        id=r.id,
        obra_id=r.obra_id,
        trabajador_id=r.trabajador_id,
        trabajador_nombre=r.trabajador.nombre if r.trabajador else "",
        oficio=r.trabajador.oficio if r.trabajador else "",
        semana_numero=r.semana_numero,
        fecha_inicio=r.fecha_inicio,
        fecha_fin=r.fecha_fin,
        tipo=r.tipo,
        cantidad=r.cantidad,
        tarifa=r.tarifa,
        importe=r.importe,
    )


@router.get("", response_model=List[TrabajadorOut])
def listar_trabajadores(db: Session = Depends(get_db)):
    return db.query(Trabajador).order_by(Trabajador.nombre.asc()).all()


@router.post("", response_model=TrabajadorOut, status_code=status.HTTP_201_CREATED)
def crear_trabajador(data: TrabajadorCreate, db: Session = Depends(get_db)):
    t = Trabajador(nombre=data.nombre.strip(), oficio=data.oficio.strip())
    db.add(t)
    db.flush()
    return t


@router.get("/{trabajador_id}", response_model=TrabajadorOut)
def obtener_trabajador(trabajador_id: int, db: Session = Depends(get_db)):
    t = db.query(Trabajador).filter(Trabajador.id == trabajador_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado.")
    return t


@router.patch("/{trabajador_id}", response_model=TrabajadorOut)
def actualizar_trabajador(trabajador_id: int, data: TrabajadorUpdate, db: Session = Depends(get_db)):
    t = db.query(Trabajador).filter(Trabajador.id == trabajador_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado.")

    datos = data.model_dump(exclude_unset=True)
    for campo, valor in datos.items():
        if isinstance(valor, str):
            valor = valor.strip()
        setattr(t, campo, valor)

    db.flush()
    return t


@router.delete("/{trabajador_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_trabajador(trabajador_id: int, db: Session = Depends(get_db)):
    t = db.query(Trabajador).filter(Trabajador.id == trabajador_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado.")

    tiene_pagos = db.query(PagoRaya).filter(PagoRaya.trabajador_id == trabajador_id).count() > 0
    if tiene_pagos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar el trabajador porque tiene pagos de raya registrados.",
        )

    db.delete(t)
    db.flush()
    return None


@router.get("/{trabajador_id}/pagos", response_model=TrabajadorPagosOut)
def obtener_pagos_trabajador(trabajador_id: int, db: Session = Depends(get_db)):
    t = db.query(Trabajador).filter(Trabajador.id == trabajador_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado.")

    pagos = (
        db.query(PagoRaya)
        .filter(PagoRaya.trabajador_id == trabajador_id)
        .order_by(PagoRaya.fecha_fin.desc(), PagoRaya.id.desc())
        .all()
    )
    total_acumulado = sum((p.importe for p in pagos), Decimal("0.00"))

    return TrabajadorPagosOut(
        trabajador=t,
        total_acumulado=money(total_acumulado),
        pagos=[raya_a_out(p) for p in pagos],
    )

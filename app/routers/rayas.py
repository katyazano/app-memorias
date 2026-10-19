"""Router para Pagos de Raya (nómina de obra)."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Obra, PagoRaya, Trabajador
from app.routers.trabajadores import raya_a_out
from app.schemas import PagoRayaCreate, PagoRayaOut, PagoRayaUpdate, PagosSemanaCreate
from app.types import money

router = APIRouter(tags=["Rayas"])


@router.get("/obras/{obra_id}/rayas", response_model=List[PagoRayaOut])
def listar_rayas_de_obra(obra_id: int, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    rayas = (
        db.query(PagoRaya)
        .filter(PagoRaya.obra_id == obra_id)
        .order_by(PagoRaya.fecha_fin.desc(), PagoRaya.id.desc())
        .all()
    )
    return [raya_a_out(r) for r in rayas]


@router.post("/obras/{obra_id}/rayas", response_model=PagoRayaOut, status_code=status.HTTP_201_CREATED)
def crear_pago_raya(obra_id: int, data: PagoRayaCreate, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    trabajador = db.query(Trabajador).filter(Trabajador.id == data.trabajador_id).first()
    if not trabajador:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado.")

    # El importe oficial lo calcula SIEMPRE el backend con Decimal: cantidad * tarifa
    importe = money(data.cantidad * data.tarifa)

    raya = PagoRaya(
        obra_id=obra_id,
        trabajador_id=data.trabajador_id,
        semana_numero=data.semana_numero,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        tipo=data.tipo,
        cantidad=data.cantidad,
        tarifa=data.tarifa,
        importe=importe,
    )
    db.add(raya)
    db.flush()
    return raya_a_out(raya)


@router.post("/obras/{obra_id}/rayas/semana", response_model=List[PagoRayaOut], status_code=status.HTTP_201_CREATED)
def crear_pagos_semana(obra_id: int, data: PagosSemanaCreate, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    creados: List[PagoRaya] = []
    for fila in data.filas:
        trabajador = db.query(Trabajador).filter(Trabajador.id == fila.trabajador_id).first()
        if not trabajador:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trabajador #{fila.trabajador_id} no encontrado.",
            )

        # Cálculo oficial del backend con Decimal
        imp = money(fila.cantidad * fila.tarifa)
        raya = PagoRaya(
            obra_id=obra_id,
            trabajador_id=fila.trabajador_id,
            semana_numero=data.semana_numero,
            fecha_inicio=data.fecha_inicio,
            fecha_fin=data.fecha_fin,
            tipo=fila.tipo,
            cantidad=fila.cantidad,
            tarifa=fila.tarifa,
            importe=imp,
        )
        db.add(raya)
        creados.append(raya)

    db.flush()
    return [raya_a_out(r) for r in creados]


@router.get("/rayas/buscar", response_model=List[PagoRayaOut])
def buscar_rayas(
    q: Optional[str] = Query(None, description="Término de búsqueda: trabajador, oficio, semana u obra"),
    excluir_obra: Optional[int] = Query(None, description="ID de obra a excluir del resultado"),
    desde: Optional[date] = Query(None, description="Fecha mínima de fin de semana"),
    hasta: Optional[date] = Query(None, description="Fecha máxima de fin de semana"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = (
        db.query(PagoRaya)
        .join(PagoRaya.trabajador)
        .join(PagoRaya.obra)
        .options(joinedload(PagoRaya.trabajador), joinedload(PagoRaya.obra))
    )

    if excluir_obra is not None:
        query = query.filter(PagoRaya.obra_id != excluir_obra)
    if desde is not None:
        query = query.filter(PagoRaya.fecha_fin >= desde)
    if hasta is not None:
        query = query.filter(PagoRaya.fecha_fin <= hasta)

    if q and q.strip():
        term = f"%{q.strip()}%"
        condiciones = [
            Trabajador.nombre.ilike(term),
            Trabajador.oficio.ilike(term),
            Obra.nombre.ilike(term),
        ]
        try:
            num = int(q.strip())
            condiciones.append(PagoRaya.semana_numero == num)
        except ValueError:
            pass
        query = query.filter(or_(*condiciones))

    rayas = query.order_by(PagoRaya.fecha_fin.desc(), PagoRaya.id.desc()).limit(limit).all()
    return [raya_a_out(r) for r in rayas]


@router.get("/rayas/{raya_id}", response_model=PagoRayaOut)
def obtener_pago_raya(raya_id: int, db: Session = Depends(get_db)):
    raya = db.query(PagoRaya).filter(PagoRaya.id == raya_id).first()
    if not raya:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pago de raya no encontrado.")
    return raya_a_out(raya)


@router.patch("/rayas/{raya_id}", response_model=PagoRayaOut)
def actualizar_pago_raya(raya_id: int, data: PagoRayaUpdate, db: Session = Depends(get_db)):
    raya = db.query(PagoRaya).filter(PagoRaya.id == raya_id).first()
    if not raya:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pago de raya no encontrado.")

    datos = data.model_dump(exclude_unset=True)
    if "trabajador_id" in datos:
        trabajador = db.query(Trabajador).filter(Trabajador.id == datos["trabajador_id"]).first()
        if not trabajador:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no encontrado.")

    for campo, valor in datos.items():
        setattr(raya, campo, valor)

    # Si se modificó cantidad o tarifa, el importe oficial lo recalcula el backend
    if "cantidad" in datos or "tarifa" in datos:
        raya.importe = money(raya.cantidad * raya.tarifa)

    db.flush()
    return raya_a_out(raya)


@router.delete("/rayas/{raya_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_pago_raya(raya_id: int, db: Session = Depends(get_db)):
    raya = db.query(PagoRaya).filter(PagoRaya.id == raya_id).first()
    if not raya:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pago de raya no encontrado.")

    db.delete(raya)
    db.flush()
    return None

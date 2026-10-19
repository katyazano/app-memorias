"""Router para CRUD de Obras y resúmenes para dashboard."""
import json
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EstadoMemoria, Gasto, Memoria, Obra, PagoRaya
from app.schemas import (
    MemoriaResumenOut,
    ObraCreate,
    ObraOut,
    ObraResumenCardOut,
    ObraUpdate,
)
from app.services.memoria_service import memoria_a_resumen
from app.services.storage import delete_obra_dir
from app.types import money

router = APIRouter(prefix="/obras", tags=["Obras"])


def calcular_resumen_obra(obra: Obra, db: Session) -> ObraResumenCardOut:
    cerradas = (
        db.query(Memoria)
        .filter(Memoria.obra_id == obra.id, Memoria.estado == EstadoMemoria.CERRADA)
        .all()
    )
    gastado_memorias = Decimal("0.00")
    for m in cerradas:
        try:
            data = json.loads(m.snapshot_json)
            gastado_memorias += Decimal(str(data.get("totales", {}).get("total_memoria", "0.00")))
        except Exception:
            pass

    gastado_total = money(obra.saldo_inicial_memorias_anteriores + gastado_memorias)
    max_memoria = db.query(func.max(Memoria.numero)).filter(Memoria.obra_id == obra.id).scalar()
    total_mems = db.query(Memoria).filter(Memoria.obra_id == obra.id).count()
    total_gastos = db.query(Gasto).filter(Gasto.obra_id == obra.id).count()
    
    # Suma de gastos (facturas + notas + manuales)
    gastos_obra = db.query(Gasto).filter(Gasto.obra_id == obra.id).all()
    total_gastos_puros = sum((g.importe for g in gastos_obra), Decimal("0.00"))

    # Suma de rayas
    rayas_obra = db.query(PagoRaya).filter(PagoRaya.obra_id == obra.id).all()
    total_rayas = sum((r.importe for r in rayas_obra), Decimal("0.00"))

    # Gastos registrados = gastos (facturas + notas + manuales) + rayas (excluyendo anticipos)
    total_registrado = total_gastos_puros + total_rayas

    return ObraResumenCardOut(
        id=obra.id,
        nombre=obra.nombre,
        ubicacion=obra.ubicacion,
        propietario=obra.propietario,
        porcentaje_honorarios=obra.porcentaje_honorarios,
        saldo_inicial_transferencias=obra.saldo_inicial_transferencias,
        saldo_inicial_efectivo=obra.saldo_inicial_efectivo,
        saldo_inicial_rayas=obra.saldo_inicial_rayas,
        saldo_inicial_memorias_anteriores=obra.saldo_inicial_memorias_anteriores,
        saldo_inicial_acumulado=obra.saldo_inicial_acumulado,
        saldo_inicial_gastado=obra.saldo_inicial_gastado,
        numero_ultima_memoria_previa=obra.numero_ultima_memoria_previa,
        estado=obra.estado,
        gastado_a_la_fecha=gastado_total,
        total_gastado_registrado=money(total_registrado),
        total_gastos_puros=money(total_gastos_puros),
        total_rayas=money(total_rayas),
        numero_ultima_memoria=max_memoria,
        total_memorias=total_mems,
        total_gastos=total_gastos,
    )


@router.get("", response_model=List[ObraOut])
def listar_obras(db: Session = Depends(get_db)):
    return db.query(Obra).order_by(Obra.id.desc()).all()


# Importante: /obras/resumen se declara antes de /obras/{obra_id}
@router.get("/resumen", response_model=List[ObraResumenCardOut])
def listar_resumenes_obras(db: Session = Depends(get_db)):
    obras = db.query(Obra).order_by(Obra.id.desc()).all()
    return [calcular_resumen_obra(o, db) for o in obras]


@router.post("", response_model=ObraOut, status_code=status.HTTP_201_CREATED)
def crear_obra(data: ObraCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    # Si los legacy vienen None, removerlos para no sobreescribir con el setter de la property
    if d.get("saldo_inicial_acumulado") is None:
        d.pop("saldo_inicial_acumulado", None)
    if d.get("saldo_inicial_gastado") is None:
        d.pop("saldo_inicial_gastado", None)
    obra = Obra(**d)
    db.add(obra)
    db.flush()
    return obra


@router.get("/{obra_id}/resumen", response_model=ObraResumenCardOut)
def obtener_resumen_obra(obra_id: int, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")
    return calcular_resumen_obra(obra, db)


@router.get("/{obra_id}", response_model=ObraOut)
def obtener_obra(obra_id: int, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")
    return obra


@router.patch("/{obra_id}", response_model=ObraOut)
def actualizar_obra(obra_id: int, data: ObraUpdate, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    datos = data.model_dump(exclude_unset=True)
    for campo, valor in datos.items():
        setattr(obra, campo, valor)

    db.flush()
    return obra


@router.delete("/{obra_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_obra(
    obra_id: int,
    forzar: bool = Query(False, description="Forzar eliminación si tiene memorias cerradas"),
    db: Session = Depends(get_db),
):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    tiene_cerradas = (
        db.query(Memoria)
        .filter(Memoria.obra_id == obra.id, Memoria.estado == EstadoMemoria.CERRADA)
        .count()
        > 0
    )
    if tiene_cerradas and not forzar:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La obra tiene memorias cerradas. Usa ?forzar=true si realmente deseas eliminarla.",
        )

    db.delete(obra)
    db.flush()
    delete_obra_dir(obra_id)
    return None


@router.get("/{obra_id}/memorias", response_model=List[MemoriaResumenOut])
def listar_memorias_de_obra(obra_id: int, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    memorias = (
        db.query(Memoria)
        .filter(Memoria.obra_id == obra_id)
        .order_by(Memoria.numero.desc())
        .all()
    )
    return [memoria_a_resumen(m) for m in memorias]

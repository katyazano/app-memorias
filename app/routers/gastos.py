"""Router para Gastos (manuales, notas, búsqueda entre obras y gestión general)."""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Factura, Gasto, MetodoPago, Obra, OrigenGasto, Proveedor
from app.schemas import FacturaOut, GastoManualCreate, GastoOut, GastoUpdate
from app.services.storage import delete_file

router = APIRouter(tags=["Gastos"])


def gasto_a_out(g: Gasto) -> GastoOut:
    fact_out = None
    if g.factura:
        f = g.factura
        fact_out = FacturaOut(
            id=f.id,
            uuid=f.uuid,
            serie=f.serie,
            folio=f.folio,
            subtotal=f.subtotal,
            total=f.total,
            rfc_emisor=f.rfc_emisor,
            forma_pago_sat=f.forma_pago_sat,
            metodo_pago_sat=f.metodo_pago_sat,
            ruta_xml=f.ruta_xml,
            ruta_pdf=f.ruta_pdf,
        )

    prov_nom = g.proveedor.nombre_memoria if g.proveedor else None
    obra_nom = g.obra.nombre if g.obra else f"Obra {g.obra_id}"

    return GastoOut(
        id=g.id,
        obra_id=g.obra_id,
        obra_nombre=obra_nom,
        fecha=g.fecha,
        proveedor_id=g.proveedor_id,
        proveedor_nombre=prov_nom,
        concepto_resumido=g.concepto_resumido,
        comprobante=g.comprobante or "",
        tipo_comprobante=g.tipo_comprobante or ("FACTURA" if g.origen == OrigenGasto.XML else "NOTA"),
        importe=g.importe,
        metodo_pago=g.metodo_pago,
        origen=g.origen,
        factura=fact_out,
    )


# OJO: /gastos/buscar debe declararse ANTES de /gastos/{gasto_id}
@router.get("/gastos/buscar", response_model=List[GastoOut])
def buscar_gastos(
    q: Optional[str] = Query(None, description="Término de búsqueda: concepto, comprobante, proveedor o importe"),
    excluir_obra: Optional[int] = Query(None, description="ID de obra a excluir del resultado"),
    desde: Optional[date] = Query(None, description="Fecha mínima"),
    hasta: Optional[date] = Query(None, description="Fecha máxima"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Gasto)
        .join(Gasto.obra)
        .outerjoin(Gasto.proveedor)
        .options(joinedload(Gasto.obra), joinedload(Gasto.proveedor), joinedload(Gasto.factura))
    )

    if excluir_obra is not None:
        query = query.filter(Gasto.obra_id != excluir_obra)
    if desde is not None:
        query = query.filter(Gasto.fecha >= desde)
    if hasta is not None:
        query = query.filter(Gasto.fecha <= hasta)

    if q and q.strip():
        term = f"%{q.strip()}%"
        condiciones = [
            Gasto.concepto_resumido.ilike(term),
            Gasto.comprobante.ilike(term),
            Proveedor.razon_social.ilike(term),
            Proveedor.alias.ilike(term),
            Proveedor.rfc.ilike(term),
            Obra.nombre.ilike(term),
        ]
        # Si el término es numérico, comparar también por importe
        try:
            val_dec = Decimal(q.strip().replace(",", "").replace("$", ""))
            condiciones.append(Gasto.importe == val_dec)
        except Exception:
            pass

        query = query.filter(or_(*condiciones))

    gastos = query.order_by(Gasto.fecha.desc(), Gasto.id.desc()).limit(limit).all()
    return [gasto_a_out(g) for g in gastos]


@router.get("/obras/{obra_id}/gastos", response_model=List[GastoOut])
def listar_gastos_obra(
    obra_id: int,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    metodo_pago: Optional[MetodoPago] = None,
    origen: Optional[OrigenGasto] = None,
    db: Session = Depends(get_db),
):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    query = (
        db.query(Gasto)
        .filter(Gasto.obra_id == obra_id)
        .options(joinedload(Gasto.obra), joinedload(Gasto.proveedor), joinedload(Gasto.factura))
    )
    if desde:
        query = query.filter(Gasto.fecha >= desde)
    if hasta:
        query = query.filter(Gasto.fecha <= hasta)
    if metodo_pago:
        query = query.filter(Gasto.metodo_pago == metodo_pago)
    if origen:
        query = query.filter(Gasto.origen == origen)

    gastos = query.order_by(Gasto.fecha.desc(), Gasto.id.desc()).all()
    return [gasto_a_out(g) for g in gastos]


@router.post("/obras/{obra_id}/gastos", response_model=GastoOut, status_code=status.HTTP_201_CREATED)
def crear_gasto_manual(obra_id: int, data: GastoManualCreate, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    if data.proveedor_id:
        prov = db.query(Proveedor).filter(Proveedor.id == data.proveedor_id).first()
        if not prov:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")

    tipo_comp = (data.tipo_comprobante or ("NOTA" if data.origen == "nota" else "NOTA")).upper()
    gasto = Gasto(
        obra_id=obra_id,
        fecha=data.fecha,
        proveedor_id=data.proveedor_id,
        concepto_resumido=data.concepto_resumido.strip(),
        comprobante=data.comprobante.strip(),
        tipo_comprobante=tipo_comp,
        importe=data.importe,
        metodo_pago=data.metodo_pago,
        origen=OrigenGasto.MANUAL if data.origen == "manual" else OrigenGasto.NOTA,
    )
    db.add(gasto)
    db.flush()
    return gasto_a_out(gasto)


@router.get("/gastos/{gasto_id}", response_model=GastoOut)
def obtener_gasto(gasto_id: int, db: Session = Depends(get_db)):
    g = (
        db.query(Gasto)
        .filter(Gasto.id == gasto_id)
        .options(joinedload(Gasto.obra), joinedload(Gasto.proveedor), joinedload(Gasto.factura))
        .first()
    )
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gasto no encontrado.")
    return gasto_a_out(g)


@router.patch("/gastos/{gasto_id}", response_model=GastoOut)
def actualizar_gasto(gasto_id: int, data: GastoUpdate, db: Session = Depends(get_db)):
    g = (
        db.query(Gasto)
        .filter(Gasto.id == gasto_id)
        .options(joinedload(Gasto.obra), joinedload(Gasto.proveedor), joinedload(Gasto.factura))
        .first()
    )
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gasto no encontrado.")

    datos = data.model_dump(exclude_unset=True)

    if "importe" in datos and g.origen == OrigenGasto.XML and datos["importe"] != g.importe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El importe de un gasto proveniente de XML no puede modificarse directamente.",
        )

    if "proveedor_id" in datos and datos["proveedor_id"] is not None:
        prov = db.query(Proveedor).filter(Proveedor.id == datos["proveedor_id"]).first()
        if not prov:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")

    for campo, valor in datos.items():
        if isinstance(valor, str):
            valor = valor.strip()
        setattr(g, campo, valor)

    db.flush()
    return gasto_a_out(g)


@router.delete("/gastos/{gasto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_gasto(gasto_id: int, db: Session = Depends(get_db)):
    g = db.query(Gasto).filter(Gasto.id == gasto_id).first()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gasto no encontrado.")

    if g.factura:
        delete_file(g.factura.ruta_xml)
        if g.factura.ruta_pdf:
            delete_file(g.factura.ruta_pdf)

    db.delete(g)
    db.flush()
    return None

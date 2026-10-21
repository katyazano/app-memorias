"""Servicio de cálculo, generación, persistencia y cierre de memorias."""
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Anticipo,
    Configuracion,
    EstadoMemoria,
    Gasto,
    Memoria,
    MetodoPago,
    Obra,
    OrigenGasto,
    PagoRaya,
    RegistroAuditoria,
)
from app.schemas import (
    MemoriaGuardar,
    MemoriaOut,
    MemoriaResumenOut,
    PreviewOut,
    RenglonEdit,
    RenglonMemoria,
)
from app.services.memoria_calculo import TotalesMemoria, calcular_memoria, sumar
from app.services.number_to_words import numero_a_letras_mxn
from app.types import money


def obtener_mapa_incluidos_en_cerradas(
    db: Session, excluir_memoria_id: Optional[int] = None
) -> Dict[Tuple[str, int], str]:
    """Devuelve un diccionario (ref_tipo, ref_id) -> texto de la memoria cerrada donde ya aparece."""
    q = db.query(Memoria).filter(Memoria.estado == EstadoMemoria.CERRADA)
    if excluir_memoria_id is not None:
        q = q.filter(Memoria.id != excluir_memoria_id)
    cerradas = q.all()
    mapa: Dict[Tuple[str, int], str] = {}
    for m in cerradas:
        try:
            data = json.loads(m.snapshot_json)
            renglones = data.get("renglones", [])
            for r in renglones:
                if r.get("incluido", True):
                    k = (str(r.get("ref_tipo")), int(r.get("ref_id")))
                    if k not in mapa:
                        mapa[k] = f"Ya incluido en Memoria #{m.numero}"
        except Exception:
            continue
    return mapa


def obtener_mapa_incluidos_en_borradores(
    db: Session, excluir_memoria_id: Optional[int] = None
) -> Dict[Tuple[str, int], str]:
    """Devuelve un diccionario (ref_tipo, ref_id) -> texto del borrador donde aparece."""
    q = db.query(Memoria).filter(Memoria.estado == EstadoMemoria.BORRADOR)
    if excluir_memoria_id is not None:
        q = q.filter(Memoria.id != excluir_memoria_id)
    borradores = q.all()
    mapa: Dict[Tuple[str, int], str] = {}
    for m in borradores:
        try:
            data = json.loads(m.snapshot_json)
            renglones = data.get("renglones", [])
            for r in renglones:
                if r.get("incluido", True):
                    k = (str(r.get("ref_tipo")), int(r.get("ref_id")))
                    if k not in mapa:
                        mapa[k] = f"En borrador Memoria #{m.numero}"
        except Exception:
            continue
    return mapa


def acumulados_anteriores(db: Session, obra_id: int, numero: int) -> Tuple[Decimal, Decimal]:
    """Suma total_memoria y transferencias de memorias cerradas de la misma obra con numero menor."""
    cerradas = (
        db.query(Memoria)
        .filter(
            Memoria.obra_id == obra_id,
            Memoria.estado == EstadoMemoria.CERRADA,
            Memoria.numero < numero,
        )
        .all()
    )
    gastado_ant = Decimal("0.00")
    transf_ant = Decimal("0.00")
    for m in cerradas:
        try:
            data = json.loads(m.snapshot_json)
            totales = data.get("totales", {})
            gastado_ant += Decimal(str(totales.get("total_memoria", "0.00")))
            transf_ant += Decimal(str(totales.get("transferencias", "0.00")))
        except Exception:
            continue
    return money(gastado_ant), money(transf_ant)


def sugerir_numero(db: Session, obra_id: int) -> int:
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    previa = obra.numero_ultima_memoria_previa if obra else 0
    max_num = db.query(func.max(Memoria.numero)).filter(Memoria.obra_id == obra_id).scalar()
    ultimo_sistema = max_num or 0
    return max(previa, ultimo_sistema) + 1


def sugerir_folio_arquitecto(db: Session) -> str:
    conf = db.query(Configuracion).filter(Configuracion.clave == "ultimo_folio_factura_arquitecto").first()
    ultimo_folio = 0
    if conf and conf.valor:
        try:
            ultimo_folio = int(conf.valor.strip())
        except ValueError:
            ultimo_folio = 0
    return str(ultimo_folio + 1)


def formatear_comprobante_gasto(g: Gasto) -> str:
    raw = (g.comprobante or "").strip()
    prefix = (getattr(g, "tipo_comprobante", None) or ("FACTURA" if g.origen == OrigenGasto.XML else "NOTA")).upper().strip()
    if not raw:
        return prefix
    if raw.upper().startswith(prefix):
        return raw.upper()
    return f"{prefix} {raw}".upper()


def generar_preview(
    db: Session,
    obra_id: int,
    fecha_inicio,
    fecha_fin,
    fecha_emision: Optional[date] = None,
    ciudad: Optional[str] = "Zapopan, Jalisco",
    gastos_extra_ids: Optional[List[int]] = None,
    rayas_extra_ids: Optional[List[int]] = None,
    numero: Optional[int] = None,
    porcentaje_honorarios: Optional[Decimal] = None,
    seleccion: Optional[List[Any]] = None,
) -> PreviewOut:
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    num_sugerido = sugerir_numero(db, obra_id)
    num_efectivo = numero if numero is not None else num_sugerido
    pct_efectivo = porcentaje_honorarios if porcentaje_honorarios is not None else obra.porcentaje_honorarios
    folio_sugerido = sugerir_folio_arquitecto(db)
    mapa_incluidos = obtener_mapa_incluidos_en_cerradas(db)
    mapa_borradores = obtener_mapa_incluidos_en_borradores(db)
    mapa_seleccion = {(s.ref_tipo, s.ref_id): s.incluido for s in seleccion} if seleccion is not None else None

    renglones: List[RenglonMemoria] = []
    vistos_gastos = set()
    vistos_rayas = set()

    def resolver_incluido(ref_tipo: str, ref_id: int, ya_inc: Optional[str]) -> bool:
        # Los renglones que ya pertenecen a una memoria cerrada NUNCA pueden incluirse
        if ya_inc:
            return False
        if mapa_seleccion is not None and (ref_tipo, ref_id) in mapa_seleccion:
            return bool(mapa_seleccion[(ref_tipo, ref_id)])
        return True

    # 1. Gastos de la obra en el rango de fechas
    gastos_obra = (
        db.query(Gasto)
        .filter(Gasto.obra_id == obra_id, Gasto.fecha >= fecha_inicio, Gasto.fecha <= fecha_fin)
        .order_by(Gasto.fecha.asc(), Gasto.id.asc())
        .all()
    )
    for g in gastos_obra:
        vistos_gastos.add(g.id)
        cat = "transferencia" if g.metodo_pago == MetodoPago.TRANSFERENCIA else "efectivo"
        prov = g.proveedor.nombre_memoria if g.proveedor else ""
        ya_inc = mapa_incluidos.get(("gasto", g.id))
        en_otro = mapa_borradores.get(("gasto", g.id))
        inc = resolver_incluido("gasto", g.id, ya_inc)
        tipo_c = getattr(g, "tipo_comprobante", None) or ("FACTURA" if g.origen == OrigenGasto.XML else "NOTA")
        comp = formatear_comprobante_gasto(g)
        renglones.append(
            RenglonMemoria(
                ref_tipo="gasto",
                ref_id=g.id,
                categoria=cat,
                incluido=inc,
                fecha=g.fecha,
                proveedor=prov,
                concepto=g.concepto_resumido,
                comprobante=comp,
                tipo_comprobante=tipo_c,
                importe=g.importe,
                es_externo=False,
                obra_origen=None,
                ya_incluido_en=ya_inc,
                en_otro_borrador=en_otro,
            )
        )

    # 2. Gastos extra solicitados
    if gastos_extra_ids:
        gastos_extra = db.query(Gasto).filter(Gasto.id.in_(gastos_extra_ids)).all()
        for g in gastos_extra:
            if g.id in vistos_gastos:
                continue
            vistos_gastos.add(g.id)
            cat = "transferencia" if g.metodo_pago == MetodoPago.TRANSFERENCIA else "efectivo"
            prov = g.proveedor.nombre_memoria if g.proveedor else ""
            es_ext = g.obra_id != obra_id
            ya_inc = mapa_incluidos.get(("gasto", g.id))
            en_otro = mapa_borradores.get(("gasto", g.id))
            inc = resolver_incluido("gasto", g.id, ya_inc)
            tipo_c = getattr(g, "tipo_comprobante", None) or ("FACTURA" if g.origen == OrigenGasto.XML else "NOTA")
            comp = formatear_comprobante_gasto(g)
            renglones.append(
                RenglonMemoria(
                    ref_tipo="gasto",
                    ref_id=g.id,
                    categoria=cat,
                    incluido=inc,
                    fecha=g.fecha,
                    proveedor=prov,
                    concepto=g.concepto_resumido,
                    comprobante=comp,
                    tipo_comprobante=tipo_c,
                    importe=g.importe,
                    es_externo=es_ext,
                    obra_origen=g.obra.nombre if es_ext and g.obra else None,
                    ya_incluido_en=ya_inc,
                    en_otro_borrador=en_otro,
                )
            )

    # 3. Rayas de la obra en el rango de fechas (por fecha_fin)
    rayas_obra = (
        db.query(PagoRaya)
        .filter(PagoRaya.obra_id == obra_id, PagoRaya.fecha_fin >= fecha_inicio, PagoRaya.fecha_fin <= fecha_fin)
        .order_by(PagoRaya.fecha_fin.asc(), PagoRaya.id.asc())
        .all()
    )
    for r in rayas_obra:
        vistos_rayas.add(r.id)
        ya_inc = mapa_incluidos.get(("raya", r.id))
        en_otro = mapa_borradores.get(("raya", r.id))
        inc = resolver_incluido("raya", r.id, ya_inc)
        renglones.append(
            RenglonMemoria(
                ref_tipo="raya",
                ref_id=r.id,
                categoria="raya",
                incluido=inc,
                fecha=r.fecha_fin,
                fecha_inicio=r.fecha_inicio,
                fecha_fin=r.fecha_fin,
                proveedor=r.trabajador.nombre if r.trabajador else "",
                concepto=f"Raya semana {r.semana_numero} ({r.trabajador.oficio if r.trabajador else ''})".strip(),
                comprobante=f"Semana {r.semana_numero}",
                importe=r.importe,
                es_externo=False,
                obra_origen=None,
                ya_incluido_en=ya_inc,
                en_otro_borrador=en_otro,
                oficio=r.trabajador.oficio if r.trabajador else None,
                semana_numero=r.semana_numero,
                tipo_raya=r.tipo,
                cantidad=r.cantidad,
                tarifa=r.tarifa,
            )
        )

    # Rayas extra solicitadas (de otra obra o fuera de rango)
    if rayas_extra_ids:
        rayas_extra = db.query(PagoRaya).filter(PagoRaya.id.in_(rayas_extra_ids)).all()
        for r in rayas_extra:
            if r.id in vistos_rayas:
                continue
            vistos_rayas.add(r.id)
            es_ext = r.obra_id != obra_id
            ya_inc = mapa_incluidos.get(("raya", r.id))
            en_otro = mapa_borradores.get(("raya", r.id))
            inc = resolver_incluido("raya", r.id, ya_inc)
            renglones.append(
                RenglonMemoria(
                    ref_tipo="raya",
                    ref_id=r.id,
                    categoria="raya",
                    incluido=inc,
                    fecha=r.fecha_fin,
                    fecha_inicio=r.fecha_inicio,
                    fecha_fin=r.fecha_fin,
                    proveedor=r.trabajador.nombre if r.trabajador else "",
                    concepto=f"Raya semana {r.semana_numero} ({r.trabajador.oficio if r.trabajador else ''})".strip(),
                    comprobante=f"Semana {r.semana_numero}",
                    importe=r.importe,
                    es_externo=es_ext,
                    obra_origen=r.obra.nombre if es_ext and r.obra else None,
                    ya_incluido_en=ya_inc,
                    en_otro_borrador=en_otro,
                    oficio=r.trabajador.oficio if r.trabajador else None,
                    semana_numero=r.semana_numero,
                    tipo_raya=r.tipo,
                    cantidad=r.cantidad,
                    tarifa=r.tarifa,
                )
            )

    # Rayas de semanas que empiezan dentro del periodo pero terminan fuera
    rayas_post_query = (
        db.query(PagoRaya)
        .filter(
            PagoRaya.obra_id == obra_id,
            PagoRaya.fecha_inicio <= fecha_fin,
            PagoRaya.fecha_fin > fecha_fin,
        )
        .order_by(PagoRaya.fecha_fin.asc(), PagoRaya.id.asc())
        .all()
    )
    rayas_posteriores: List[RenglonMemoria] = []
    for r in rayas_post_query:
        if r.id in vistos_rayas:
            continue
        ya_inc = mapa_incluidos.get(("raya", r.id))
        en_otro = mapa_borradores.get(("raya", r.id))
        rayas_posteriores.append(
            RenglonMemoria(
                ref_tipo="raya",
                ref_id=r.id,
                categoria="raya",
                incluido=False,
                fecha=r.fecha_fin,
                fecha_inicio=r.fecha_inicio,
                fecha_fin=r.fecha_fin,
                proveedor=r.trabajador.nombre if r.trabajador else "",
                concepto=f"Raya semana {r.semana_numero} ({r.trabajador.oficio if r.trabajador else ''})".strip(),
                comprobante=f"Semana {r.semana_numero}",
                importe=r.importe,
                es_externo=False,
                obra_origen=None,
                ya_incluido_en=ya_inc,
                en_otro_borrador=en_otro,
                oficio=r.trabajador.oficio if r.trabajador else None,
                semana_numero=r.semana_numero,
                tipo_raya=r.tipo,
                cantidad=r.cantidad,
                tarifa=r.tarifa,
            )
        )

    # 4. Anticipos de la obra en el rango de fechas
    anticipos_obra = (
        db.query(Anticipo)
        .filter(Anticipo.obra_id == obra_id, Anticipo.fecha >= fecha_inicio, Anticipo.fecha <= fecha_fin)
        .order_by(Anticipo.fecha.asc(), Anticipo.id.asc())
        .all()
    )
    for a in anticipos_obra:
        ya_inc = mapa_incluidos.get(("anticipo", a.id))
        en_otro = mapa_borradores.get(("anticipo", a.id))
        inc = resolver_incluido("anticipo", a.id, ya_inc)
        renglones.append(
            RenglonMemoria(
                ref_tipo="anticipo",
                ref_id=a.id,
                categoria="anticipo",
                incluido=inc,
                fecha=a.fecha,
                proveedor="",
                concepto="Anticipo",
                comprobante=a.comprobante or "",
                importe=a.importe,
                es_externo=False,
                obra_origen=None,
                ya_incluido_en=ya_inc,
                en_otro_borrador=en_otro,
            )
        )

    # Ordenar renglones por fecha y luego categoría
    cat_order = {"transferencia": 0, "efectivo": 1, "raya": 2, "anticipo": 3}
    renglones.sort(key=lambda item: (item.fecha, cat_order.get(item.categoria, 9), item.ref_id))

    # Cálculo de totales
    transf_list = [r.importe for r in renglones if r.incluido and r.categoria == "transferencia"]
    efec_list = [r.importe for r in renglones if r.incluido and r.categoria == "efectivo"]
    rayas_list = [r.importe for r in renglones if r.incluido and r.categoria == "raya"]
    anticipos_list = [r.importe for r in renglones if r.incluido and r.categoria == "anticipo"]

    gastado_ant, transf_ant = acumulados_anteriores(db, obra_id, num_efectivo)
    totales = calcular_memoria(
        sumar(transf_list),
        sumar(efec_list),
        sumar(rayas_list),
        pct_efectivo,
        anticipos=sumar(anticipos_list),
        saldo_inicial_memorias_anteriores=obra.saldo_inicial_memorias_anteriores,
        saldo_inicial_transferencias=obra.saldo_inicial_transferencias,
        saldo_inicial_efectivo=obra.saldo_inicial_efectivo,
        saldo_inicial_rayas=obra.saldo_inicial_rayas,
        gastado_memorias_anteriores=gastado_ant,
        transferencias_memorias_anteriores=transf_ant,
    )

    total_txt = numero_a_letras_mxn(totales.total_memoria)
    factura_txt = numero_a_letras_mxn(totales.importe_factura)
    gastado_txt = numero_a_letras_mxn(totales.gastado_a_la_fecha)

    tot_dict = totales.to_json()
    tot_dict["importe_factura_texto"] = factura_txt
    tot_dict["gastado_a_la_fecha_texto"] = gastado_txt

    return PreviewOut(
        obra_id=obra_id,
        numero_sugerido=num_efectivo,
        folio_sugerido=folio_sugerido,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        fecha_emision=fecha_emision or date.today(),
        ciudad=ciudad or "Zapopan, Jalisco",
        porcentaje_honorarios=pct_efectivo,
        renglones=renglones,
        anticipos=[r for r in renglones if r.ref_tipo == "anticipo"],
        rayas_posteriores=rayas_posteriores,
        totales=tot_dict,
        total_texto=total_txt,
        importe_factura_texto=factura_txt,
        gastado_a_la_fecha_texto=gastado_txt,
    )



def guardar_memoria(
    db: Session,
    data: MemoriaGuardar,
    memoria_id: Optional[int] = None,
) -> Memoria:
    obra = db.query(Obra).filter(Obra.id == data.obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    if memoria_id is not None:
        memoria = db.query(Memoria).filter(Memoria.id == memoria_id).first()
        if not memoria:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memoria no encontrada.")
        if memoria.estado == EstadoMemoria.CERRADA:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede modificar una memoria cerrada.",
            )
        numero = data.numero if data.numero is not None else memoria.numero
        if numero != memoria.numero:
            existe_num = (
                db.query(Memoria)
                .filter(Memoria.obra_id == obra.id, Memoria.numero == numero, Memoria.id != memoria.id)
                .first()
            )
            if existe_num:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe una memoria con el número {numero} para esta obra.",
                )
    else:
        numero = data.numero if data.numero is not None else sugerir_numero(db, obra.id)
        existe_num = db.query(Memoria).filter(Memoria.obra_id == obra.id, Memoria.numero == numero).first()
        if existe_num:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una memoria con el número {numero} para esta obra.",
            )
        memoria = Memoria(obra_id=obra.id, numero=numero)
        db.add(memoria)

    # Validar duplicados de renglones en la solicitud
    claves_renglones = set()
    for r in data.renglones:
        k = (r.ref_tipo, r.ref_id)
        if k in claves_renglones:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El renglón {r.ref_tipo} id={r.ref_id} está duplicado en la solicitud.",
            )
        claves_renglones.add(k)

    porcentaje = data.porcentaje_honorarios if data.porcentaje_honorarios is not None else obra.porcentaje_honorarios
    mapa_incluidos = obtener_mapa_incluidos_en_cerradas(db, excluir_memoria_id=memoria.id)
    mapa_borradores = obtener_mapa_incluidos_en_borradores(db, excluir_memoria_id=memoria.id)

    # Validar que ningún renglón marcado como incluido pertenezca a una memoria cerrada
    conflictos_cerradas = []
    for r in data.renglones:
        if r.incluido:
            k = (str(r.ref_tipo), int(r.ref_id))
            if k in mapa_incluidos:
                conflictos_cerradas.append(f"{r.ref_tipo.capitalize()} #{r.ref_id} ({mapa_incluidos[k]})")

    if conflictos_cerradas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pueden incluir renglones que ya pertenecen a una memoria cerrada: {', '.join(conflictos_cerradas)}",
        )

    renglones_finales: List[RenglonMemoria] = []

    for r_edit in data.renglones:
        if r_edit.ref_tipo == "gasto":
            g = db.query(Gasto).filter(Gasto.id == r_edit.ref_id).first()
            if not g:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"No se encontró el gasto con id {r_edit.ref_id}.",
                )
            cat = "transferencia" if g.metodo_pago == MetodoPago.TRANSFERENCIA else "efectivo"
            prov_def = g.proveedor.nombre_memoria if g.proveedor else ""
            prov = r_edit.proveedor if r_edit.proveedor is not None else prov_def
            conc = r_edit.concepto if r_edit.concepto is not None else g.concepto_resumido
            comp_def = formatear_comprobante_gasto(g)
            comp = r_edit.comprobante if r_edit.comprobante is not None else comp_def
            tipo_c = getattr(g, "tipo_comprobante", None) or ("FACTURA" if g.origen == OrigenGasto.XML else "NOTA")
            imp = r_edit.importe if r_edit.importe is not None else g.importe
            es_ext = g.obra_id != obra.id
            renglones_finales.append(
                RenglonMemoria(
                    ref_tipo="gasto",
                    ref_id=g.id,
                    categoria=cat,
                    incluido=r_edit.incluido,
                    fecha=g.fecha,
                    proveedor=prov,
                    concepto=conc,
                    comprobante=comp,
                    tipo_comprobante=tipo_c,
                    importe=money(imp),
                    es_externo=es_ext,
                    obra_origen=g.obra.nombre if es_ext and g.obra else None,
                    ya_incluido_en=mapa_incluidos.get(("gasto", g.id)),
                    en_otro_borrador=mapa_borradores.get(("gasto", g.id)),
                )
            )
        elif r_edit.ref_tipo == "raya":
            raya = db.query(PagoRaya).filter(PagoRaya.id == r_edit.ref_id).first()
            if not raya:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"No se encontró el pago de raya con id {r_edit.ref_id}.",
                )
            es_ext = raya.obra_id != obra.id
            prov_def = raya.trabajador.nombre if raya.trabajador else ""
            prov = r_edit.proveedor if r_edit.proveedor is not None else prov_def
            conc_def = f"Raya semana {raya.semana_numero} ({raya.trabajador.oficio if raya.trabajador else ''})".strip()
            conc = r_edit.concepto if r_edit.concepto is not None else conc_def
            comp = r_edit.comprobante if r_edit.comprobante is not None else f"Semana {raya.semana_numero}"
            imp = r_edit.importe if r_edit.importe is not None else raya.importe
            f_ini = r_edit.fecha_inicio or raya.fecha_inicio
            f_fin = r_edit.fecha_fin or raya.fecha_fin
            sem_num = r_edit.semana_numero or raya.semana_numero
            t_raya = r_edit.tipo_raya or raya.tipo
            ofic = r_edit.oficio if r_edit.oficio is not None else (raya.trabajador.oficio if raya.trabajador else None)
            cant = r_edit.cantidad if r_edit.cantidad is not None else raya.cantidad
            tarif = r_edit.tarifa if r_edit.tarifa is not None else raya.tarifa
            renglones_finales.append(
                RenglonMemoria(
                    ref_tipo="raya",
                    ref_id=raya.id,
                    categoria="raya",
                    incluido=r_edit.incluido,
                    fecha=f_fin,
                    fecha_inicio=f_ini,
                    fecha_fin=f_fin,
                    proveedor=prov,
                    concepto=conc,
                    comprobante=comp,
                    importe=money(imp),
                    es_externo=es_ext,
                    obra_origen=raya.obra.nombre if es_ext and raya.obra else None,
                    ya_incluido_en=mapa_incluidos.get(("raya", raya.id)),
                    en_otro_borrador=mapa_borradores.get(("raya", raya.id)),
                    oficio=ofic,
                    semana_numero=sem_num,
                    tipo_raya=t_raya,
                    cantidad=cant,
                    tarifa=tarif,
                )
            )
        elif r_edit.ref_tipo == "anticipo":
            ant = db.query(Anticipo).filter(Anticipo.id == r_edit.ref_id).first()
            if not ant:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"No se encontró el anticipo con id {r_edit.ref_id}.",
                )
            if ant.obra_id != obra.id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"El anticipo {r_edit.ref_id} no pertenece a la obra {obra.nombre}.",
                )
            comp = r_edit.comprobante if r_edit.comprobante is not None else (ant.comprobante or "")
            conc = r_edit.concepto if r_edit.concepto is not None else "Anticipo"
            imp = r_edit.importe if r_edit.importe is not None else ant.importe
            renglones_finales.append(
                RenglonMemoria(
                    ref_tipo="anticipo",
                    ref_id=ant.id,
                    categoria="anticipo",
                    incluido=r_edit.incluido,
                    fecha=ant.fecha,
                    proveedor=r_edit.proveedor or "",
                    concepto=conc,
                    comprobante=comp,
                    importe=money(imp),
                    es_externo=False,
                    obra_origen=None,
                    ya_incluido_en=mapa_incluidos.get(("anticipo", ant.id)),
                    en_otro_borrador=mapa_borradores.get(("anticipo", ant.id)),
                )
            )

    # Totales
    transf_list = [r.importe for r in renglones_finales if r.incluido and r.categoria == "transferencia"]
    efec_list = [r.importe for r in renglones_finales if r.incluido and r.categoria == "efectivo"]
    rayas_list = [r.importe for r in renglones_finales if r.incluido and r.categoria == "raya"]
    anticipos_list = [r.importe for r in renglones_finales if r.incluido and r.categoria == "anticipo"]

    gastado_ant, transf_ant = acumulados_anteriores(db, obra.id, numero)
    totales = calcular_memoria(
        sumar(transf_list),
        sumar(efec_list),
        sumar(rayas_list),
        porcentaje,
        anticipos=sumar(anticipos_list),
        saldo_inicial_memorias_anteriores=obra.saldo_inicial_memorias_anteriores,
        saldo_inicial_transferencias=obra.saldo_inicial_transferencias,
        saldo_inicial_efectivo=obra.saldo_inicial_efectivo,
        saldo_inicial_rayas=obra.saldo_inicial_rayas,
        gastado_memorias_anteriores=gastado_ant,
        transferencias_memorias_anteriores=transf_ant,
    )
    total_txt = numero_a_letras_mxn(totales.total_memoria)

    snapshot: Dict[str, Any] = {
        "version": 1,
        "obra": {
            "id": obra.id,
            "nombre": obra.nombre,
            "ubicacion": obra.ubicacion,
            "propietario": obra.propietario,
        },
        "periodo": {
            "fecha_inicio": data.fecha_inicio.isoformat(),
            "fecha_fin": data.fecha_fin.isoformat(),
        },
        "numero": numero,
        "folio_factura_arquitecto": data.folio_factura_arquitecto,
        "fecha_emision": (data.fecha_emision or date.today()).isoformat(),
        "ciudad": data.ciudad or "Zapopan, Jalisco",
        "porcentaje_honorarios": str(porcentaje),
        "renglones": [r.model_dump(mode="json") for r in renglones_finales],
        "anticipos": [r.model_dump(mode="json") for r in renglones_finales if r.ref_tipo == "anticipo"],
        "totales": {
            **totales.to_json(),
            "importe_factura_texto": numero_a_letras_mxn(totales.importe_factura),
            "gastado_a_la_fecha_texto": numero_a_letras_mxn(totales.gastado_a_la_fecha),
        },
        "total_texto": total_txt,
        "importe_factura_texto": numero_a_letras_mxn(totales.importe_factura),
        "gastado_a_la_fecha_texto": numero_a_letras_mxn(totales.gastado_a_la_fecha),
    }

    memoria.numero = numero
    memoria.folio_factura_arquitecto = data.folio_factura_arquitecto
    memoria.fecha_inicio = data.fecha_inicio
    memoria.fecha_fin = data.fecha_fin
    memoria.fecha_emision = data.fecha_emision or date.today()
    memoria.ciudad = data.ciudad or "Zapopan, Jalisco"
    memoria.porcentaje_honorarios_usado = porcentaje
    memoria.snapshot_json = json.dumps(snapshot, ensure_ascii=False)
    memoria.total_texto = total_txt
    memoria.estado = EstadoMemoria.BORRADOR

    db.flush()
    return memoria


def cerrar_memoria(db: Session, memoria_id: int) -> Memoria:
    memoria = db.query(Memoria).filter(Memoria.id == memoria_id).first()
    if not memoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memoria no encontrada.")
    if memoria.estado == EstadoMemoria.CERRADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La memoria ya se encuentra cerrada.")

    try:
        snapshot = json.loads(memoria.snapshot_json)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al leer el snapshot de la memoria.",
        )

    renglones_data = snapshot.get("renglones", [])
    # Asegurar que todas las rayas tengan fecha_inicio y fecha_fin en el snapshot
    for r in renglones_data:
        if r.get("ref_tipo") == "raya" or r.get("categoria") == "raya":
            if not r.get("fecha_inicio") or not r.get("fecha_fin") or str(r.get("fecha_inicio")) == "None":
                pago = db.query(PagoRaya).filter(PagoRaya.id == r.get("ref_id")).first()
                if pago:
                    f_ini_str = pago.fecha_inicio.isoformat() if hasattr(pago.fecha_inicio, "isoformat") else str(pago.fecha_inicio)
                    f_fin_str = pago.fecha_fin.isoformat() if hasattr(pago.fecha_fin, "isoformat") else str(pago.fecha_fin)
                    r["fecha_inicio"] = f_ini_str
                    r["fecha_fin"] = f_fin_str
                    if not r.get("semana_numero"):
                        r["semana_numero"] = pago.semana_numero
                    if not r.get("tipo_raya"):
                        r["tipo_raya"] = pago.tipo.value if hasattr(pago.tipo, "value") else str(pago.tipo)
                    if not r.get("cantidad"):
                        r["cantidad"] = str(pago.cantidad)
                    if not r.get("tarifa"):
                        r["tarifa"] = str(pago.tarifa)

    incluidos = [r for r in renglones_data if r.get("incluido", True)]
    if not incluidos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se puede cerrar una memoria sin renglones incluidos.",
        )

    # Validar que ningún renglón incluido pertenezca a otra memoria cerrada
    mapa_cerradas = obtener_mapa_incluidos_en_cerradas(db, excluir_memoria_id=memoria.id)
    conflictos_cerradas = []
    for r in incluidos:
        k = (str(r.get("ref_tipo")), int(r.get("ref_id")))
        if k in mapa_cerradas:
            conflictos_cerradas.append(f"{str(r.get('ref_tipo')).capitalize()} #{r.get('ref_id')} ({mapa_cerradas[k]})")

    if conflictos_cerradas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pueden incluir renglones que ya pertenecen a una memoria cerrada: {', '.join(conflictos_cerradas)}",
        )

    # Recalcular totales con base ESTRICTA en los renglones congelados del snapshot
    transf_list = [r["importe"] for r in incluidos if r.get("categoria") == "transferencia"]
    efec_list = [r["importe"] for r in incluidos if r.get("categoria") == "efectivo"]
    rayas_list = [r["importe"] for r in incluidos if r.get("categoria") == "raya"]
    anticipos_list = [r["importe"] for r in incluidos if r.get("categoria") == "anticipo"]

    obra = memoria.obra
    pct = Decimal(str(snapshot.get("porcentaje_honorarios", memoria.porcentaje_honorarios_usado)))
    gastado_ant, transf_ant = acumulados_anteriores(db, memoria.obra_id, memoria.numero)

    totales = calcular_memoria(
        sumar(transf_list),
        sumar(efec_list),
        sumar(rayas_list),
        pct,
        anticipos=sumar(anticipos_list),
        saldo_inicial_memorias_anteriores=obra.saldo_inicial_memorias_anteriores if obra else Decimal("0.00"),
        saldo_inicial_transferencias=obra.saldo_inicial_transferencias if obra else Decimal("0.00"),
        saldo_inicial_efectivo=obra.saldo_inicial_efectivo if obra else Decimal("0.00"),
        saldo_inicial_rayas=obra.saldo_inicial_rayas if obra else Decimal("0.00"),
        gastado_memorias_anteriores=gastado_ant,
        transferencias_memorias_anteriores=transf_ant,
    )
    total_txt = numero_a_letras_mxn(totales.total_memoria)
    factura_txt = numero_a_letras_mxn(totales.importe_factura)
    gastado_txt = numero_a_letras_mxn(totales.gastado_a_la_fecha)

    tot_dict = totales.to_json()
    tot_dict["importe_factura_texto"] = factura_txt
    tot_dict["gastado_a_la_fecha_texto"] = gastado_txt

    ahora = datetime.now()
    snapshot["totales"] = tot_dict
    snapshot["total_texto"] = total_txt
    snapshot["importe_factura_texto"] = factura_txt
    snapshot["gastado_a_la_fecha_texto"] = gastado_txt
    snapshot["cerrada_at"] = ahora.isoformat()

    memoria.estado = EstadoMemoria.CERRADA
    memoria.cerrada_at = ahora
    memoria.snapshot_json = json.dumps(snapshot, ensure_ascii=False)
    memoria.total_texto = total_txt

    # Si la memoria tiene un folio numérico, actualizar configuracion "ultimo_folio_factura_arquitecto"
    if memoria.folio_factura_arquitecto:
        try:
            folio_int = int(str(memoria.folio_factura_arquitecto).strip())
            conf = db.query(Configuracion).filter(Configuracion.clave == "ultimo_folio_factura_arquitecto").first()
            if not conf:
                conf = Configuracion(clave="ultimo_folio_factura_arquitecto", valor=str(folio_int))
                db.add(conf)
            else:
                try:
                    actual = int(conf.valor.strip())
                except ValueError:
                    actual = 0
                conf.valor = str(max(actual, folio_int))
        except ValueError:
            pass

    db.flush()
    db.commit()

    # Generar respaldo automático tras el cierre de cada memoria
    try:
        from app.services.backup_service import crear_respaldo_seguro
        crear_respaldo_seguro(db, origen="cierre_memoria")
    except Exception as e:
        logger.error(f"Error generando respaldo automático tras cerrar memoria {memoria.id}: {e}")

    return memoria


def reabrir_memoria(db: Session, memoria_id: int) -> Memoria:
    """Reabre una memoria cerrada:
    - SOLO la última memoria cerrada de la obra puede reabrirse (para proteger los acumulados).
    - Vuelve a estado BORRADOR y libera sus renglones para edición.
    - El folio sugerido de factura del arquitecto regresa si fue el último registrado.
    - Genera un respaldo automático preventivo antes de reabrir.
    - Registra una entrada en la tabla y log de auditoría (fecha, acción, memoria, detalles).
    """
    memoria = db.query(Memoria).filter(Memoria.id == memoria_id).first()
    if not memoria:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memoria no encontrada.")
    if memoria.estado != EstadoMemoria.CERRADA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden reabrir memorias que se encuentren cerradas.",
        )

    # Validar que sea estrictamente la ÚLTIMA memoria cerrada de esta obra
    memoria_posterior = (
        db.query(Memoria)
        .filter(
            Memoria.obra_id == memoria.obra_id,
            Memoria.estado == EstadoMemoria.CERRADA,
            Memoria.numero > memoria.numero,
        )
        .order_by(Memoria.numero.desc())
        .first()
    )
    if memoria_posterior:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No se puede reabrir la Memoria #{memoria.numero} porque existen memorias cerradas posteriores "
                f"(Memoria #{memoria_posterior.numero}). Solo la última memoria cerrada puede reabrirse "
                f"para preservar la consistencia de los acumulados contables."
            ),
        )

    # 1. Respaldo automático preventivo antes de reabrir
    try:
        from app.services.backup_service import crear_respaldo_seguro
        zip_path, _ = crear_respaldo_seguro(db, origen="reapertura_memoria")
        logger.info(f"Respaldo preventivo automático generado antes de reabrir memoria #{memoria_id}: {zip_path}")
    except Exception as e:
        logger.error(f"Fallo al crear respaldo preventivo antes de reabrir memoria #{memoria_id}: {e}")

    # 2. Revertir folio sugerido si fue el último folio registrado en configuración
    folio_arquitecto = (memoria.folio_factura_arquitecto or "").strip()
    if folio_arquitecto:
        try:
            folio_int = int(folio_arquitecto)
            conf = db.query(Configuracion).filter(Configuracion.clave == "ultimo_folio_factura_arquitecto").first()
            if conf and conf.valor.strip():
                try:
                    conf_int = int(conf.valor.strip())
                except ValueError:
                    conf_int = 0

                if conf_int == folio_int:
                    # Encontrar el folio numérico más alto entre las demás memorias cerradas
                    otras_cerradas = (
                        db.query(Memoria)
                        .filter(Memoria.id != memoria.id, Memoria.estado == EstadoMemoria.CERRADA)
                        .all()
                    )
                    max_otro_folio = 0
                    for oc in otras_cerradas:
                        if oc.folio_factura_arquitecto:
                            try:
                                f_num = int(str(oc.folio_factura_arquitecto).strip())
                                if f_num > max_otro_folio:
                                    max_otro_folio = f_num
                            except ValueError:
                                pass

                    if max_otro_folio > 0:
                        conf.valor = str(max_otro_folio)
                    else:
                        conf.valor = str(max(0, folio_int - 1))
                    logger.info(f"Folio sugerido revertido en configuración de {folio_int} a {conf.valor}")
        except ValueError:
            pass

    # 3. Revertir estado a borrador y limpiar fecha de cierre
    memoria.estado = EstadoMemoria.BORRADOR
    memoria.cerrada_at = None

    # Limpiar cerrada_at del snapshot
    try:
        snapshot = json.loads(memoria.snapshot_json) if memoria.snapshot_json else {}
        snapshot.pop("cerrada_at", None)
        memoria.snapshot_json = json.dumps(snapshot, ensure_ascii=False)
    except Exception:
        pass

    # 4. Registro de auditoría (fecha, acción, memoria, detalles)
    ahora = datetime.now()
    obra = memoria.obra
    obra_nom = obra.nombre if obra else f"Obra #{memoria.obra_id}"
    detalles_audit = (
        f"Reapertura de Memoria #{memoria.numero} (Folio Factura: '{folio_arquitecto or 'Sin folio'}') "
        f"de la obra '{obra_nom}' (ID {memoria.obra_id}). Estado revertido a borrador."
    )
    reg_audit = RegistroAuditoria(
        fecha=ahora,
        accion="reapertura_memoria",
        memoria_id=memoria.id,
        obra_id=memoria.obra_id,
        detalles=detalles_audit,
    )
    db.add(reg_audit)
    logger.info(f"[AUDITORIA] {detalles_audit}")

    db.flush()
    db.commit()
    return memoria


def to_decimal(val: Any) -> Decimal:
    if val is None or val == "":
        return Decimal("0.00")
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0.00")


def memoria_a_out(memoria: Memoria) -> MemoriaOut:
    try:
        data = json.loads(memoria.snapshot_json)
    except Exception:
        data = {}

    totales = dict(data.get("totales", {}))
    renglones_raw = data.get("renglones", [])

    # Asegurar consistencia matemática de acumulados anteriores y totales
    transf_esta = to_decimal(totales.get("transferencias", "0.00"))
    tot_mem_esta = to_decimal(totales.get("total_memoria", "0.00"))

    if "transferencias_memorias_anteriores" not in totales or totales["transferencias_memorias_anteriores"] is None:
        acum_transf = to_decimal(totales.get("acumulado_transferencias", transf_esta))
        totales["transferencias_memorias_anteriores"] = str(money(acum_transf - transf_esta))

    transf_ant = to_decimal(totales["transferencias_memorias_anteriores"])
    totales["acumulado_transferencias"] = str(money(transf_ant + transf_esta))

    if "gastado_memorias_anteriores" not in totales or totales["gastado_memorias_anteriores"] is None:
        gastado_tot = to_decimal(totales.get("gastado_a_la_fecha", tot_mem_esta))
        totales["gastado_memorias_anteriores"] = str(money(gastado_tot - tot_mem_esta))

    gast_ant = to_decimal(totales["gastado_memorias_anteriores"])
    totales["gastado_a_la_fecha"] = str(money(gast_ant + tot_mem_esta))

    if "total_honorarios" not in totales or totales["total_honorarios"] is None:
        hon = to_decimal(totales.get("honorarios", "0.00"))
        iva = to_decimal(totales.get("iva", "0.00"))
        totales["total_honorarios"] = str(money(hon + iva))

    from sqlalchemy.orm import object_session
    s = object_session(memoria)
    healed = False
    for r_raw in renglones_raw:
        if (r_raw.get("ref_tipo") == "raya" or r_raw.get("categoria") == "raya") and (
            not r_raw.get("fecha_inicio") or not r_raw.get("fecha_fin") or str(r_raw.get("fecha_inicio")) == "None"
        ):
            if s:
                pago = s.query(PagoRaya).filter(PagoRaya.id == r_raw.get("ref_id")).first()
                if pago:
                    f_ini_str = pago.fecha_inicio.isoformat() if hasattr(pago.fecha_inicio, "isoformat") else str(pago.fecha_inicio)
                    f_fin_str = pago.fecha_fin.isoformat() if hasattr(pago.fecha_fin, "isoformat") else str(pago.fecha_fin)
                    r_raw["fecha_inicio"] = f_ini_str
                    r_raw["fecha_fin"] = f_fin_str
                    if not r_raw.get("semana_numero"):
                        r_raw["semana_numero"] = pago.semana_numero
                    if not r_raw.get("tipo_raya"):
                        r_raw["tipo_raya"] = pago.tipo.value if hasattr(pago.tipo, "value") else str(pago.tipo)
                    if not r_raw.get("cantidad"):
                        r_raw["cantidad"] = str(pago.cantidad)
                    if not r_raw.get("tarifa"):
                        r_raw["tarifa"] = str(pago.tarifa)
                    healed = True

    if healed and s:
        data["renglones"] = renglones_raw
        memoria.snapshot_json = json.dumps(data, ensure_ascii=False)
        s.flush()

    renglones = [RenglonMemoria(**r) for r in renglones_raw]
    anticipos = [r for r in renglones if r.ref_tipo == "anticipo"]

    f_emision_raw = data.get("fecha_emision")
    f_emision = date.fromisoformat(f_emision_raw) if f_emision_raw else memoria.fecha_emision
    ciudad = data.get("ciudad") or memoria.ciudad or "Zapopan, Jalisco"
    importe_fac_txt = (
        data.get("importe_factura_texto")
        or totales.get("importe_factura_texto")
        or (numero_a_letras_mxn(Decimal(totales["importe_factura"])) if "importe_factura" in totales else "")
        or ""
    )
    gastado_txt = (
        data.get("gastado_a_la_fecha_texto")
        or totales.get("gastado_a_la_fecha_texto")
        or (numero_a_letras_mxn(Decimal(totales["gastado_a_la_fecha"])) if "gastado_a_la_fecha" in totales else "")
        or ""
    )

    totales["importe_factura_texto"] = importe_fac_txt
    totales["gastado_a_la_fecha_texto"] = gastado_txt

    return MemoriaOut(
        id=memoria.id,
        obra_id=memoria.obra_id,
        numero=memoria.numero,
        folio_factura_arquitecto=memoria.folio_factura_arquitecto,
        fecha_inicio=memoria.fecha_inicio,
        fecha_fin=memoria.fecha_fin,
        fecha_emision=f_emision,
        ciudad=ciudad,
        porcentaje_honorarios_usado=memoria.porcentaje_honorarios_usado,
        estado=memoria.estado,
        total_texto=memoria.total_texto or data.get("total_texto", ""),
        total_memoria=totales.get("total_memoria"),
        importe_factura_texto=importe_fac_txt,
        gastado_a_la_fecha_texto=gastado_txt,
        cerrada_at=memoria.cerrada_at,
        renglones=renglones,
        anticipos=anticipos,
        totales=totales,
    )


def memoria_a_resumen(memoria: Memoria) -> MemoriaResumenOut:
    try:
        data = json.loads(memoria.snapshot_json)
        totales = data.get("totales", {})
        total_mem = totales.get("total_memoria")
        f_emision_raw = data.get("fecha_emision")
        f_emision = date.fromisoformat(f_emision_raw) if f_emision_raw else memoria.fecha_emision
        ciudad = data.get("ciudad") or memoria.ciudad or "Zapopan, Jalisco"
        importe_fac_txt = data.get("importe_factura_texto") or totales.get("importe_factura_texto") or (
            numero_a_letras_mxn(Decimal(totales["importe_factura"])) if "importe_factura" in totales else None
        )
        gastado_txt = data.get("gastado_a_la_fecha_texto") or totales.get("gastado_a_la_fecha_texto") or (
            numero_a_letras_mxn(Decimal(totales["gastado_a_la_fecha"])) if "gastado_a_la_fecha" in totales else None
        )
    except Exception:
        total_mem = None
        f_emision = memoria.fecha_emision
        ciudad = memoria.ciudad or "Zapopan, Jalisco"
        importe_fac_txt = None
        gastado_txt = None

    return MemoriaResumenOut(
        id=memoria.id,
        obra_id=memoria.obra_id,
        numero=memoria.numero,
        folio_factura_arquitecto=memoria.folio_factura_arquitecto,
        fecha_inicio=memoria.fecha_inicio,
        fecha_fin=memoria.fecha_fin,
        fecha_emision=f_emision,
        ciudad=ciudad,
        porcentaje_honorarios_usado=memoria.porcentaje_honorarios_usado,
        estado=memoria.estado,
        total_texto=memoria.total_texto,
        total_memoria=total_mem,
        importe_factura_texto=importe_fac_txt,
        gastado_a_la_fecha_texto=gastado_txt,
        cerrada_at=memoria.cerrada_at,
    )


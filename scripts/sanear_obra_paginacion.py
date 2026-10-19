"""Script para sanear los datos de prueba de la obra 'PRUEBA PAGINACIÓN' (Obra ID 2).

Opciones:
1. --particionar (por defecto):
   - Memoria 01: Quincena 1 (01/10/2026 al 15/10/2026, 41 renglones: 29 gastos, 10 rayas, 2 anticipos).
   - Memoria 02: Quincena 2 (16/10/2026 al 31/10/2026, 26 renglones: 16 gastos, 10 rayas, 0 anticipos).
   - Recalcula snapshots con fórmula única y acumulados consistentes (X, Y, X+Y).
2. --eliminar-memoria-2:
   - Elimina únicamente la Memoria 02 (que contenía duplicados de la 01).
   - Deja la Memoria 01 con sus 67 renglones lista para probar el asistente (donde ningún renglón de la 01 podrá ser incluido en la 02).
"""
import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models import EstadoMemoria, Gasto, Memoria, Obra, PagoRaya, Anticipo
from app.services.memoria_calculo import calcular_memoria, sumar
from app.services.number_to_words import numero_a_letras_mxn
from app.types import money


def sanear_particionar(db):
    obra = db.query(Obra).filter(Obra.nombre.like("%PAGINACI%")).first()
    if not obra:
        print("No se encontró la obra 'PRUEBA PAGINACIÓN'.")
        return

    mems = db.query(Memoria).filter(Memoria.obra_id == obra.id).order_by(Memoria.numero.asc()).all()
    if len(mems) < 2:
        print(f"La obra tiene {len(mems)} memorias. Se requieren al menos 2 para particionar.")
        return

    m1, m2 = mems[0], mems[1]

    # Cargar todos los renglones de la obra
    gastos = db.query(Gasto).filter(Gasto.obra_id == obra.id).order_by(Gasto.fecha.asc()).all()
    rayas = db.query(PagoRaya).filter(PagoRaya.obra_id == obra.id).order_by(PagoRaya.fecha_fin.asc()).all()
    anticipos = db.query(Anticipo).filter(Anticipo.obra_id == obra.id).order_by(Anticipo.fecha.asc()).all()

    corte_q1 = date(2026, 10, 15)

    # Renglones Quincena 1 (<= 15/10/2026)
    r1 = []
    for g in gastos:
        if g.fecha <= corte_q1:
            r1.append({
                "ref_tipo": "gasto",
                "ref_id": g.id,
                "categoria": "transferencia" if g.metodo_pago.value == "transferencia" else "efectivo",
                "incluido": True,
                "fecha": g.fecha.isoformat(),
                "proveedor": g.proveedor.nombre_memoria if g.proveedor else "",
                "concepto": g.concepto_resumido,
                "comprobante": g.comprobante or "",
                "importe": str(g.importe),
                "tipo_comprobante": getattr(g, "tipo_comprobante", "NOTA"),
            })

    for ray in rayas:
        if ray.fecha_fin <= corte_q1:
            r1.append({
                "ref_tipo": "raya",
                "ref_id": ray.id,
                "categoria": "raya",
                "incluido": True,
                "fecha": ray.fecha_fin.isoformat(),
                "fecha_inicio": ray.fecha_inicio.isoformat() if ray.fecha_inicio else None,
                "fecha_fin": ray.fecha_fin.isoformat() if ray.fecha_fin else None,
                "proveedor": ray.trabajador.nombre if ray.trabajador else "",
                "oficio": ray.trabajador.oficio if ray.trabajador else "",
                "concepto": f"Raya semana {ray.semana_numero}",
                "comprobante": f"Semana {ray.semana_numero}",
                "tipo_raya": ray.tipo.value if hasattr(ray.tipo, "value") else str(ray.tipo),
                "cantidad": str(ray.cantidad),
                "tarifa": str(ray.tarifa),
                "semana_numero": ray.semana_numero,
                "importe": str(ray.importe),
            })

    for a in anticipos:
        if a.fecha <= corte_q1:
            r1.append({
                "ref_tipo": "anticipo",
                "ref_id": a.id,
                "categoria": "anticipo",
                "incluido": True,
                "fecha": a.fecha.isoformat(),
                "proveedor": obra.propietario,
                "concepto": "Anticipo",
                "comprobante": a.comprobante or "",
                "importe": str(a.importe),
            })

    # Renglones Quincena 2 (> 15/10/2026)
    r2 = []
    for g in gastos:
        if g.fecha > corte_q1:
            r2.append({
                "ref_tipo": "gasto",
                "ref_id": g.id,
                "categoria": "transferencia" if g.metodo_pago.value == "transferencia" else "efectivo",
                "incluido": True,
                "fecha": g.fecha.isoformat(),
                "proveedor": g.proveedor.nombre_memoria if g.proveedor else "",
                "concepto": g.concepto_resumido,
                "comprobante": g.comprobante or "",
                "importe": str(g.importe),
                "tipo_comprobante": getattr(g, "tipo_comprobante", "NOTA"),
            })

    for ray in rayas:
        if ray.fecha_fin > corte_q1:
            r2.append({
                "ref_tipo": "raya",
                "ref_id": ray.id,
                "categoria": "raya",
                "incluido": True,
                "fecha": ray.fecha_fin.isoformat(),
                "fecha_inicio": ray.fecha_inicio.isoformat() if ray.fecha_inicio else None,
                "fecha_fin": ray.fecha_fin.isoformat() if ray.fecha_fin else None,
                "proveedor": ray.trabajador.nombre if ray.trabajador else "",
                "oficio": ray.trabajador.oficio if ray.trabajador else "",
                "concepto": f"Raya semana {ray.semana_numero}",
                "comprobante": f"Semana {ray.semana_numero}",
                "tipo_raya": ray.tipo.value if hasattr(ray.tipo, "value") else str(ray.tipo),
                "cantidad": str(ray.cantidad),
                "tarifa": str(ray.tarifa),
                "semana_numero": ray.semana_numero,
                "importe": str(ray.importe),
            })

    for a in anticipos:
        if a.fecha > corte_q1:
            r2.append({
                "ref_tipo": "anticipo",
                "ref_id": a.id,
                "categoria": "anticipo",
                "incluido": True,
                "fecha": a.fecha.isoformat(),
                "proveedor": obra.propietario,
                "concepto": "Anticipo",
                "comprobante": a.comprobante or "",
                "importe": str(a.importe),
            })

    # Calcular Memoria 01
    t1_transf = [r["importe"] for r in r1 if r["categoria"] == "transferencia"]
    t1_efec = [r["importe"] for r in r1 if r["categoria"] == "efectivo"]
    t1_rayas = [r["importe"] for r in r1 if r["categoria"] == "raya"]
    t1_ant = [r["importe"] for r in r1 if r["categoria"] == "anticipo"]

    tot1 = calcular_memoria(
        sumar(t1_transf),
        sumar(t1_efec),
        sumar(t1_rayas),
        obra.porcentaje_honorarios,
        anticipos=sumar(t1_ant),
    )

    snap1 = {
        "version": 1,
        "obra": {"id": obra.id, "nombre": obra.nombre, "ubicacion": obra.ubicacion, "propietario": obra.propietario},
        "periodo": {"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-15"},
        "numero": 1,
        "folio_factura_arquitecto": m1.folio_factura_arquitecto or "101",
        "fecha_emision": "2026-10-15",
        "ciudad": m1.ciudad or "Zapopan, Jalisco",
        "porcentaje_honorarios": str(obra.porcentaje_honorarios),
        "renglones": r1,
        "anticipos": [r for r in r1 if r["categoria"] == "anticipo"],
        "totales": tot1.to_json(),
        "total_texto": numero_a_letras_mxn(tot1.total_memoria),
        "importe_factura_texto": numero_a_letras_mxn(tot1.importe_factura),
        "gastado_a_la_fecha_texto": numero_a_letras_mxn(tot1.gastado_a_la_fecha),
    }

    m1.fecha_inicio = date(2026, 10, 1)
    m1.fecha_fin = date(2026, 10, 15)
    m1.fecha_emision = date(2026, 10, 15)
    m1.snapshot_json = json.dumps(snap1, ensure_ascii=False)
    m1.total_texto = numero_a_letras_mxn(tot1.total_memoria)
    m1.estado = EstadoMemoria.CERRADA

    # Calcular Memoria 02 con base en los acumulados de Memoria 01
    t2_transf = [r["importe"] for r in r2 if r["categoria"] == "transferencia"]
    t2_efec = [r["importe"] for r in r2 if r["categoria"] == "efectivo"]
    t2_rayas = [r["importe"] for r in r2 if r["categoria"] == "raya"]
    t2_ant = [r["importe"] for r in r2 if r["categoria"] == "anticipo"]

    tot2 = calcular_memoria(
        sumar(t2_transf),
        sumar(t2_efec),
        sumar(t2_rayas),
        obra.porcentaje_honorarios,
        anticipos=sumar(t2_ant),
        gastado_memorias_anteriores=tot1.total_memoria,
        transferencias_memorias_anteriores=tot1.transferencias,
    )

    snap2 = {
        "version": 1,
        "obra": {"id": obra.id, "nombre": obra.nombre, "ubicacion": obra.ubicacion, "propietario": obra.propietario},
        "periodo": {"fecha_inicio": "2026-10-16", "fecha_fin": "2026-10-31"},
        "numero": 2,
        "folio_factura_arquitecto": m2.folio_factura_arquitecto or "102",
        "fecha_emision": "2026-10-31",
        "ciudad": m2.ciudad or "Zapopan, Jalisco",
        "porcentaje_honorarios": str(obra.porcentaje_honorarios),
        "renglones": r2,
        "anticipos": [r for r in r2 if r["categoria"] == "anticipo"],
        "totales": tot2.to_json(),
        "total_texto": numero_a_letras_mxn(tot2.total_memoria),
        "importe_factura_texto": numero_a_letras_mxn(tot2.importe_factura),
        "gastado_a_la_fecha_texto": numero_a_letras_mxn(tot2.gastado_a_la_fecha),
    }

    m2.fecha_inicio = date(2026, 10, 16)
    m2.fecha_fin = date(2026, 10, 31)
    m2.fecha_emision = date(2026, 10, 31)
    m2.snapshot_json = json.dumps(snap2, ensure_ascii=False)
    m2.total_texto = numero_a_letras_mxn(tot2.total_memoria)
    m2.estado = EstadoMemoria.CERRADA

    db.commit()

    print("✓ Saneamiento completado con éxito:")
    print(f"  - Memoria 01 (ID {m1.id}): {len(r1)} renglones (Periodo 01/10/2026 - 15/10/2026)")
    print(f"    Transf: ${tot1.transferencias:,.2f} | Total: ${tot1.total_memoria:,.2f}")
    print(f"  - Memoria 02 (ID {m2.id}): {len(r2)} renglones (Periodo 16/10/2026 - 31/10/2026)")
    print(f"    Transf Ant: ${tot2.transferencias_memorias_anteriores:,.2f} + De esta: ${tot2.transferencias:,.2f} = Total Transf: ${tot2.acumulado_transferencias:,.2f}")
    print(f"    Gastado Ant: ${tot2.gastado_memorias_anteriores:,.2f} + De esta: ${tot2.total_memoria:,.2f} = Gastado a la fecha: ${tot2.gastado_a_la_fecha:,.2f}")
    print("  - Intersección de renglones entre Memoria 01 y 02: 0 (Cero duplicados)")


def sanear_eliminar_memoria_2(db):
    obra = db.query(Obra).filter(Obra.nombre.like("%PAGINACI%")).first()
    if not obra:
        print("No se encontró la obra 'PRUEBA PAGINACIÓN'.")
        return

    m2 = db.query(Memoria).filter(Memoria.obra_id == obra.id, Memoria.numero == 2).first()
    if m2:
        db.delete(m2)
        db.commit()
        print(f"✓ Memoria 02 (ID {m2.id}) eliminada. Ahora la obra tiene únicamente Memoria 01.")
    else:
        print("No se encontró la Memoria 02 para esta obra.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eliminar-memoria-2", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.eliminar_memoria_2:
            sanear_eliminar_memoria_2(db)
        else:
            sanear_particionar(db)
    finally:
        db.close()

"""Script de desarrollo: Genera la obra 'PRUEBA PAGINACIÓN' con volumen de datos
para verificar la paginación e impresión en tamaño carta:
- 15 pagos por transferencia
- 30 gastos/notas en efectivo
- 4 semanas de raya con 5 trabajadores (20 pagos de raya)
- 2 anticipos

Uso:
  python scripts/seed_prueba_paginacion.py            # Crea / recrea la obra y datos de prueba
  python scripts/seed_prueba_paginacion.py --limpiar  # Elimina la obra y todos sus datos asociados
"""
import argparse
import os
import sys
from datetime import date
from decimal import Decimal

# Agregar la raíz del repositorio al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models import (
    Anticipo,
    EstadoObra,
    Gasto,
    MetodoPago,
    Obra,
    OrigenGasto,
    PagoRaya,
    Proveedor,
    TipoProveedor,
    TipoRaya,
    Trabajador,
)

OBRA_NOMBRE = "PRUEBA PAGINACIÓN"


def limpiar_datos(db):
    """Elimina la obra de prueba y todos sus registros en cascada."""
    obras = db.query(Obra).filter(Obra.nombre == OBRA_NOMBRE).all()
    if not obras:
        print(f"ℹ No se encontró ninguna obra con nombre '{OBRA_NOMBRE}'. Nada que limpiar.")
        return 0

    count = len(obras)
    for obra in obras:
        obra_id = obra.id
        db.delete(obra)
        print(f"✓ Obra ID {obra_id} '{OBRA_NOMBRE}' y todos sus gastos/rayas/anticipos/memorias eliminados.")
    db.commit()
    return count


def sembrar_datos(db):
    """Genera la obra y todos los registros de prueba."""
    # 1. Limpiar primero si ya existía para asegurar estado limpio
    limpiar_datos(db)

    print(f"Creando obra '{OBRA_NOMBRE}'...")
    obra = Obra(
        nombre=OBRA_NOMBRE,
        ubicacion="Av. Circunvalación del Sol 1420, Zapopan, Jal.",
        propietario="Desarrollos Residenciales del Sol S.A. de C.V.",
        porcentaje_honorarios=Decimal("10.00"),
        saldo_inicial_transferencias=Decimal("0.00"),
        saldo_inicial_efectivo=Decimal("0.00"),
        saldo_inicial_rayas=Decimal("0.00"),
        saldo_inicial_memorias_anteriores=Decimal("0.00"),
        numero_ultima_memoria_previa=0,
        estado=EstadoObra.EN_CURSO,
    )
    db.add(obra)
    db.flush()

    # 2. Proveedores
    proveedores_data = [
        ("CME890115XX1", "Cementos Mexicanos S.A.B. de C.V.", "CEMEX"),
        ("HDM001016AB1", "Home Depot México S. de R.L. de C.V.", "THE HOME DEPOT"),
        ("MAO980421CC2", "Materiales y Aceros de Occidente S.A. de C.V.", "MATERIALES OCCIDENTE"),
        ("DFA950312DD3", "Distribuidora de Fierro y Acero de Jalisco S.A.", "ACEROS GUADALAJARA"),
        ("TSS020524EE4", "Truper Servicios S.A. de C.V.", "TRUPER"),
        ("PCO910228FF5", "Consorcio Comex S.A. de C.V.", "COMEX"),
        ("PERJ800101GG6", "Juan Pérez Rodríguez", "TLAPALERÍA EL MARTILLO"),
        ("FPA050607HH7", "Ferretera y Perfiles Atlas S.A. de C.V.", "FERRETERÍA ATLAS"),
        ("SHI120304JJ8", "Suministros Hidráulicos e Industriales S.A.", "TUBERÍAS Y CONEXIONES"),
        ("VIJ150809KK9", "Vidriería Integral de Jalisco S.A. de C.V.", "VIDRIOS Y ALUMINIO DEL BAJÍO"),
    ]

    prov_objs = []
    for rfc, razon, alias in proveedores_data:
        p = db.query(Proveedor).filter(Proveedor.rfc == rfc).first()
        if not p:
            p = Proveedor(
                rfc=rfc,
                razon_social=razon,
                alias=alias,
                tipo=TipoProveedor.CON_FACTURA,
            )
            db.add(p)
            db.flush()
        prov_objs.append(p)

    # 3. 15 Transferencias (Facturas bancarias)
    transferencias_items = [
        ("CEMENTO GRIS CPC 30R - 10 TONELADAS", "FACTURA A-1024", Decimal("38500.00"), prov_objs[0], date(2026, 10, 1)),
        ("VARILLA CORRUGADA 3/8 Y ALAMBRE RECOCIDO", "FACTURA AC-882", Decimal("24850.50"), prov_objs[3], date(2026, 10, 2)),
        ("GRAVA Y ARENA DE RÍO 14 M3", "FACTURA MAT-450", Decimal("8400.00"), prov_objs[2], date(2026, 10, 3)),
        ("TABIQUE ROJO RECOCIDO 5 MIL PIEZAS", "FACTURA MAT-462", Decimal("16500.00"), prov_objs[2], date(2026, 10, 5)),
        ("VIGUETA Y BOVEDILLA LOSA PLANTA ALTA", "FACTURA MAT-475", Decimal("31200.00"), prov_objs[2], date(2026, 10, 6)),
        ("MALLA ELECTROSOLDADA 6-6/10-10", "FACTURA AC-905", Decimal("9750.00"), prov_objs[3], date(2026, 10, 7)),
        ("IMPERMEABILIZANTE ACRÍLICO 10 AÑOS Y MALLA", "FACTURA F-5510", Decimal("12300.00"), prov_objs[5], date(2026, 10, 9)),
        ("TUBO SANITARIO PVC 4 PULG Y CONEXIONES", "FACTURA TUB-112", Decimal("7850.00"), prov_objs[8], date(2026, 10, 10)),
        ("CABLE DE COBRE CALIBRE 12 Y 10 CONDUMEX", "FACTURA HD-9941", Decimal("14200.00"), prov_objs[1], date(2026, 10, 12)),
        ("PISOS PORCELANATO 60X60 Y PEGAPISO", "FACTURA HD-9988", Decimal("28900.00"), prov_objs[1], date(2026, 10, 14)),
        ("HERRAMIENTA MENOR Y REVOLVEDORA 1 SACO", "FACTURA TRU-304", Decimal("18500.00"), prov_objs[4], date(2026, 10, 16)),
        ("CAL Y YESO 40 BULTOS", "FACTURA MAT-501", Decimal("4600.00"), prov_objs[2], date(2026, 10, 18)),
        ("VENTANERÍA DE ALUMINIO LÍNEA PANORAMA", "FACTURA VID-77", Decimal("45000.00"), prov_objs[9], date(2026, 10, 20)),
        ("TABLAROCA EXTRAPLACA Y PERFILES GALVANIZADOS", "FACTURA HD-1011", Decimal("11600.00"), prov_objs[1], date(2026, 10, 22)),
        ("PINTURA VINÍLICA Y ESMALTE ANTICORROSIVO", "FACTURA F-5620", Decimal("8950.00"), prov_objs[5], date(2026, 10, 24)),
    ]

    for conc, comp, imp, prov, f in transferencias_items:
        g = Gasto(
            obra_id=obra.id,
            fecha=f,
            proveedor_id=prov.id,
            concepto_resumido=conc,
            comprobante=comp,
            tipo_comprobante="FACTURA",
            importe=imp,
            metodo_pago=MetodoPago.TRANSFERENCIA,
            origen=OrigenGasto.XML,
        )
        db.add(g)

    # 4. 30 Gastos en Efectivo (Caja chica, notas, tickets)
    efectivo_items = [
        ("CLAVOS PARA CONCRETO Y MADERA", "NOTA 101", Decimal("185.00"), prov_objs[6], date(2026, 10, 1)),
        ("DISCOS DE CORTE PARA ESMERIL 4 1/2", "NOTA 102", Decimal("320.00"), prov_objs[6], date(2026, 10, 1)),
        ("FLETE MATERIAL MENOR CAMIONETA", "RECIBO 01", Decimal("600.00"), None, date(2026, 10, 2)),
        ("RODILLOS Y BROCHAS DE 4 PULGADAS", "NOTA 105", Decimal("280.00"), prov_objs[5], date(2026, 10, 2)),
        ("SEGUETAS Y HOJAS DE REPUESTO", "NOTA 108", Decimal("140.00"), prov_objs[4], date(2026, 10, 3)),
        ("HIELO Y AGUA POTABLE PARA CUADRILLA", "TICKET OXXO", Decimal("225.50"), None, date(2026, 10, 3)),
        ("CINTA CANELA Y PLÁSTICO NEGRO CALIBRE 600", "NOTA 115", Decimal("450.00"), prov_objs[6], date(2026, 10, 4)),
        ("TORNILLOS TABLAROCA Y TAQUETES", "NOTA 118", Decimal("195.00"), prov_objs[4], date(2026, 10, 5)),
        ("FLETE RETIRO DE ESCOMBRO CAMIÓN 7 M3", "RECIBO 02", Decimal("1400.00"), None, date(2026, 10, 5)),
        ("GASOLINA GENERADOR ELÉCTRICO", "TICKET GAS", Decimal("500.00"), None, date(2026, 10, 6)),
        ("SILICÓN TRANSPARENTE Y PISTOLA DE CALAFATEO", "NOTA 125", Decimal("310.00"), prov_objs[7], date(2026, 10, 7)),
        ("CHAPA Y CANDADO DE ALTA SEGURIDAD BODEGA", "NOTA 130", Decimal("850.00"), prov_objs[7], date(2026, 10, 8)),
        ("GUANTES DE CARNAZA Y LENTES DE SEGURIDAD", "NOTA 134", Decimal("420.00"), prov_objs[4], date(2026, 10, 9)),
        ("PEGAMENTO Y LIMPIADOR PARA TUBERÍA PVC", "NOTA 140", Decimal("215.00"), prov_objs[8], date(2026, 10, 10)),
        ("CABLE Y CLAVIJA USO RUDO 20 METROS", "NOTA 145", Decimal("680.00"), prov_objs[7], date(2026, 10, 11)),
        ("BOTAS DE CASQUILLO AYUDANTE", "TICKET 342", Decimal("650.00"), prov_objs[4], date(2026, 10, 12)),
        ("LIJAS DE AGUA Y MADERA VARIAS", "NOTA 151", Decimal("130.00"), prov_objs[6], date(2026, 10, 13)),
        ("COPLAS CONDUIT Y CAJAS REGISTRO", "NOTA 155", Decimal("295.00"), prov_objs[7], date(2026, 10, 14)),
        ("BROCAS PARA CONCRETO 3/8 Y 1/2", "NOTA 160", Decimal("410.00"), prov_objs[4], date(2026, 10, 15)),
        ("LLAVE DE PASO Y CINTA TEFLÓN", "NOTA 165", Decimal("260.00"), prov_objs[8], date(2026, 10, 16)),
        ("TIÑER AMERICANO 5 LITROS", "NOTA 170", Decimal("190.00"), prov_objs[5], date(2026, 10, 17)),
        ("ESPÁTULAS Y LLANAS METÁLICAS", "NOTA 174", Decimal("380.00"), prov_objs[4], date(2026, 10, 18)),
        ("PIJAS AUTORROSCANTES BROCA", "NOTA 179", Decimal("165.00"), prov_objs[7], date(2026, 10, 19)),
        ("EXTENSIÓN ELÉCTRICA CALIBRE 14", "NOTA 182", Decimal("490.00"), prov_objs[7], date(2026, 10, 20)),
        ("AGUA Y SUEROS HIDRATANTES CUADRILLA", "TICKET 992", Decimal("240.00"), None, date(2026, 10, 21)),
        ("RETIRO DE BASURA Y MADERA VIEJA", "RECIBO 03", Decimal("800.00"), None, date(2026, 10, 22)),
        ("CEMENTO BLANCO 5 KG Y COLOR ROJO", "NOTA 190", Decimal("175.00"), prov_objs[6], date(2026, 10, 23)),
        ("TAPAS CIEGAS Y APAGADORES", "NOTA 195", Decimal("340.00"), prov_objs[7], date(2026, 10, 23)),
        ("BARREDORAS Y BOTES DE PLÁSTICO", "NOTA 201", Decimal("290.00"), prov_objs[6], date(2026, 10, 24)),
        ("GASOLINA FLETES LOCALES", "TICKET GAS 2", Decimal("600.00"), None, date(2026, 10, 25)),
    ]

    for conc, comp, imp, prov, f in efectivo_items:
        g = Gasto(
            obra_id=obra.id,
            fecha=f,
            proveedor_id=prov.id if prov else None,
            concepto_resumido=conc,
            comprobante=comp,
            tipo_comprobante="NOTA",
            importe=imp,
            metodo_pago=MetodoPago.EFECTIVO,
            origen=OrigenGasto.NOTA if "NOTA" in comp else OrigenGasto.MANUAL,
        )
        db.add(g)

    # 5. 5 Trabajadores
    trabajadores_data = [
        ("Roberto Hernández Mendoza", "Maestro de Obras"),
        ("Juan Carlos Gómez Ruiz", "Albañil"),
        ("Pedro Sánchez López", "Albañil"),
        ("Miguel Ángel Torres Cruz", "Fierrero"),
        ("José Luis Ramírez Nava", "Ayudante General"),
    ]

    trab_objs = []
    for nom, ofi in trabajadores_data:
        t = db.query(Trabajador).filter(Trabajador.nombre == nom).first()
        if not t:
            t = Trabajador(nombre=nom, oficio=ofi)
            db.add(t)
            db.flush()
        trab_objs.append(t)

    # 6. 4 Semanas de Raya (Semanas 40, 41, 42, 43)
    semanas_info = [
        (40, date(2026, 9, 28), date(2026, 10, 4)),
        (41, date(2026, 10, 5), date(2026, 10, 11)),
        (42, date(2026, 10, 12), date(2026, 10, 18)),
        (43, date(2026, 10, 19), date(2026, 10, 25)),
    ]

    for sem_num, f_ini, f_fin in semanas_info:
        # Maestro: 6 días x $500
        db.add(PagoRaya(
            obra_id=obra.id,
            trabajador_id=trab_objs[0].id,
            semana_numero=sem_num,
            fecha_inicio=f_ini,
            fecha_fin=f_fin,
            tipo=TipoRaya.DIA,
            cantidad=Decimal("6.000"),
            tarifa=Decimal("500.00"),
            importe=Decimal("3000.00"),
        ))
        # Albañil 1: 6 días x $400
        db.add(PagoRaya(
            obra_id=obra.id,
            trabajador_id=trab_objs[1].id,
            semana_numero=sem_num,
            fecha_inicio=f_ini,
            fecha_fin=f_fin,
            tipo=TipoRaya.DIA,
            cantidad=Decimal("6.000"),
            tarifa=Decimal("400.00"),
            importe=Decimal("2400.00"),
        ))
        # Albañil 2: Destajo (metros pegados/aplanados)
        m2 = Decimal("25.500") if sem_num % 2 == 0 else Decimal("28.000")
        tarifa_dest = Decimal("95.00")
        imp_dest = (m2 * tarifa_dest).quantize(Decimal("0.01"))
        db.add(PagoRaya(
            obra_id=obra.id,
            trabajador_id=trab_objs[2].id,
            semana_numero=sem_num,
            fecha_inicio=f_ini,
            fecha_fin=f_fin,
            tipo=TipoRaya.DESTAJO,
            cantidad=m2,
            tarifa=tarifa_dest,
            importe=imp_dest,
        ))
        # Fierrero: 6 días x $380
        db.add(PagoRaya(
            obra_id=obra.id,
            trabajador_id=trab_objs[3].id,
            semana_numero=sem_num,
            fecha_inicio=f_ini,
            fecha_fin=f_fin,
            tipo=TipoRaya.DIA,
            cantidad=Decimal("6.000"),
            tarifa=Decimal("380.00"),
            importe=Decimal("2280.00"),
        ))
        # Ayudante: 6 días x $250
        db.add(PagoRaya(
            obra_id=obra.id,
            trabajador_id=trab_objs[4].id,
            semana_numero=sem_num,
            fecha_inicio=f_ini,
            fecha_fin=f_fin,
            tipo=TipoRaya.DIA,
            cantidad=Decimal("6.000"),
            tarifa=Decimal("250.00"),
            importe=Decimal("1500.00"),
        ))

    # 7. 2 Anticipos
    db.add(Anticipo(
        obra_id=obra.id,
        importe=Decimal("35000.00"),
        comprobante="TRANSF BANCOMER #89214",
        fecha=date(2026, 10, 2),
    ))
    db.add(Anticipo(
        obra_id=obra.id,
        importe=Decimal("25000.00"),
        comprobante="TRANSF BANORTE #10452",
        fecha=date(2026, 10, 15),
    ))

    db.commit()

    print("\n✅ Datos de prueba creados exitosamente:")
    print(f"  • Obra ID: {obra.id} - '{obra.nombre}'")
    print("  • 15 Pagos por Transferencia")
    print("  • 30 Gastos / Notas en Efectivo")
    print("  • 20 Pagos de Raya (4 semanas × 5 trabajadores)")
    print("  • 2 Anticipos ($35,000.00 y $25,000.00 = $60,000.00 total)")
    print("\nPara probar la paginación en el navegador:")
    print(f"  1. Ve a http://localhost:5173/obras/{obra.id}")
    print("  2. Haz clic en 'Crear Memoria' y selecciona el rango del 01/10/2026 al 31/10/2026.")
    print("  3. Marca todos los gastos y nóminas en el Paso 2.")
    print("  4. Avanza al Paso 3 (Vista Previa) o ingresa a su ruta de impresión.")
    print("  5. Presiona Ctrl+P y verifica:")
    print("     - thead repetido en cada cambio de página")
    print("     - Filas no cortadas a la mitad (break-inside: avoid)")
    print("     - Totales pegados a sus tablas")
    print("     - Sección del arquitecto forzada en página nueva")
    print(f"\nPara limpiar estos datos en un solo comando:")
    print("  python scripts/seed_prueba_paginacion.py --limpiar\n")


def main():
    parser = argparse.ArgumentParser(
        description="Genera o elimina el proyecto 'PRUEBA PAGINACIÓN' con volumen de datos para pruebas de impresión."
    )
    parser.add_argument(
        "--limpiar",
        "--clean",
        action="store_true",
        help="Elimina la obra de prueba y todos sus registros asociados.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.limpiar:
            limpiar_datos(db)
        else:
            sembrar_datos(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()

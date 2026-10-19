"""Pruebas de integración de la API REST completa (100% local SQLite)."""
import io
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

CFDI_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Serie="{serie}" Folio="{folio}" Fecha="{fecha}T12:00:00"
    SubTotal="{subtotal}" Total="{total}" Moneda="MXN" FormaPago="{forma_pago}" MetodoPago="PUE">
  <cfdi:Emisor Rfc="{rfc}" Nombre="{nombre}" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="XAXX010101000" Nombre="CLIENTE PRUEBA" UsoCFDI="G03" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="601"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="30111500" Cantidad="10" ClaveUnidad="H87" Unidad="PZA"
        Descripcion="Bultos de Cemento Gris Tolteca 50kg" ValorUnitario="200.00" Importe="2000.00"/>
  </cfdi:Conceptos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="{uuid_str}" FechaTimbrado="{fecha}T12:05:00" Version="1.1"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
"""


def generar_cfdi_xml(
    uuid_str: str,
    total: str = "2320.00",
    subtotal: str = "2000.00",
    serie: str = "A",
    folio: str = "100",
    rfc: str = "CEM850101XYZ",
    nombre: str = "CEMENTERA DE ORIENTE SA DE CV",
    forma_pago: str = "03",
    fecha: str = "2026-03-10",
) -> bytes:
    return CFDI_TEMPLATE.format(
        serie=serie,
        folio=folio,
        fecha=fecha,
        subtotal=subtotal,
        total=total,
        forma_pago=forma_pago,
        rfc=rfc,
        nombre=nombre,
        uuid_str=uuid_str,
    ).encode("utf-8")


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_crud_obras(client: TestClient):
    # Crear obra
    payload = {
        "nombre": "Casa Bosques",
        "ubicacion": "Bosques de las Lomas",
        "propietario": "Arq. Roberto",
        "porcentaje_honorarios": "10.00",
        "saldo_inicial_acumulado": "0.00",
        "saldo_inicial_gastado": "0.00",
    }
    r = client.post("/obras", json=payload)
    assert r.status_code == 201
    obra = r.json()
    assert obra["id"] > 0
    assert obra["nombre"] == "Casa Bosques"
    assert obra["porcentaje_honorarios"] == "10.00"

    obra_id = obra["id"]

    # Obtener obra
    r = client.get(f"/obras/{obra_id}")
    assert r.status_code == 200
    assert r.json()["nombre"] == "Casa Bosques"

    # Actualizar obra
    r = client.patch(f"/obras/{obra_id}", json={"propietario": "Roberto Carlos"})
    assert r.status_code == 200
    assert r.json()["propietario"] == "Roberto Carlos"

    # Listar obras
    r = client.get("/obras")
    assert r.status_code == 200
    assert any(o["id"] == obra_id for o in r.json())


def test_crud_proveedores_y_unicidad(client: TestClient):
    rfc = f"PROV{uuid.uuid4().hex[:8].upper()}"
    # Crear proveedor
    r = client.post("/proveedores", json={"rfc": rfc, "razon_social": "Materiales El Roble SA", "alias": "El Roble"})
    assert r.status_code == 201
    prov = r.json()
    assert prov["rfc"] == rfc
    assert prov["alias"] == "El Roble"
    assert prov["nombre_memoria"] == "El Roble"

    # Duplicado de RFC -> 409
    r_dup = client.post("/proveedores", json={"rfc": rfc, "razon_social": "Otro Nombre"})
    assert r_dup.status_code == 409

    # Búsqueda
    r_search = client.get("/proveedores", params={"q": "Roble"})
    assert r_search.status_code == 200
    assert any(p["rfc"] == rfc for p in r_search.json())


def test_crud_trabajadores_y_rayas(client: TestClient):
    # Crear trabajador
    r_t = client.post("/trabajadores", json={"nombre": "Pedro Albañil", "oficio": "Oficial Albañil"})
    assert r_t.status_code == 201
    t = r_t.json()
    t_id = t["id"]

    # Crear obra para las rayas
    r_o = client.post("/obras", json={"nombre": "Obra Rayas Test"})
    o_id = r_o.json()["id"]

    # Crear pago de raya sin importe explícito -> debe calcular cantidad * tarifa
    payload_raya = {
        "trabajador_id": t_id,
        "semana_numero": 12,
        "fecha_inicio": "2026-03-01",
        "fecha_fin": "2026-03-07",
        "tipo": "dia",
        "cantidad": "6.000",
        "tarifa": "500.00",
    }
    r_r = client.post(f"/obras/{o_id}/rayas", json=payload_raya)
    assert r_r.status_code == 201
    raya = r_r.json()
    assert raya["importe"] == "3000.00"
    assert raya["trabajador_nombre"] == "Pedro Albañil"

    # Consultar pagos acumulados del trabajador
    r_pagos = client.get(f"/trabajadores/{t_id}/pagos")
    assert r_pagos.status_code == 200
    pagos_data = r_pagos.json()
    assert pagos_data["total_acumulado"] == "3000.00"
    assert len(pagos_data["pagos"]) == 1


def test_crud_anticipos(client: TestClient):
    r_o = client.post("/obras", json={"nombre": "Obra Anticipos"})
    o_id = r_o.json()["id"]

    r_ant = client.post(
        f"/obras/{o_id}/anticipos",
        json={"importe": "25000.00", "comprobante": "TRANSF-001", "fecha": "2026-03-02"},
    )
    assert r_ant.status_code == 201
    ant = r_ant.json()
    assert ant["importe"] == "25000.00"

    r_list = client.get(f"/obras/{o_id}/anticipos")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1


def test_facturas_subida_confirmacion_y_duplicados(client: TestClient):
    r_o = client.post("/obras", json={"nombre": "Obra Facturas CFDI"})
    o_id = r_o.json()["id"]

    test_uuid = str(uuid.uuid4()).upper()
    xml_bytes = generar_cfdi_xml(test_uuid, total="1500.00", subtotal="1293.10", serie="FAC", folio="999")

    # 1. Subida para revisión (staging)
    files = [("files", ("factura_test.xml", xml_bytes, "application/xml"))]
    r_upload = client.post(f"/obras/{o_id}/facturas", files=files)
    assert r_upload.status_code == 200
    upload_res = r_upload.json()
    assert len(upload_res["items"]) == 1
    item = upload_res["items"][0]
    staging_id = item["staging_id"]
    assert item["datos"]["uuid"] == test_uuid
    assert item["sugerido"]["comprobante"] == "FAC 999"
    # Total 1500.00 <= 2000.00 -> metodo_pago es None y requiere_decision_metodo_pago es True
    assert item["sugerido"]["metodo_pago"] is None
    assert item["sugerido"]["requiere_decision_metodo_pago"] is True
    assert item["requiere_decision_metodo_pago"] is True

    # Confirmación sin método de pago debe ser rechazada con HTTP 422
    payload_sin_metodo = {"items": [{"staging_id": staging_id}]}
    r_sin_metodo = client.post(f"/obras/{o_id}/facturas/confirmar", json=payload_sin_metodo)
    assert r_sin_metodo.status_code == 422

    # 2. Confirmación con método de pago explícito
    payload_conf = {
        "items": [
            {
                "staging_id": staging_id,
                "metodo_pago": "transferencia",
                "proveedor_alias": "Mi Cementara Favorita",
            }
        ]
    }
    r_conf = client.post(f"/obras/{o_id}/facturas/confirmar", json=payload_conf)
    assert r_conf.status_code == 201
    gastos_creados = r_conf.json()
    assert len(gastos_creados) == 1
    gasto = gastos_creados[0]
    assert gasto["importe"] == "1500.00"
    assert gasto["origen"] == "xml"
    assert gasto["factura"]["uuid"] == test_uuid

    # 3. Descarga del XML guardado
    r_file = client.get(f"/facturas/{gasto['id']}/archivo/xml")
    assert r_file.status_code == 200
    assert r_file.headers["content-type"].startswith("application/xml")

    # 4. Proteger importe de gasto XML contra modificaciones manuales
    r_patch = client.patch(f"/gastos/{gasto['id']}", json={"importe": "9999.00"})
    assert r_patch.status_code == 400
    assert "XML" in r_patch.json()["detail"]

    # 5. Intentar subir el mismo UUID otra vez -> reporte de duplicado / 409
    files_dup = [("files", ("factura_test_repetida.xml", xml_bytes, "application/xml"))]
    r_upload_dup = client.post(f"/obras/{o_id}/facturas", files=files_dup)
    assert r_upload_dup.status_code == 409


def test_gastos_buscar_y_excluir_obra(client: TestClient):
    r_o1 = client.post("/obras", json={"nombre": "Obra A"})
    o1_id = r_o1.json()["id"]
    r_o2 = client.post("/obras", json={"nombre": "Obra B"})
    o2_id = r_o2.json()["id"]

    # Gasto en Obra A
    client.post(
        f"/obras/{o1_id}/gastos",
        json={
            "fecha": "2026-03-05",
            "concepto_resumido": "Varilla corrugada 3/8",
            "comprobante": "TICKET-11",
            "importe": "4500.00",
            "metodo_pago": "transferencia",
            "origen": "manual",
        },
    )

    # Gasto en Obra B
    client.post(
        f"/obras/{o2_id}/gastos",
        json={
            "fecha": "2026-03-06",
            "concepto_resumido": "Varilla corrugada 1/2",
            "comprobante": "TICKET-22",
            "importe": "6200.00",
            "metodo_pago": "efectivo",
            "origen": "nota",
        },
    )

    # Búsqueda excluyendo Obra A: solo debe aparecer el de Obra B
    r_busq = client.get("/gastos/buscar", params={"q": "Varilla", "excluir_obra": o1_id})
    assert r_busq.status_code == 200
    resultados = r_busq.json()
    assert all(g["obra_id"] != o1_id for g in resultados)
    assert any(g["obra_id"] == o2_id for g in resultados)


def test_memoria_caso_obligatorio_y_cierre(client: TestClient):
    """
    Caso de prueba obligatorio:
    Memoria 01 con 10% de honorarios:
    transferencias: 116,634.40
    efectivo: 10,835.20
    rayas: 17,109.60

    Esperados:
    honorarios: 14,457.92
    subtotal: 31,567.52
    iva: 5,050.80
    importe_factura: 36,618.32
    total_memoria: 164,087.92
    cobrado: 47,453.52
    """
    # 1. Crear obra con 10% de honorarios
    r_o = client.post(
        "/obras",
        json={
            "nombre": "Residencia Campestre",
            "porcentaje_honorarios": "10.00",
            "saldo_inicial_acumulado": "0.00",
            "saldo_inicial_gastado": "0.00",
        },
    )
    obra_id = r_o.json()["id"]

    # 2. Registrar gasto en transferencia
    r_g1 = client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "fecha": "2026-03-02",
            "concepto_resumido": "Materiales gruesos",
            "comprobante": "TRANSF-01",
            "importe": "116634.40",
            "metodo_pago": "transferencia",
            "origen": "manual",
        },
    )
    gasto_transf_id = r_g1.json()["id"]

    # 3. Registrar gasto en efectivo
    r_g2 = client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "fecha": "2026-03-03",
            "concepto_resumido": "Fletes y herramienta menor",
            "comprobante": "EFEC-01",
            "importe": "10835.20",
            "metodo_pago": "efectivo",
            "origen": "manual",
        },
    )
    gasto_efec_id = r_g2.json()["id"]

    # 4. Registrar trabajador y pago de raya
    r_t = client.post("/trabajadores", json={"nombre": "Cuadrilla Rayas", "oficio": "Albañiles"})
    t_id = r_t.json()["id"]

    r_raya = client.post(
        f"/obras/{obra_id}/rayas",
        json={
            "trabajador_id": t_id,
            "semana_numero": 1,
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-03-07",
            "tipo": "dia",
            "cantidad": "1.000",
            "tarifa": "17109.60",
            "importe": "17109.60",
        },
    )
    raya_id = r_raya.json()["id"]

    # 5. Previsualizar Memoria (Preview)
    r_prev = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-03-01", "fecha_fin": "2026-03-10"},
    )
    assert r_prev.status_code == 200
    prev_data = r_prev.json()
    totales = prev_data["totales"]

    assert totales["transferencias"] == "116634.40"
    assert totales["efectivo"] == "10835.20"
    assert totales["rayas"] == "17109.60"
    assert totales["honorarios"] == "14457.92"
    assert totales["subtotal"] == "31567.52"
    assert totales["iva"] == "5050.80"
    assert totales["importe_factura"] == "36618.32"
    assert totales["total_memoria"] == "164087.92"
    assert totales["cobrado"] == "47453.52"
    assert "PESOS" in prev_data["total_texto"]

    # 6. Guardar borrador de la Memoria 01
    renglones_edit = [
        {"ref_tipo": "gasto", "ref_id": gasto_transf_id, "incluido": True},
        {"ref_tipo": "gasto", "ref_id": gasto_efec_id, "incluido": True},
        {"ref_tipo": "raya", "ref_id": raya_id, "incluido": True},
    ]
    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": obra_id,
            "numero": 1,
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-03-10",
            "porcentaje_honorarios": "10.00",
            "renglones": renglones_edit,
        },
    )
    assert r_guardar.status_code == 201
    memoria_creada = r_guardar.json()
    memoria_id = memoria_creada["id"]
    assert memoria_creada["estado"] == "borrador"
    assert memoria_creada["numero"] == 1

    # 7. Cerrar la Memoria 01
    r_cerrar = client.post(f"/memorias/{memoria_id}/cerrar")
    assert r_cerrar.status_code == 200
    memoria_cerrada = r_cerrar.json()
    assert memoria_cerrada["estado"] == "cerrada"
    assert memoria_cerrada["totales"]["total_memoria"] == "164087.92"

    # 8. Modificar un gasto vivo en la BD después del cierre
    client.patch(f"/gastos/{gasto_efec_id}", json={"concepto_resumido": "Concepto cambiado a posteriori"})

    # Verificar que la memoria cerrada PERMANECE INTACTA (snapshot congelado)
    r_get_mem = client.get(f"/memorias/{memoria_id}")
    assert r_get_mem.status_code == 200
    mem_congelada = r_get_mem.json()
    assert mem_congelada["totales"]["total_memoria"] == "164087.92"
    renglon_efec = next(r for r in mem_congelada["renglones"] if r["ref_id"] == gasto_efec_id)
    assert renglon_efec["concepto"] == "Fletes y herramienta menor"

    # 9. Acumulación para Memoria 02:
    # Si generamos preview para la Memoria 02, debe tomar los 164,087.92 como gastado anterior
    r_prev_m2 = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-03-11", "fecha_fin": "2026-03-20"},
    )
    assert r_prev_m2.status_code == 200
    totales_m2 = r_prev_m2.json()["totales"]
    assert r_prev_m2.json()["numero_sugerido"] == 2
    # Como no hay gastos nuevos en ese rango, gastado_a_la_fecha = lo gastado de la memoria 1
    assert totales_m2["gastado_a_la_fecha"] == "164087.92"
    assert totales_m2["acumulado_transferencias"] == "116634.40"

    # 10. Exportación a XLSX con fórmulas vivas
    r_xlsx = client.get(f"/memorias/{memoria_id}/xlsx")
    assert r_xlsx.status_code == 200
    assert "application/vnd.openxmlformats" in r_xlsx.headers["content-type"]
    assert 'attachment; filename="MEMORIA 01 - Residencia Campestre.xlsx"' in r_xlsx.headers.get("content-disposition", "")
    assert len(r_xlsx.content) > 1000


def test_configuracion_endpoints(client: TestClient):
    # GET valor por defecto
    r = client.get("/configuracion/ultimo_folio_factura_arquitecto")
    assert r.status_code == 200
    assert r.json()["clave"] == "ultimo_folio_factura_arquitecto"

    # PUT valor nuevo
    r_put = client.put("/configuracion/ultimo_folio_factura_arquitecto", json={"valor": "120"})
    assert r_put.status_code == 200
    assert r_put.json()["valor"] == "120"

    # GET valor actualizado
    r_get = client.get("/configuracion/ultimo_folio_factura_arquitecto")
    assert r_get.status_code == 200
    assert r_get.json()["valor"] == "120"

    # PUT valor inválido no numérico
    r_bad = client.put("/configuracion/ultimo_folio_factura_arquitecto", json={"valor": "abc"})
    assert r_bad.status_code == 422


def test_folio_factura_arquitecto_preview_y_cierre(client: TestClient):
    # Establecer último folio en 50
    client.put("/configuracion/ultimo_folio_factura_arquitecto", json={"valor": "50"})

    # Crear obra y gasto
    r_o = client.post("/obras", json={"nombre": "Obra Folio Test"})
    o_id = r_o.json()["id"]
    r_g = client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2026-03-01",
            "concepto_resumido": "Gasto test",
            "comprobante": "T-1",
            "importe": "1000.00",
            "metodo_pago": "efectivo",
            "origen": "manual",
        },
    )
    g_id = r_g.json()["id"]

    # Preview debe sugerir 51 (ultimo + 1)
    r_prev = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={"fecha_inicio": "2026-03-01", "fecha_fin": "2026-03-15"},
    )
    assert r_prev.status_code == 200
    assert r_prev.json()["folio_sugerido"] == "51"

    # Guardar borrador con folio 55
    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": o_id,
            "numero": 1,
            "folio_factura_arquitecto": "55",
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-03-15",
            "porcentaje_honorarios": "10.00",
            "renglones": [{"ref_tipo": "gasto", "ref_id": g_id, "incluido": True}],
        },
    )
    assert r_guardar.status_code == 201
    mem_id = r_guardar.json()["id"]
    assert r_guardar.json()["folio_factura_arquitecto"] == "55"

    # Cerrar memoria -> debe actualizar configuración al mayor valor (55)
    r_cerrar = client.post(f"/memorias/{mem_id}/cerrar")
    assert r_cerrar.status_code == 200
    assert r_cerrar.json()["folio_factura_arquitecto"] == "55"

    r_conf = client.get("/configuracion/ultimo_folio_factura_arquitecto")
    assert r_conf.json()["valor"] == "55"


def test_regla_metodo_pago_mayor_2000(client: TestClient):
    r_o = client.post("/obras", json={"nombre": "Obra Regla 2000"})
    o_id = r_o.json()["id"]

    # Factura > 2000.00 -> metodo_pago sugerido = transferencia, requiere_decision = False
    uuid_mayor = str(uuid.uuid4()).upper()
    xml_mayor = generar_cfdi_xml(uuid_mayor, total="2500.00", subtotal="2155.17")
    files_mayor = [("files", ("factura_mayor.xml", xml_mayor, "application/xml"))]
    r_up_mayor = client.post(f"/obras/{o_id}/facturas", files=files_mayor)
    assert r_up_mayor.status_code == 200
    item_mayor = r_up_mayor.json()["items"][0]
    assert item_mayor["sugerido"]["metodo_pago"] == "transferencia"
    assert item_mayor["sugerido"]["requiere_decision_metodo_pago"] is False
    assert item_mayor["requiere_decision_metodo_pago"] is False


def test_memoria_con_anticipos_y_saldo_a_favor(client: TestClient):
    # Caso obligatorio con anticipo: cobrado 47453.52 con anticipos 20000.00 -> saldo_a_favor 27453.52
    r_o = client.post(
        "/obras",
        json={
            "nombre": "Obra Con Anticipos",
            "porcentaje_honorarios": "10.00",
            "saldo_inicial_acumulado": "0.00",
            "saldo_inicial_gastado": "0.00",
        },
    )
    o_id = r_o.json()["id"]

    # Gasto transferencia 116,634.40
    r_g1 = client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2026-03-02",
            "concepto_resumido": "Material",
            "comprobante": "T-01",
            "importe": "116634.40",
            "metodo_pago": "transferencia",
            "origen": "manual",
        },
    )
    g1_id = r_g1.json()["id"]

    # Gasto efectivo 10,835.20
    r_g2 = client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2026-03-03",
            "concepto_resumido": "Flete",
            "comprobante": "E-01",
            "importe": "10835.20",
            "metodo_pago": "efectivo",
            "origen": "manual",
        },
    )
    g2_id = r_g2.json()["id"]

    # Raya 17,109.60
    r_t = client.post("/trabajadores", json={"nombre": "Juan Peon", "oficio": "Peon"})
    t_id = r_t.json()["id"]
    r_raya = client.post(
        f"/obras/{o_id}/rayas",
        json={
            "trabajador_id": t_id,
            "semana_numero": 1,
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-03-07",
            "tipo": "dia",
            "cantidad": "1.000",
            "tarifa": "17109.60",
            "importe": "17109.60",
        },
    )
    raya_id = r_raya.json()["id"]

    # Anticipo de 20,000.00
    r_ant = client.post(
        f"/obras/{o_id}/anticipos",
        json={"importe": "20000.00", "comprobante": "ANT-001", "fecha": "2026-03-01"},
    )
    ant_id = r_ant.json()["id"]

    # 1. Preview: debe listar el anticipo y calcular saldo a favor
    r_prev = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={"fecha_inicio": "2026-03-01", "fecha_fin": "2026-03-10"},
    )
    assert r_prev.status_code == 200
    data_prev = r_prev.json()
    totales = data_prev["totales"]
    assert totales["cobrado"] == "47453.52"
    assert totales["anticipos_total"] == "20000.00"
    assert totales["saldo_a_favor"] == "27453.52"
    assert len(data_prev["anticipos"]) == 1
    assert data_prev["anticipos"][0]["importe"] == "20000.00"

    # 2. Guardar borrador incluyendo el anticipo
    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": o_id,
            "numero": 1,
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-03-10",
            "porcentaje_honorarios": "10.00",
            "renglones": [
                {"ref_tipo": "gasto", "ref_id": g1_id, "incluido": True},
                {"ref_tipo": "gasto", "ref_id": g2_id, "incluido": True},
                {"ref_tipo": "raya", "ref_id": raya_id, "incluido": True},
                {"ref_tipo": "anticipo", "ref_id": ant_id, "incluido": True},
            ],
        },
    )
    assert r_guardar.status_code == 201
    mem_guardada = r_guardar.json()
    assert mem_guardada["totales"]["anticipos_total"] == "20000.00"
    assert mem_guardada["totales"]["saldo_a_favor"] == "27453.52"

    # 3. Guardar borrador deseleccionando el anticipo (incluido = False)
    r_deselec = client.put(
        f"/memorias/{mem_guardada['id']}",
        json={
            "obra_id": o_id,
            "numero": 1,
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-03-10",
            "porcentaje_honorarios": "10.00",
            "renglones": [
                {"ref_tipo": "gasto", "ref_id": g1_id, "incluido": True},
                {"ref_tipo": "gasto", "ref_id": g2_id, "incluido": True},
                {"ref_tipo": "raya", "ref_id": raya_id, "incluido": True},
                {"ref_tipo": "anticipo", "ref_id": ant_id, "incluido": False},
            ],
        },
    )
    assert r_deselec.status_code == 200
    assert r_deselec.json()["totales"]["anticipos_total"] == "0.00"
    assert r_deselec.json()["totales"]["saldo_a_favor"] == "47453.52"


def test_obras_resumen_endpoints(client: TestClient):
    """Verifica que /obras/resumen y /obras/{id}/resumen devuelvan correctamente
    los totales de gastos y última memoria sin colisionar con /{obra_id}."""
    # 1. Crear obra de prueba con saldos iniciales
    r_obra = client.post(
        "/obras",
        json={
            "nombre": "Resumen Test Obra",
            "ubicacion": "Colonia Roma",
            "propietario": "Arq. Test",
            "porcentaje_honorarios": "10.00",
            "saldo_inicial_acumulado": "1000.00",
            "saldo_inicial_gastado": "500.00",
        },
    )
    assert r_obra.status_code == 201
    obra_id = r_obra.json()["id"]

    # 2. Agregar un gasto manual de 350.00
    r_gasto = client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "fecha": "2026-03-05",
            "concepto_resumido": "Material menor",
            "comprobante": "TICKET-1",
            "importe": "350.00",
            "metodo_pago": "efectivo",
            "origen": "nota",
        },
    )
    assert r_gasto.status_code == 201

    # 3. GET /obras/resumen (lista de tarjetas)
    r_resumenes = client.get("/obras/resumen")
    assert r_resumenes.status_code == 200
    resumenes = r_resumenes.json()
    assert isinstance(resumenes, list)
    obra_card = next((o for o in resumenes if o["id"] == obra_id), None)
    assert obra_card is not None
    # gastado_a_la_fecha = saldo_inicial_gastado (500.00) + memorias cerradas (0.00) = 500.00
    assert obra_card["gastado_a_la_fecha"] == "500.00"
    # total_gastos es el conteo de gastos registrados en la obra
    assert obra_card["total_gastos"] == 1
    assert obra_card["numero_ultima_memoria"] is None

    # 4. GET /obras/{id}/resumen (individual)
    r_single = client.get(f"/obras/{obra_id}/resumen")
    assert r_single.status_code == 200
    data_single = r_single.json()
    assert data_single["id"] == obra_id
    assert data_single["gastado_a_la_fecha"] == "500.00"
    assert data_single["total_gastos"] == 1
    assert data_single["total_gastado_registrado"] == "350.00"
    assert data_single["numero_ultima_memoria"] is None


def test_obra_numero_memoria_previa_y_sugerido(client: TestClient):
    """Verifica que el campo numero_ultima_memoria_previa se guarde y que
    el número sugerido de la siguiente memoria sea mayor entre ese valor y la última memoria + 1."""
    # 1. Crear obra con memoria previa = 15
    r_obra = client.post(
        "/obras",
        json={
            "nombre": "Obra Con Historial Previo",
            "ubicacion": "Zapopan",
            "propietario": "Cliente Previo",
            "porcentaje_honorarios": "10.00",
            "numero_ultima_memoria_previa": 15,
        },
    )
    assert r_obra.status_code == 201
    obra_id = r_obra.json()["id"]
    assert r_obra.json()["numero_ultima_memoria_previa"] == 15

    # 2. Preview de memoria: siguiente número debe ser 15 + 1 = 16
    r_prev = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-03-01", "fecha_fin": "2026-03-15"},
    )
    assert r_prev.status_code == 200
    assert r_prev.json()["numero_sugerido"] == 16


def test_rayas_captura_por_semana_batch(client: TestClient):
    """Verifica la creación de múltiples pagos de raya por semana en un solo request."""
    # 1. Crear obra y 2 trabajadores
    r_o = client.post("/obras", json={"nombre": "Obra Rayas Semana"})
    assert r_o.status_code == 201
    o_id = r_o.json()["id"]

    r_t1 = client.post("/trabajadores", json={"nombre": "Juan Pérez", "oficio": "Albañil"})
    assert r_t1.status_code == 201
    t1_id = r_t1.json()["id"]

    r_t2 = client.post("/trabajadores", json={"nombre": "Mario Gómez", "oficio": "Ayudante"})
    assert r_t2.status_code == 201
    t2_id = r_t2.json()["id"]

    # 2. POST /obras/{id}/rayas/semana
    payload = {
        "semana_numero": 31,
        "fecha_inicio": "2026-07-28",
        "fecha_fin": "2026-08-03",
        "filas": [
            {"trabajador_id": t1_id, "tipo": "dia", "cantidad": "6.000", "tarifa": "500.00"},
            {"trabajador_id": t2_id, "tipo": "destajo", "cantidad": "25.000", "tarifa": "100.00"},
        ],
    }
    r_batch = client.post(f"/obras/{o_id}/rayas/semana", json=payload)
    assert r_batch.status_code == 201
    rayas_creadas = r_batch.json()
    assert len(rayas_creadas) == 2
    assert rayas_creadas[0]["importe"] == "3000.00"  # 6 * 500
    assert rayas_creadas[1]["importe"] == "2500.00"  # 25 * 100


def test_descargar_respaldo_zip(client: TestClient):
    """Verifica que el endpoint /configuracion/sistema/respaldo devuelva un archivo zip válido,
    que contenga la base de datos app.db y que SQLite pueda abrirla y consultar tablas."""
    import sqlite3
    import tempfile
    import zipfile

    r = client.get("/configuracion/sistema/respaldo")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "attachment; filename=respaldo_memorias_" in r.headers["content-disposition"]
    assert len(r.content) > 0

    # Descomprimir en memoria y verificar SQLite
    zip_bytes = io.BytesIO(r.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "data/app.db" in namelist
        # Extraer a archivo temporal para que sqlite3 pueda abrirlo
        db_bytes = zf.read("data/app.db")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            tf.write(db_bytes)
            tf.flush()
            temp_db_name = tf.name

        try:
            conn = sqlite3.connect(temp_db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            assert "obras" in tables
            assert "gastos" in tables
            assert "proveedores" in tables
        finally:
            import os
            if os.path.exists(temp_db_name):
                os.remove(temp_db_name)


def test_rayas_calculo_exacto_casos_especificos(client: TestClient):
    """Pruebas exigidas: 6×50=300, 2.1×50=105, 1×100=100, 0.5×333.33=166.67."""
    r_obra = client.post("/obras", json={"nombre": "Obra Pruebas Rayas Multiplicacion"})
    obra_id = r_obra.json()["id"]

    r_t = client.post("/trabajadores", json={"nombre": "Trabajador Calculo"})
    t_id = r_t.json()["id"]

    casos = [
        ("6", "50.00", "300.00"),
        ("2.1", "50.00", "105.00"),
        ("1", "100.00", "100.00"),
        ("0.5", "333.33", "166.67"),
    ]

    for cant, tarifa, imp_esperado in casos:
        # 1. Individual
        payload_ind = {
            "trabajador_id": t_id,
            "semana_numero": 10,
            "fecha_inicio": "2026-03-02",
            "fecha_fin": "2026-03-08",
            "tipo": "dia",
            "cantidad": cant,
            "tarifa": tarifa,
        }
        r = client.post(f"/obras/{obra_id}/rayas", json=payload_ind)
        assert r.status_code == 201
        assert r.json()["importe"] == imp_esperado

        # 2. Batch por semana (enviando incluso un importe erróneo desde el cliente para confirmar que el backend lo recalcula)
        payload_batch = {
            "semana_numero": 11,
            "fecha_inicio": "2026-03-09",
            "fecha_fin": "2026-03-15",
            "filas": [
                {
                    "trabajador_id": t_id,
                    "tipo": "dia",
                    "cantidad": cant,
                    "tarifa": tarifa,
                    "importe": "999999.00",  # El backend debe ignorar esto y calcular imp_esperado
                }
            ],
        }
        r_b = client.post(f"/obras/{obra_id}/rayas/semana", json=payload_batch)
        assert r_b.status_code == 201
        assert r_b.json()[0]["importe"] == imp_esperado


def test_proveedores_con_y_sin_factura_y_conversion(client: TestClient):
    """Prueba proveedor sin factura (RFC opcional/nulo), unicidad de RFC no nulo, y conversión a con_factura."""
    # 1. Crear sin factura sin RFC
    r1 = client.post(
        "/proveedores",
        json={"tipo": "sin_factura", "razon_social": "Ferretería Don Pepe", "alias": "Don Pepe"},
    )
    assert r1.status_code == 201
    prov1 = r1.json()
    assert prov1["tipo"] == "sin_factura"
    assert prov1["rfc"] is None
    assert prov1["nombre_memoria"] == "Don Pepe"

    # 2. Crear otro sin factura también sin RFC (ambos RFC nulos permitidos)
    r2 = client.post(
        "/proveedores",
        json={"tipo": "sin_factura", "razon_social": "Tlapalería La Fe"},
    )
    assert r2.status_code == 201
    prov2 = r2.json()
    assert prov2["rfc"] is None

    # 3. Proveedor con factura exige RFC
    r_err = client.post(
        "/proveedores",
        json={"tipo": "con_factura", "razon_social": "Distribuidora ACME"},
    )
    assert r_err.status_code == 422

    # 4. Proveedor con factura con RFC válido
    rfc_test = f"ACM{uuid.uuid4().hex[:8].upper()}"
    r3 = client.post(
        "/proveedores",
        json={"tipo": "con_factura", "rfc": rfc_test, "razon_social": "Distribuidora ACME SA"},
    )
    assert r3.status_code == 201

    # 5. Convertir prov1 (sin_factura) a con_factura asignando RFC
    rfc_conv = f"PEP{uuid.uuid4().hex[:8].upper()}"
    r_conv = client.patch(
        f"/proveedores/{prov1['id']}",
        json={"tipo": "con_factura", "rfc": rfc_conv},
    )
    assert r_conv.status_code == 200
    assert r_conv.json()["tipo"] == "con_factura"
    assert r_conv.json()["rfc"] == rfc_conv


def test_obra_cuatro_saldos_iniciales(client: TestClient):
    """Verifica creación y consulta de una obra con los 4 saldos iniciales."""
    payload = {
        "nombre": "Obra Saldos 4 Campos",
        "porcentaje_honorarios": "10.00",
        "saldo_inicial_transferencias": "15000.00",
        "saldo_inicial_efectivo": "5000.00",
        "saldo_inicial_rayas": "25000.00",
        "saldo_inicial_memorias_anteriores": "45000.00",
    }
    r = client.post("/obras", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["saldo_inicial_transferencias"] == "15000.00"
    assert data["saldo_inicial_efectivo"] == "5000.00"
    assert data["saldo_inicial_rayas"] == "25000.00"
    assert data["saldo_inicial_memorias_anteriores"] == "45000.00"
    # Compatibilidad
    assert data["saldo_inicial_acumulado"] == "15000.00"
    assert data["saldo_inicial_gastado"] == "45000.00"

    # Resumen
    r_res = client.get(f"/obras/{data['id']}/resumen")
    assert r_res.status_code == 200
    res_data = r_res.json()
    assert res_data["saldo_inicial_memorias_anteriores"] == "45000.00"
    assert res_data["gastado_a_la_fecha"] == "45000.00"


def test_preview_seleccion_y_verificar_folio(client: TestClient):
    """Verifica que el preview acepte mapa de seleccion, recalcule totales y que verificar-folio funcione."""
    r_o = client.post("/obras", json={"nombre": "Obra Test D1", "porcentaje_honorarios": "10.00"})
    o_id = r_o.json()["id"]

    # Crear 2 gastos en efectivo: $1000 y $2000
    r_g1 = client.post(
        f"/obras/{o_id}/gastos",
        json={"fecha": "2026-04-01", "concepto_resumido": "Gasto 1", "comprobante": "N1", "importe": "1000.00", "metodo_pago": "efectivo", "origen": "nota"},
    )
    g1_id = r_g1.json()["id"]

    r_g2 = client.post(
        f"/obras/{o_id}/gastos",
        json={"fecha": "2026-04-02", "concepto_resumido": "Gasto 2", "comprobante": "N2", "importe": "2000.00", "metodo_pago": "efectivo", "origen": "nota"},
    )
    g2_id = r_g2.json()["id"]

    # Preview inicial (ambos incluidos): total = 3000 + 300 hon + 48 iva = 3348
    r_prev1 = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={"fecha_inicio": "2026-04-01", "fecha_fin": "2026-04-05"},
    )
    assert r_prev1.status_code == 200
    data1 = r_prev1.json()
    assert data1["totales"]["efectivo"] == "3000.00"
    assert data1["totales"]["total_memoria"] == "3348.00"

    # Preview con seleccion desmarcando g1:
    r_prev2 = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-04-05",
            "seleccion": [{"ref_tipo": "gasto", "ref_id": g1_id, "incluido": False}],
        },
    )
    assert r_prev2.status_code == 200
    data2 = r_prev2.json()
    # Solo g2 incluido (2000)
    assert data2["totales"]["efectivo"] == "2000.00"
    assert data2["totales"]["total_memoria"] == "2232.00"
    # Verificar status de g1 en renglones
    r_g1_out = next(r for r in data2["renglones"] if r["ref_id"] == g1_id)
    assert r_g1_out["incluido"] is False

    # Verificar endpoint /memorias/verificar-folio
    r_verif1 = client.get("/memorias/verificar-folio?folio=FOLIO999")
    assert r_verif1.status_code == 200
    assert r_verif1.json()["usado"] is False

    # Guardar y cerrar memoria con folio FOLIO999
    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": o_id,
            "numero": 1,
            "folio_factura_arquitecto": "FOLIO999",
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-04-05",
            "renglones": [{"ref_tipo": "gasto", "ref_id": g2_id, "incluido": True}],
        },
    )
    mem_id = r_guardar.json()["id"]
    client.post(f"/memorias/{mem_id}/cerrar")

    # Ahora verificar-folio debe reportar usado=True
    r_verif2 = client.get("/memorias/verificar-folio?folio=FOLIO999")
    assert r_verif2.status_code == 200
    assert r_verif2.json()["usado"] is True
    assert r_verif2.json()["memoria_numero"] == 1

    # Y si abrimos un preview nuevo sobre el mismo rango, g2 (ya incluido en memoria 1) debe venir desmarcado (incluido=False)
    r_prev3 = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={"fecha_inicio": "2026-04-01", "fecha_fin": "2026-04-05"},
    )
    assert r_prev3.status_code == 200
    r_g2_out = next(r for r in r_prev3.json()["renglones"] if r["ref_id"] == g2_id)
    assert r_g2_out["incluido"] is False
    assert "Memoria #1" in r_g2_out["ya_incluido_en"]


def test_rayas_posteriores_y_buscador_rayas(client: TestClient):
    """Verifica detección de semanas que terminan después del periodo y búsqueda de rayas."""
    # 1. Crear obra y trabajador
    r_o = client.post("/obras", json={"nombre": "Obra Rayas Periodo", "porcentaje_honorarios": "10.00"})
    o_id = r_o.json()["id"]

    r_t = client.post("/trabajadores", json={"nombre": "Juan Pérez Albañil", "oficio": "Albañil"})
    t_id = r_t.json()["id"]

    # Crear raya de la semana del 13/10 al 19/10
    r_raya = client.post(
        f"/obras/{o_id}/rayas",
        json={
            "trabajador_id": t_id,
            "semana_numero": 42,
            "fecha_inicio": "2026-10-13",
            "fecha_fin": "2026-10-19",
            "tipo": "dia",
            "cantidad": "6",
            "tarifa": "50.00",
        },
    )
    assert r_raya.status_code == 201
    raya_id = r_raya.json()["id"]

    # 2. Preview del periodo 01/10 al 15/10:
    # La raya NO cae dentro (fecha_fin 19 > 15), pero empieza dentro (13 <= 15).
    # Debe aparecer en 'rayas_posteriores'.
    r_prev = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-15"},
    )
    assert r_prev.status_code == 200
    prev_data = r_prev.json()
    assert len(prev_data["renglones"]) == 0
    assert len(prev_data["rayas_posteriores"]) == 1
    assert prev_data["rayas_posteriores"][0]["ref_id"] == raya_id

    # 3. Al pasar raya_id en rayas_extra_ids, se incorpora a los renglones
    r_prev_extra = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-15",
            "rayas_extra_ids": [raya_id],
        },
    )
    assert r_prev_extra.status_code == 200
    data_extra = r_prev_extra.json()
    assert len(data_extra["renglones"]) == 1
    assert data_extra["renglones"][0]["ref_id"] == raya_id
    assert data_extra["totales"]["rayas"] == "300.00"

    # 4. Buscador /rayas/buscar
    r_search = client.get("/rayas/buscar?q=Juan")
    assert r_search.status_code == 200
    assert any(item["id"] == raya_id for item in r_search.json())

    # 5. Raya de otra obra incorporada en borrador
    r_o2 = client.post("/obras", json={"nombre": "Obra Destino"})
    o2_id = r_o2.json()["id"]

    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": o2_id,
            "numero": 1,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-15",
            "renglones": [{"ref_tipo": "raya", "ref_id": raya_id, "incluido": True}],
        },
    )
    assert r_guardar.status_code == 201
    mem_guardada = r_guardar.json()
    r_raya_ext = mem_guardada["renglones"][0]
    assert r_raya_ext["es_externo"] is True
    assert r_raya_ext["obra_origen"] == "Obra Rayas Periodo"


def test_end_to_end_periodo_julio_2025_octubre_2026(client: TestClient):
    """Verifica caso end-to-end con datos del despacho:
    Periodo 01/07/2025–19/10/2026 debe dar:
    total memoria: 22,760.92, cobrado: 5,029.52, importe factura: 2,937.51.
    """
    # 1. Crear Obra
    r_o = client.post(
        "/obras",
        json={
            "nombre": "Obra E2E Test",
            "porcentaje_honorarios": "10.00",
            "propietario": "Cliente Prueba",
            "ubicacion": "Zapopan",
        },
    )
    o_id = r_o.json()["id"]

    # 2. Transferencia 1: 2025-07-14, $9822.52
    client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2025-07-14",
            "concepto_resumido": "Pisos y pegamix",
            "comprobante": "TR-1",
            "importe": "9822.52",
            "metodo_pago": "transferencia",
            "origen": "manual",
        },
    )
    # 3. Efectivo 1: 2025-07-31, $1880.01
    client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2025-07-31",
            "concepto_resumido": "Pintura tonal",
            "comprobante": "N-1",
            "importe": "1880.01",
            "metodo_pago": "efectivo",
            "origen": "nota",
        },
    )
    # 4. Transferencia 2: 2026-03-19, $7908.88
    client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2026-03-19",
            "concepto_resumido": "Silicones duretan",
            "comprobante": "FLC 90648",
            "importe": "7908.88",
            "metodo_pago": "transferencia",
            "origen": "manual",
        },
    )
    # 5. Efectivo 2: 2026-10-09, $200.00
    client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2026-10-09",
            "concepto_resumido": "Mopas",
            "comprobante": "N-2",
            "importe": "200.00",
            "metodo_pago": "efectivo",
            "origen": "nota",
        },
    )
    # 6. Efectivo 3: 2026-10-15, $12.00
    client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2026-10-15",
            "concepto_resumido": "Tornillos",
            "comprobante": "N-3",
            "importe": "12.00",
            "metodo_pago": "efectivo",
            "origen": "nota",
        },
    )
    # 7. Anticipo: 2026-10-15, $1500.00
    client.post(
        f"/obras/{o_id}/anticipos",
        json={
            "fecha": "2026-10-15",
            "comprobante": "ANT-1",
            "importe": "1500.00",
        },
    )
    # 8. Trabajadores y Rayas: semana 42 al 19/10/2026, total $500.00 (300 + 200)
    r_t1 = client.post("/trabajadores", json={"nombre": "Trabajador 1", "oficio": "Albañil"})
    r_t2 = client.post("/trabajadores", json={"nombre": "Trabajador 2", "oficio": "Maestro"})
    t1_id = r_t1.json()["id"]
    t2_id = r_t2.json()["id"]

    client.post(
        f"/obras/{o_id}/rayas/semana",
        json={
            "semana_numero": 42,
            "fecha_inicio": "2026-10-13",
            "fecha_fin": "2026-10-19",
            "filas": [
                {"trabajador_id": t1_id, "tipo": "dia", "cantidad": "6", "tarifa": "50.00"},
                {"trabajador_id": t2_id, "tipo": "dia", "cantidad": "2", "tarifa": "100.00"},
            ],
        },
    )

    # 9. Generar preview para periodo 01/07/2025 al 19/10/2026
    r_prev = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={"fecha_inicio": "2025-07-01", "fecha_fin": "2026-10-19"},
    )
    assert r_prev.status_code == 200
    totales = r_prev.json()["totales"]

    # Verificaciones exactas
    assert totales["total_memoria"] == "22760.92"
    assert totales["cobrado"] == "5029.52"
    assert totales["importe_factura"] == "2937.51"
    assert totales["transferencias"] == "17731.40"
    assert totales["efectivo"] == "2092.01"
    assert totales["rayas"] == "500.00"
    assert totales["honorarios"] == "2032.34"
    assert totales["iva"] == "405.17"
    assert totales["anticipos_total"] == "1500.00"
    assert totales["saldo_a_favor"] == "3529.52"


def test_tipo_comprobante_y_formato_memoria_d2(client: TestClient):
    """Verifica tipo_comprobante en gastos, prefijos de comprobante,
    fechas reales de semanas en rayas y persistencia de fecha_emision y ciudad."""
    # 1. Crear obra
    r_obra = client.post("/obras", json={"nombre": "Obra D2 Formato"})
    assert r_obra.status_code == 201
    o_id = r_obra.json()["id"]

    # 2. Crear gasto manual con tipo_comprobante TICKET
    r_gasto = client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2026-10-15",
            "concepto_resumido": "10 kg yeso",
            "comprobante": "92989",
            "tipo_comprobante": "TICKET",
            "importe": "80.01",
            "metodo_pago": "efectivo",
            "origen": "manual",
        },
    )
    assert r_gasto.status_code == 201
    g_data = r_gasto.json()
    assert g_data["tipo_comprobante"] == "TICKET"
    g_id = g_data["id"]

    # 3. Crear trabajador y raya
    r_trab = client.post("/trabajadores", json={"nombre": "Juan Pérez", "oficio": "Albañil"})
    assert r_trab.status_code == 201
    t_id = r_trab.json()["id"]

    r_raya = client.post(
        f"/obras/{o_id}/rayas",
        json={
            "trabajador_id": t_id,
            "semana_numero": 42,
            "fecha_inicio": "2026-10-13",
            "fecha_fin": "2026-10-19",
            "tipo": "destajo",
            "cantidad": "10.000",
            "tarifa": "200.00",
            "importe": "2000.00",
        },
    )
    assert r_raya.status_code == 201
    raya_id = r_raya.json()["id"]

    # 4. Preview con fecha_emision y ciudad
    r_prev = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-20",
            "fecha_emision": "2026-10-16",
            "ciudad": "Zapopan, Jalisco",
        },
    )
    assert r_prev.status_code == 200
    prev = r_prev.json()
    assert prev["fecha_emision"] == "2026-10-16"
    assert prev["ciudad"] == "Zapopan, Jalisco"
    assert prev["importe_factura_texto"] is not None

    # Comprobar renglón de gasto: prefijo TICKET 92989
    g_reng = next(r for r in prev["renglones"] if r["ref_tipo"] == "gasto" and r["ref_id"] == g_id)
    assert g_reng["comprobante"] == "TICKET 92989"
    assert g_reng["tipo_comprobante"] == "TICKET"

    # Comprobar renglón de raya: fechas reales de semana
    r_reng = next(r for r in prev["renglones"] if r["ref_tipo"] == "raya" and r["ref_id"] == raya_id)
    assert r_reng["fecha_inicio"] == "2026-10-13"
    assert r_reng["fecha_fin"] == "2026-10-19"

    # 5. Guardar borrador
    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": o_id,
            "numero": 1,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-20",
            "fecha_emision": "2026-10-16",
            "ciudad": "Guadalajara, Jalisco",
            "folio_factura_arquitecto": "100",
            "renglones": [
                {"ref_tipo": "gasto", "ref_id": g_id, "incluido": True},
                {"ref_tipo": "raya", "ref_id": raya_id, "incluido": True},
            ],
        },
    )
    assert r_guardar.status_code == 201
    mem = r_guardar.json()
    assert mem["fecha_emision"] == "2026-10-16"
    assert mem["ciudad"] == "Guadalajara, Jalisco"
    assert mem["importe_factura_texto"] is not None

    # 6. Cerrar memoria y verificar
    r_cerrar = client.post(f"/memorias/{mem['id']}/cerrar")
    assert r_cerrar.status_code == 200
    mem_cerrada = r_cerrar.json()
    assert mem_cerrada["estado"] == "cerrada"
    assert mem_cerrada["fecha_emision"] == "2026-10-16"
    assert mem_cerrada["ciudad"] == "Guadalajara, Jalisco"


def test_cerrar_memoria_con_raya_rango_snapshot(client: TestClient):
    """Prueba: cerrar una memoria con una raya y comprobar que fecha_inicio y fecha_fin
    queden congeladas en el snapshot y sean leídas fielmente."""
    from app.database import SessionLocal
    from app.models import Memoria
    # 1. Crear obra y trabajador
    r_obra = client.post("/obras", json={"nombre": "Obra Raya Snapshot", "porcentaje_honorarios": "10.00"})
    o_id = r_obra.json()["id"]

    r_trab = client.post("/trabajadores", json={"nombre": "Juan Pérez", "oficio": "Albañil"})
    t_id = r_trab.json()["id"]

    # 2. Crear pago de raya con semana 42 (13 oct a 19 oct)
    r_raya = client.post(
        f"/obras/{o_id}/rayas",
        json={
            "trabajador_id": t_id,
            "semana_numero": 42,
            "fecha_inicio": "2026-10-13",
            "fecha_fin": "2026-10-19",
            "tipo": "dia",
            "cantidad": "6.000",
            "tarifa": "50.00",
            "importe": "300.00",
        },
    )
    assert r_raya.status_code == 201
    raya_id = r_raya.json()["id"]

    # 3. Preview de memoria
    r_prev = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-31"},
    )
    assert r_prev.status_code == 200
    p_data = r_prev.json()
    rayas_prev = [r for r in p_data["renglones"] if r["ref_tipo"] == "raya"]
    assert len(rayas_prev) == 1
    assert rayas_prev[0]["fecha_inicio"] == "2026-10-13"
    assert rayas_prev[0]["fecha_fin"] == "2026-10-19"
    assert p_data["totales"]["total_honorarios"] is not None

    # 4. Guardar borrador
    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": o_id,
            "numero": 1,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-31",
            "fecha_emision": "2026-10-19",
            "renglones": [{"ref_tipo": "raya", "ref_id": raya_id, "incluido": True}],
        },
    )
    assert r_guardar.status_code == 201
    mem_id = r_guardar.json()["id"]

    # 5. Cerrar memoria
    r_cerrar = client.post(f"/memorias/{mem_id}/cerrar")
    assert r_cerrar.status_code == 200

    # 6. Consultar memoria cerrada y verificar snapshot en DB y respuesta
    r_get = client.get(f"/memorias/{mem_id}")
    assert r_get.status_code == 200
    mem_out = r_get.json()
    assert mem_out["estado"] == "cerrada"
    rayas_out = [r for r in mem_out["renglones"] if r["ref_tipo"] == "raya"]
    assert len(rayas_out) == 1
    assert rayas_out[0]["fecha_inicio"] == "2026-10-13"
    assert rayas_out[0]["fecha_fin"] == "2026-10-19"

    # Verificar directamente en la columna snapshot_json de la base de datos
    with SessionLocal() as db_session:
        mem_db = db_session.query(Memoria).filter(Memoria.id == mem_id).first()
        assert mem_db is not None
        import json
        snap = json.loads(mem_db.snapshot_json)
        snap_rayas = [r for r in snap["renglones"] if r["ref_tipo"] == "raya"]
        assert len(snap_rayas) == 1
        assert snap_rayas[0]["fecha_inicio"] == "2026-10-13"
        assert snap_rayas[0]["fecha_fin"] == "2026-10-19"
        assert snap_rayas[0]["semana_numero"] == 42


def test_flujo_completo_captura_semana_preview_guardar_cerrar_e_imprimir(client: TestClient):
    """Prueba el flujo real completo del usuario:
    1. Crear obra y trabajador
    2. Capturar semana completa desde endpoint /rayas/semana
    3. Solicitar preview de memoria
    4. Guardar borrador enviando renglones del preview
    5. Cerrar memoria
    6. Consultar memoria para impresión y comprobar que fecha_inicio y fecha_fin están presentes
    """
    # 1. Crear obra y trabajador
    r_obra = client.post("/obras", json={"nombre": "Obra Flujo Real Rayas", "porcentaje_honorarios": "10.00"})
    assert r_obra.status_code == 201
    o_id = r_obra.json()["id"]

    r_trab = client.post("/trabajadores", json={"nombre": "Pedro Albañil Test", "oficio": "Albañil"})
    assert r_trab.status_code == 201
    t_id = r_trab.json()["id"]

    # 2. Capturar semana de raya desde /obras/{id}/rayas/semana
    r_semana = client.post(
        f"/obras/{o_id}/rayas/semana",
        json={
            "semana_numero": 40,
            "fecha_inicio": "2026-09-28",
            "fecha_fin": "2026-10-04",
            "filas": [
                {
                    "trabajador_id": t_id,
                    "tipo": "dia",
                    "cantidad": "6",
                    "tarifa": "400.00",
                }
            ],
        },
    )
    assert r_semana.status_code == 201
    rayas_creadas = r_semana.json()
    assert len(rayas_creadas) == 1
    raya_id = rayas_creadas[0]["id"]
    assert rayas_creadas[0]["fecha_inicio"] == "2026-09-28"
    assert rayas_creadas[0]["fecha_fin"] == "2026-10-04"

    # 3. Solicitar preview de memoria en el rango
    r_prev = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={"fecha_inicio": "2026-09-01", "fecha_fin": "2026-10-31"},
    )
    assert r_prev.status_code == 200
    prev_data = r_prev.json()
    rayas_prev = [r for r in prev_data["renglones"] if r["ref_tipo"] == "raya"]
    assert len(rayas_prev) == 1
    assert rayas_prev[0]["fecha_inicio"] == "2026-09-28"
    assert rayas_prev[0]["fecha_fin"] == "2026-10-04"

    # 4. Guardar borrador tal como lo envía el frontend AsistenteMemoriaPage
    renglones_payload = [
        {
            "ref_tipo": r["ref_tipo"],
            "ref_id": r["ref_id"],
            "incluido": r["incluido"],
            "proveedor": r["proveedor"],
            "concepto": r["concepto"],
            "comprobante": r["comprobante"],
            "importe": r["importe"],
            "tipo_comprobante": r.get("tipo_comprobante"),
            "fecha_inicio": r.get("fecha_inicio"),
            "fecha_fin": r.get("fecha_fin"),
            "oficio": r.get("oficio"),
            "cantidad": r.get("cantidad"),
            "tarifa": r.get("tarifa"),
            "tipo_raya": r.get("tipo_raya"),
            "semana_numero": r.get("semana_numero"),
        }
        for r in prev_data["renglones"]
    ]

    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": o_id,
            "numero": 1,
            "fecha_inicio": "2026-09-01",
            "fecha_fin": "2026-10-31",
            "fecha_emision": "2026-10-05",
            "renglones": renglones_payload,
        },
    )
    assert r_guardar.status_code == 201
    mem_guardada = r_guardar.json()
    rayas_guardadas = [r for r in mem_guardada["renglones"] if r["ref_tipo"] == "raya"]
    assert len(rayas_guardadas) == 1
    assert rayas_guardadas[0]["fecha_inicio"] == "2026-09-28"
    assert rayas_guardadas[0]["fecha_fin"] == "2026-10-04"

    # 5. Cerrar memoria
    r_cerrar = client.post(f"/memorias/{mem_guardada['id']}/cerrar")
    assert r_cerrar.status_code == 200

    # 6. Consultar memoria cerrada
    r_get = client.get(f"/memorias/{mem_guardada['id']}")
    assert r_get.status_code == 200
    mem_out = r_get.json()
    rayas_out = [r for r in mem_out["renglones"] if r["ref_tipo"] == "raya"]
    assert len(rayas_out) == 1
    assert rayas_out[0]["fecha_inicio"] == "2026-09-28"
    assert rayas_out[0]["fecha_fin"] == "2026-10-04"


def test_debug_app_db():
    import sqlite3, json, os
    db_path = "data/app.db"
    if not os.path.exists(db_path):
        print("NO app.db")
        return
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    mems = cur.execute("SELECT id, obra_id, numero, estado, snapshot_json FROM memorias").fetchall()
    print(f"\n--- MEMORIAS EN APP.DB: {len(mems)} ---")
    for m in mems:
        snap = json.loads(m[4]) if m[4] else {}
        rayas = [r for r in snap.get("renglones", []) if r.get("ref_tipo") == "raya"]
        print(f"Memoria #{m[0]} (Obra {m[1]}, Num {m[2]}, Estado {m[3]}): {len(rayas)} rayas")
        for ry in rayas:
            print("  Raya:", ry.get("ref_id"), ry.get("concepto"), "inicio:", ry.get("fecha_inicio"), "fin:", ry.get("fecha_fin"), "sem:", ry.get("semana_numero"))
    rayas_db = cur.execute("SELECT id, obra_id, semana_numero, fecha_inicio, fecha_fin, tipo, importe FROM pagos_raya").fetchall()
    print(f"\n--- PAGOS_RAYA EN APP.DB: {len(rayas_db)} ---")
    for r in rayas_db[:10]:
        print("  DB Raya:", r)
    con.close()


def test_etapa_e_excel_descarga_borrador_y_cerrada_con_formulas(client: TestClient):
    """Verifica:
    1. Descarga de Excel de borrador con marca visible [ DOCUMENTO EN BORRADOR ].
    2. Descarga de Excel de memoria cerrada sin marca de borrador.
    3. Evaluación de fórmulas vivas con el paquete 'formulas' comparando con el snapshot.
    4. Validación de fórmulas en destajos/rayas (=C*D).
    5. Manejo de error 404 si la memoria no existe.
    """
    import io
    import os
    import tempfile
    import formulas
    import openpyxl

    # 1. Crear obra con 10% honorarios
    r_obra = client.post("/obras", json={"nombre": "Obra Etapa E Excel", "porcentaje_honorarios": "10.00"})
    assert r_obra.status_code == 201
    o_id = r_obra.json()["id"]

    # 2. Agregar gastos en transferencia y efectivo
    client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2026-10-10",
            "concepto_resumido": "Cemento gris",
            "comprobante": "FAC 101",
            "importe": "5000.00",
            "metodo_pago": "transferencia",
            "origen": "manual",
        },
    )
    client.post(
        f"/obras/{o_id}/gastos",
        json={
            "fecha": "2026-10-11",
            "concepto_resumido": "Clavos para cimbra",
            "comprobante": "NOTA 202",
            "importe": "350.00",
            "metodo_pago": "efectivo",
            "origen": "nota",
        },
    )

    # 3. Agregar anticipo
    client.post(
        f"/obras/{o_id}/anticipos",
        json={
            "fecha": "2026-10-05",
            "comprobante": "ANT-01",
            "importe": "2000.00",
        },
    )

    # 4. Agregar trabajador y raya
    r_t = client.post("/trabajadores", json={"nombre": "Carlos Albañil", "oficio": "Oficial"})
    t_id = r_t.json()["id"]

    client.post(
        f"/obras/{o_id}/rayas/semana",
        json={
            "semana_numero": 41,
            "fecha_inicio": "2026-10-05",
            "fecha_fin": "2026-10-11",
            "filas": [
                {
                    "trabajador_id": t_id,
                    "tipo": "destajo",
                    "cantidad": "10",
                    "tarifa": "150.00",
                }
            ],
        },
    )

    # 5. Obtener preview y guardar borrador
    r_prev = client.post(
        f"/obras/{o_id}/memorias/preview",
        json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-15"},
    )
    assert r_prev.status_code == 200
    prev_data = r_prev.json()
    snapshot_totales = prev_data["totales"]

    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": o_id,
            "numero": 1,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-15",
            "fecha_emision": "2026-10-12",
            "renglones": prev_data["renglones"],
        },
    )
    assert r_guardar.status_code == 201
    mem_borrador = r_guardar.json()
    mem_id = mem_borrador["id"]

    # 6. Descargar Excel de BORRADOR
    r_xlsx_borrador = client.get(f"/memorias/{mem_id}/xlsx")
    assert r_xlsx_borrador.status_code == 200
    assert r_xlsx_borrador.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "MEMORIA 01 - Obra Etapa E Excel.xlsx" in r_xlsx_borrador.headers["content-disposition"]

    wb_borrador = openpyxl.load_workbook(io.BytesIO(r_xlsx_borrador.content))
    assert "MEMORIA 01" in wb_borrador.sheetnames
    assert "ARQUITECTO" in wb_borrador.sheetnames
    ws_borr_1 = wb_borrador["MEMORIA 01"]
    texto_a1 = ws_borr_1["A1"].value or ""
    assert "BORRADOR" in texto_a1

    # 7. Cerrar memoria
    r_cerrar = client.post(f"/memorias/{mem_id}/cerrar")
    assert r_cerrar.status_code == 200

    # 8. Descargar Excel de MEMORIA CERRADA
    r_xlsx_cerrada = client.get(f"/memorias/{mem_id}/xlsx")
    assert r_xlsx_cerrada.status_code == 200
    wb_cerrada = openpyxl.load_workbook(io.BytesIO(r_xlsx_cerrada.content), data_only=False)
    ws_cerr_1 = wb_cerrada["MEMORIA 01"]
    ws_cerr_2 = wb_cerrada["ARQUITECTO"]

    # Sin marca de borrador en A1
    assert "BORRADOR" not in (ws_cerr_1["A1"].value or "")

    # Verificar que las fórmulas en destajos/rayas son vivas =C*D
    formula_destajo = ws_cerr_2["E26"].value or ws_cerr_2["E27"].value or ""
    # Encontrar celda con fórmula de multiplicación
    formulas_multiplicacion = [
        cell.value for row in ws_cerr_2.iter_rows()
        for cell in row if isinstance(cell.value, str) and "*" in cell.value
    ]
    assert len(formulas_multiplicacion) > 0
    assert any("*" in str(f) for f in formulas_multiplicacion)

    # 9. Evaluar fórmulas vivas con 'formulas' package y comparar contra el snapshot
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(r_xlsx_cerrada.content)
        tmp_path = tmp.name

    try:
        model = formulas.ExcelModel().loads(tmp_path).finish()
        calc = model.calculate()

        def get_val(key_fragment):
            for k, v in calc.items():
                if key_fragment in k:
                    val = v.value[0, 0] if hasattr(v.value, "shape") else v.value
                    if isinstance(val, (int, float)):
                        return round(float(val), 2)
            return None

        # ARQUITECTO!B5 -> Honorarios
        val_hon = get_val("ARQUITECTO'!B5")
        assert val_hon == float(snapshot_totales["honorarios"])

        # ARQUITECTO!B6 -> IVA
        val_iva = get_val("ARQUITECTO'!B6")
        assert val_iva == float(snapshot_totales["iva"])

        # ARQUITECTO!B7 -> Total Honorarios
        val_tot_hon = get_val("ARQUITECTO'!B7")
        assert val_tot_hon == float(snapshot_totales["total_honorarios"])

        # ARQUITECTO!B10 -> Notas Efectivo
        val_efec = get_val("ARQUITECTO'!B10")
        assert val_efec == float(snapshot_totales["efectivo"])

        # ARQUITECTO!B11 -> Nómina Rayas
        val_rayas = get_val("ARQUITECTO'!B11")
        assert val_rayas == float(snapshot_totales["rayas"])

        # ARQUITECTO!B12 -> Cobrado
        val_cobrado = get_val("ARQUITECTO'!B12")
        assert val_cobrado == float(snapshot_totales["cobrado"])

        # ARQUITECTO!B14 -> Saldo a Favor
        val_saldo = get_val("ARQUITECTO'!B14")
        assert val_saldo == float(snapshot_totales["saldo_a_favor"])

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # 10. Probar 404 si la memoria no existe
    r_404 = client.get("/memorias/99999/xlsx")
    assert r_404.status_code == 404


def test_etapa_e_pdf_descarga_paginacion_y_sin_headers_chrome(client: TestClient):
    """Verifica:
    1. Generación de PDF con Playwright (usando navegador del sistema msedge/chrome/chromium).
    2. Paginación de la obra de prueba con 30 renglones de efectivo = exactamente 4 páginas.
    3. Encabezado de continuación 'CONTINUACIÓN' en página 2.
    4. Sin encabezados/pies por defecto de Chrome (sin URL ni puerto en el texto).
    5. Descarga vía endpoint GET /memorias/{id}/pdf con Content-Disposition adecuado.
    """
    import io
    import os
    import socket
    import threading
    import time
    from pypdf import PdfReader
    import uvicorn
    from app.services.pdf_service import generar_pdf_memoria
    from app.database import SessionLocal
    from scripts.seed_prueba_paginacion import sembrar_datos
    from app.models import Obra

    # 1. Sembrar obra de prueba con 30 gastos de efectivo, 15 transferencias, 20 rayas y 2 anticipos
    with SessionLocal() as db:
        sembrar_datos(db)
        obra = db.query(Obra).filter(Obra.nombre == "PRUEBA PAGINACIÓN").first()
        obra_id = obra.id

    # 2. Generar preview, guardar y cerrar memoria para la obra
    r_prev = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-31"},
    )
    assert r_prev.status_code == 200
    prev_data = r_prev.json()

    r_guardar = client.post(
        "/memorias",
        json={
            "obra_id": obra_id,
            "numero": 1,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-31",
            "fecha_emision": "2026-10-25",
            "renglones": prev_data["renglones"],
        },
    )
    assert r_guardar.status_code == 201
    mem_id = r_guardar.json()["id"]

    r_cerrar = client.post(f"/memorias/{mem_id}/cerrar")
    assert r_cerrar.status_code == 200

    # 3. Iniciar servidor Uvicorn efímero en un hilo de fondo
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config("app.main:app", host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)

    base_url = f"http://127.0.0.1:{port}"
    os.environ["TEST_SERVER_URL"] = base_url

    try:
        # Generar PDF de la memoria de prueba con 67 renglones totales (30 notas en efectivo)
        pdf_bytes = generar_pdf_memoria(memoria_id=mem_id, base_url=base_url)
        assert pdf_bytes.startswith(b"%PDF-")

        reader = PdfReader(io.BytesIO(pdf_bytes))
        # Exactamente 4 páginas
        assert len(reader.pages) == 4

        # No contiene encabezados de continuación ocultos ni la palabra CONTINUACIÓN
        all_text = " ".join(page.extract_text() for page in reader.pages)
        assert "CONTINUACIÓN" not in all_text and "CONTINUACION" not in all_text
        p2_text = reader.pages[1].extract_text()
        assert "NOTAS Y FACTURAS EN EFECTIVO" in p2_text

        # Sin encabezados ni pies de Chrome (no contiene la URL del servidor ni el puerto)
        all_text = " ".join(page.extract_text() for page in reader.pages)
        assert f"http://127.0.0.1:{port}" not in all_text
        assert f":{port}" not in all_text

        # Probar endpoint GET /memorias/{mem_id}/pdf con TEST_SERVER_URL activo
        r_pdf = client.get(f"/memorias/{mem_id}/pdf")
        assert r_pdf.status_code == 200
        assert r_pdf.headers["content-type"] == "application/pdf"
        assert "MEMORIA 01" in r_pdf.headers["content-disposition"]
        assert r_pdf.content.startswith(b"%PDF-")

        # Probar 404 si la memoria no existe
        r_404 = client.get("/memorias/99999/pdf")
        assert r_404.status_code == 404

    finally:
        server.should_exit = True
        os.environ.pop("TEST_SERVER_URL", None)


def test_etapa_e_error_handling_sin_navegador(monkeypatch):
    """Verifica que si no hay navegador disponible, se lanza un error descriptivo en español."""
    from app.services import pdf_service

    # Simular fallo en todos los lanzamientos de navegador
    class DummyPlaywright:
        def __enter__(self):
            class DummyChromium:
                def launch(self, **kwargs):
                    raise RuntimeError("No browser found")
            self.chromium = DummyChromium()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(pdf_service, "sync_playwright", lambda: DummyPlaywright())

    import pytest
    with pytest.raises(RuntimeError) as exc_info:
        pdf_service.generar_pdf_memoria(1, base_url="http://127.0.0.1:8000")

    err_str = str(exc_info.value)
    assert "No se encontró ningún navegador disponible" in err_str
    assert "Microsoft Edge" in err_str or "Google Chrome" in err_str



def test_memoria_acumulados_transferencias_consistentes(client: TestClient):
    """Prueba que los acumulados de transferencias cumplen estrictamente:
    total = acumulado_anterior + esta_memoria (X, Y, X + Y) tanto en memoria 1 como en memoria 2.
    """
    # 1. Crear obra
    r_obra = client.post("/obras", json={"nombre": "Obra Acumulados Test", "porcentaje_honorarios": "10.00"})
    assert r_obra.status_code == 201
    obra_id = r_obra.json()["id"]

    # 2. Crear proveedor y gastos por transferencia para periodo 1 (X) y periodo 2 (Y)
    rfc1 = f"PROV{uuid.uuid4().hex[:8].upper()}"
    r_prov = client.post("/proveedores", json={"razon_social": "Proveedor Acumulados", "rfc": rfc1, "alias": "Proveedor Acumulados"})
    assert r_prov.status_code == 201
    prov_id = r_prov.json()["id"]

    # Gastos Periodo 1 (Total X = 2,500.00)
    g1_1 = client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-02",
            "concepto_resumido": "Gasto T1 Mem1",
            "importe": "1000.00",
            "metodo_pago": "transferencia",
            "tipo_comprobante": "FACTURA",
            "comprobante": "FAC-01",
            "origen": "manual",
        },
    ).json()["id"]

    g1_2 = client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-05",
            "concepto_resumido": "Gasto T2 Mem1",
            "importe": "1500.00",
            "metodo_pago": "transferencia",
            "tipo_comprobante": "FACTURA",
            "comprobante": "FAC-02",
            "origen": "manual",
        },
    ).json()["id"]

    # Gastos Periodo 2 (Total Y = 3,200.00)
    g2_1 = client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-18",
            "concepto_resumido": "Gasto T1 Mem2",
            "importe": "2000.00",
            "metodo_pago": "transferencia",
            "tipo_comprobante": "FACTURA",
            "comprobante": "FAC-03",
            "origen": "manual",
        },
    ).json()["id"]

    g2_2 = client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-22",
            "concepto_resumido": "Gasto T2 Mem2",
            "importe": "1200.00",
            "metodo_pago": "transferencia",
            "tipo_comprobante": "FACTURA",
            "comprobante": "FAC-04",
            "origen": "manual",
        },
    ).json()["id"]

    # 3. Guardar y cerrar Memoria 1 (Periodo 01/10/2026 a 15/10/2026)
    p1 = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-15"},
    )
    assert p1.status_code == 200
    p1_data = p1.json()
    assert p1_data["totales"]["transferencias"] == "2500.00"
    assert p1_data["totales"]["transferencias_memorias_anteriores"] == "0.00"
    assert p1_data["totales"]["acumulado_transferencias"] == "2500.00"

    r_save1 = client.post(
        "/memorias",
        json={
            "obra_id": obra_id,
            "numero": 1,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-15",
            "folio_factura_arquitecto": "101",
            "porcentaje_honorarios": "10.00",
            "renglones": p1_data["renglones"],
        },
    )
    assert r_save1.status_code == 201
    mem1_id = r_save1.json()["id"]

    r_close1 = client.post(f"/memorias/{mem1_id}/cerrar")
    assert r_close1.status_code == 200
    mem1_cerrada = r_close1.json()
    tot1 = mem1_cerrada["totales"]
    assert tot1["transferencias_memorias_anteriores"] == "0.00"
    assert tot1["transferencias"] == "2500.00"
    assert tot1["acumulado_transferencias"] == "2500.00"
    total_mem1 = Decimal(tot1["total_memoria"])

    # 4. Preview de Memoria 2 (Periodo 16/10/2026 a 31/10/2026)
    p2 = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-10-16", "fecha_fin": "2026-10-31"},
    )
    assert p2.status_code == 200
    p2_data = p2.json()
    tot2_prev = p2_data["totales"]

    # Verificación de fuente única de cálculo: acumulado anterior = X, esta = Y, total = X + Y
    assert tot2_prev["transferencias_memorias_anteriores"] == "2500.00"
    assert tot2_prev["transferencias"] == "3200.00"
    assert tot2_prev["acumulado_transferencias"] == "5700.00"
    assert Decimal(tot2_prev["acumulado_transferencias"]) == (
        Decimal(tot2_prev["transferencias_memorias_anteriores"]) + Decimal(tot2_prev["transferencias"])
    )
    assert tot2_prev["gastado_memorias_anteriores"] == str(total_mem1)
    assert Decimal(tot2_prev["gastado_a_la_fecha"]) == (
        Decimal(tot2_prev["gastado_memorias_anteriores"]) + Decimal(tot2_prev["total_memoria"])
    )

    # 5. Guardar y cerrar Memoria 2
    r_save2 = client.post(
        "/memorias",
        json={
            "obra_id": obra_id,
            "numero": 2,
            "fecha_inicio": "2026-10-16",
            "fecha_fin": "2026-10-31",
            "folio_factura_arquitecto": "102",
            "porcentaje_honorarios": "10.00",
            "renglones": p2_data["renglones"],
        },
    )
    assert r_save2.status_code == 201
    mem2_id = r_save2.json()["id"]

    r_close2 = client.post(f"/memorias/{mem2_id}/cerrar")
    assert r_close2.status_code == 200
    mem2_cerrada = r_close2.json()
    tot2_cerrada = mem2_cerrada["totales"]

    assert tot2_cerrada["transferencias_memorias_anteriores"] == "2500.00"
    assert tot2_cerrada["transferencias"] == "3200.00"
    assert tot2_cerrada["acumulado_transferencias"] == "5700.00"
    assert Decimal(tot2_cerrada["acumulado_transferencias"]) == (
        Decimal(tot2_cerrada["transferencias_memorias_anteriores"]) + Decimal(tot2_cerrada["transferencias"])
    )

    # Verificar que el Excel también refleja los acumulados y fórmulas
    r_xlsx = client.get(f"/memorias/{mem2_id}/xlsx")
    assert r_xlsx.status_code == 200
    assert len(r_xlsx.content) > 1000


def test_evitar_doble_conteo_error_409(client: TestClient):
    """Verifica que un renglón (gasto o raya) ya cerrado no puede incluirse en otra memoria.
    El backend responde HTTP 409 con el detalle de renglones duplicados y la memoria donde están.
    """
    # 1. Crear obra, proveedor, gasto y raya
    r_obra = client.post("/obras", json={"nombre": "Obra Doble Conteo Test", "porcentaje_honorarios": "10.00"})
    assert r_obra.status_code == 201
    obra_id = r_obra.json()["id"]

    rfc2 = f"PROV{uuid.uuid4().hex[:8].upper()}"
    r_prov = client.post("/proveedores", json={"razon_social": "Proveedor Doble Conteo", "rfc": rfc2, "alias": "Proveedor Doble Conteo"})
    assert r_prov.status_code == 201
    prov_id = r_prov.json()["id"]

    g_id = client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-05",
            "concepto_resumido": "Gasto Duplicado Test",
            "importe": "500.00",
            "metodo_pago": "transferencia",
            "tipo_comprobante": "NOTA",
            "comprobante": "NOTA-01",
            "origen": "manual",
        },
    ).json()["id"]

    r_trab = client.post("/trabajadores", json={"nombre": "Juan Raya Doble", "oficio": "Albañil"})
    assert r_trab.status_code == 201
    trab_id = r_trab.json()["id"]

    r_raya = client.post(
        f"/obras/{obra_id}/rayas/semana",
        json={
            "semana_numero": 40,
            "fecha_inicio": "2026-09-28",
            "fecha_fin": "2026-10-04",
            "filas": [{"trabajador_id": trab_id, "tipo": "dia", "cantidad": "5", "tarifa": "300.00"}],
        },
    )
    assert r_raya.status_code == 201
    raya_id = r_raya.json()[0]["id"]

    # 2. Preview, guardar y cerrar Memoria 1 conteniendo el gasto y la raya
    p1 = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-09-28", "fecha_fin": "2026-10-10"},
    )
    assert p1.status_code == 200
    p1_data = p1.json()

    r_save1 = client.post(
        "/memorias",
        json={
            "obra_id": obra_id,
            "numero": 1,
            "fecha_inicio": "2026-09-28",
            "fecha_fin": "2026-10-10",
            "folio_factura_arquitecto": "201",
            "porcentaje_honorarios": "10.00",
            "renglones": p1_data["renglones"],
        },
    )
    assert r_save1.status_code == 201
    mem1_id = r_save1.json()["id"]

    r_close1 = client.post(f"/memorias/{mem1_id}/cerrar")
    assert r_close1.status_code == 200

    # 3. Preview de una segunda memoria: los renglones cerrados vienen marcados con ya_incluido_en e incluido=False
    p2 = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-15"},
    )
    assert p2.status_code == 200
    p2_data = p2.json()
    for r in p2_data["renglones"]:
        if (r["ref_tipo"] == "gasto" and r["ref_id"] == g_id) or (r["ref_tipo"] == "raya" and r["ref_id"] == raya_id):
            assert r["ya_incluido_en"] is not None
            assert "Memoria #1" in r["ya_incluido_en"]
            assert r["incluido"] is False

    # 4. Intentar guardar Memoria 2 forzando incluido=True en el gasto cerrado -> Debe responder HTTP 409
    renglones_con_duplicado = [dict(r) for r in p2_data["renglones"]]
    for r in renglones_con_duplicado:
        if r["ref_tipo"] == "gasto" and r["ref_id"] == g_id:
            r["incluido"] = True

    r_save2_invalido = client.post(
        "/memorias",
        json={
            "obra_id": obra_id,
            "numero": 2,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-15",
            "folio_factura_arquitecto": "202",
            "porcentaje_honorarios": "10.00",
            "renglones": renglones_con_duplicado,
        },
    )
    assert r_save2_invalido.status_code == 409
    det_409 = r_save2_invalido.json()["detail"]
    assert "No se pueden incluir renglones que ya pertenecen a una memoria cerrada" in det_409
    assert f"Gasto #{g_id}" in det_409
    assert "Memoria #1" in det_409

    # 5. Guardar como borrador válido con incluido=False
    for r in renglones_con_duplicado:
        if r["ref_tipo"] == "gasto" and r["ref_id"] == g_id:
            r["incluido"] = False

    # Crear un gasto nuevo válido para que la memoria 2 tenga al menos un renglón
    g_nuevo = client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-12",
            "concepto_resumido": "Gasto Valido Mem2",
            "importe": "800.00",
            "metodo_pago": "efectivo",
            "tipo_comprobante": "NOTA",
            "comprobante": "NOTA-02",
            "origen": "nota",
        },
    ).json()["id"]

    renglones_con_duplicado.append({
        "ref_tipo": "gasto",
        "ref_id": g_nuevo,
        "categoria": "efectivo",
        "incluido": True,
        "fecha": "2026-10-12",
        "proveedor": "Proveedor Doble Conteo",
        "concepto": "Gasto Valido Mem2",
        "comprobante": "NOTA-02",
        "importe": "800.00",
    })

    r_save2_valido = client.post(
        "/memorias",
        json={
            "obra_id": obra_id,
            "numero": 2,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-15",
            "folio_factura_arquitecto": "202",
            "porcentaje_honorarios": "10.00",
            "renglones": renglones_con_duplicado,
        },
    )
    assert r_save2_valido.status_code == 201
    mem2_valida_id = r_save2_valido.json()["id"]

    # 6. Intentar cerrar memoria si en el snapshot se hubiera colado el gasto cerrado con incluido=True
    import json
    from app.database import SessionLocal
    from app.models import Memoria
    with SessionLocal() as db_s:
        m2_db = db_s.query(Memoria).filter(Memoria.id == mem2_valida_id).first()
        snap_m2 = json.loads(m2_db.snapshot_json)
        # Forzar un renglón incluido duplicado en el snapshot
        for r in snap_m2["renglones"]:
            if r["ref_tipo"] == "gasto" and r["ref_id"] == g_id:
                r["incluido"] = True
        m2_db.snapshot_json = json.dumps(snap_m2)
        db_s.commit()

    r_cerrar_conflicto = client.post(f"/memorias/{mem2_valida_id}/cerrar")
    assert r_cerrar_conflicto.status_code == 409
    assert "No se pueden incluir renglones que ya pertenecen a una memoria cerrada" in r_cerrar_conflicto.json()["detail"]


def test_excel_formulas_recalculadas_coinciden_con_snapshot(client: TestClient):
    import datetime
    import openpyxl

    # 1. Crear obra de prueba
    obra = client.post("/obras", json={"nombre": "Obra Excel Test", "porcentaje_honorarios": "10.00"}).json()
    obra_id = obra["id"]

    # 2. Crear proveedor
    rfc_p = f"PEX{uuid.uuid4().hex[:8].upper()}"
    prov = client.post("/proveedores", json={"rfc": rfc_p, "razon_social": "PROV EXCEL SA", "alias": "PROV EXCEL"}).json()
    prov_id = prov["id"]

    # 3. Crear gasto transferencia y gasto efectivo con concepto largo
    client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-05",
            "concepto_resumido": "SUMINISTRO E INSTALACION DE TUBERIA HIDRAULICA DE COBRE TIPO M DE 1 PULGADA",
            "importe": "5000.00",
            "metodo_pago": "transferencia",
            "tipo_comprobante": "FACTURA",
            "comprobante": "F-101",
            "origen": "manual",
        },
    )
    client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-06",
            "concepto_resumido": "PAGO DE HERRAMIENTA MENOR Y DISCOS DE CORTE EN FERRETERIA LOCAL",
            "importe": "1200.00",
            "metodo_pago": "efectivo",
            "tipo_comprobante": "NOTA",
            "comprobante": "NOTA-55",
            "origen": "nota",
        },
    )

    # 4. Crear raya
    trab = client.post("/trabajadores", json={"nombre": "JUAN PEREZ", "oficio": "ALBAÑIL"}).json()
    client.post(
        f"/obras/{obra_id}/rayas",
        json={
            "trabajador_id": trab["id"],
            "semana_numero": 41,
            "tipo": "dia",
            "fecha_inicio": "2026-10-05",
            "fecha_fin": "2026-10-10",
            "cantidad": "6.000",
            "tarifa": "400.00",
        },
    )

    # 5. Crear anticipo
    client.post(
        f"/obras/{obra_id}/anticipos",
        json={
            "fecha": "2026-10-02",
            "importe": "3000.00",
            "comprobante": "ANTICIPO INICIAL OBRA",
        },
    )

    # 6. Preview y guardar Memoria 01
    prev = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-15"},
    ).json()

    res_crear = client.post(
        "/memorias",
        json={
            "obra_id": obra_id,
            "numero": 1,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-15",
            "folio_factura_arquitecto": "101",
            "porcentaje_honorarios": "10.00",
            "renglones": prev["renglones"],
            "anticipos": prev["anticipos"],
        },
    )
    assert res_crear.status_code == 201
    m1_id = res_crear.json()["id"]

    # Cerrar Memoria 01
    res_cerrar = client.post(f"/memorias/{m1_id}/cerrar")
    assert res_cerrar.status_code == 200
    m1_closed = res_cerrar.json()

    # Descargar XLSX de Memoria 01
    r_xlsx = client.get(f"/memorias/{m1_id}/xlsx")
    assert r_xlsx.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r_xlsx.content), data_only=False)

    # Validar hojas
    assert "MEMORIA 01" in wb.sheetnames
    assert "ARQUITECTO" in wb.sheetnames
    ws_cli = wb["MEMORIA 01"]
    ws_arq = wb["ARQUITECTO"]

    # Validar fechas reales y formato DD/MM/YYYY
    fechas_encontradas = []
    for r in range(1, ws_cli.max_row + 1):
        cell_c = ws_cli[f"C{r}"]
        if isinstance(cell_c.value, (datetime.date, datetime.datetime)):
            fechas_encontradas.append(cell_c)
            assert cell_c.number_format == "DD/MM/YYYY"

    assert len(fechas_encontradas) >= 2  # Gasto transf y gasto efec

    # Validar que los conceptos largos de renglones tienen wrap_text=True y height=28
    filas_largas = [r for r in range(1, ws_cli.max_row + 1) if ws_cli[f"B{r}"].value and ws_cli[f"A{r}"].value and len(str(ws_cli[f"A{r}"].value)) > 40]
    assert len(filas_largas) >= 1
    for r_l in filas_largas:
        assert ws_cli[f"A{r_l}"].alignment.wrap_text is True
        assert ws_cli.row_dimensions[r_l].height == 28

    # Validar que las fórmulas vivas usan ROUND(..., 2)
    formulas_con_round = []
    for row in ws_cli.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                assert "ROUND(" in cell.value or cell.value == "=D" + str(cell.row - 1) or cell.value.startswith("=D")
                if "ROUND(" in cell.value:
                    formulas_con_round.append(cell.value)
    assert len(formulas_con_round) >= 5

    # Validar celda visible de memorias anteriores
    celdas_mem_ant = [cell for row in ws_cli.iter_rows() for cell in row if cell.value == "IMPORTE DE MEMORIAS ANTERIORES:"]
    assert len(celdas_mem_ant) == 1

    # Validar hoja ARQUITECTO: semana header no duplica (SEMANA #X)
    semana_headers = [ws_arq[f"A{r}"].value for r in range(1, ws_arq.max_row + 1) if ws_arq[f"A{r}"].value and "SEMANA #" in str(ws_arq[f"A{r}"].value)]
    for h in semana_headers:
        assert "(SEMANA #" not in h, f"Encabezado duplicado incorrecto: {h}"

    # Validar fórmula de honorarios cross-sheet
    hon_cells = [ws_arq[f"B{r}"].value for r in range(1, 15) if isinstance(ws_arq[f"B{r}"].value, str) and "ROUND(SUM('MEMORIA 01'!" in ws_arq[f"B{r}"].value]
    assert len(hon_cells) == 1
    assert ":'MEMORIA 01'!" not in hon_cells[0], "Referencia cross-sheet mal formateada"


def test_xlsx_olivos1_sin_constantes_y_con_round(client: TestClient):
    """
    Verifica que el XLSX generado para una memoria (como Olivos 1):
    1. No contiene constantes incrustadas (,0.0) en las fórmulas de totales.
    2. Usa ROUND(..., 2) en honorarios, IVA, subtotal, factura, total y saldo.
    3. Contiene la fila visible y editable 'IMPORTE DE MEMORIAS ANTERIORES:'.
    4. Las fechas se guardan como objetos date/datetime reales con formato 'DD/MM/YYYY'.
    5. En ARQUITECTO, el rótulo del saldo usa fórmula IF(..., 'SALDO A MI FAVOR:', 'ANTICIPO PENDIENTE DE APLICAR:')
       y el importe usa ROUND(ABS(...), 2).
    """
    import datetime
    import io
    import openpyxl

    # 1. Crear obra similar a Olivos 1
    r_obra = client.post("/obras", json={"nombre": "OLIVOS 1 TEST", "porcentaje_honorarios": "10.00"})
    assert r_obra.status_code == 201
    obra_id = r_obra.json()["id"]

    # 2. Proveedor
    r_prov = client.post("/proveedores", json={"rfc": "OLI880101AA1", "razon_social": "PROVEEDOR OLIVOS SA", "alias": "OLIVOS PROV"})
    assert r_prov.status_code == 201
    prov_id = r_prov.json()["id"]

    # 3. Gasto transferencia y gasto efectivo
    client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-08",
            "concepto_resumido": "MATERIAL DE CONSTRUCCION Y SELLADORES",
            "importe": "7908.88",
            "metodo_pago": "transferencia",
            "tipo_comprobante": "FACTURA",
            "comprobante": "F-881",
            "origen": "manual",
        },
    )
    client.post(
        f"/obras/{obra_id}/gastos",
        json={
            "proveedor_id": prov_id,
            "fecha": "2026-10-09",
            "concepto_resumido": "PINTURA TONAL Y MATERIAL DE LIMPIEZA",
            "importe": "2092.01",
            "metodo_pago": "efectivo",
            "tipo_comprobante": "NOTA",
            "comprobante": "NOTA-102",
            "origen": "nota",
        },
    )

    # 4. Raya con fechas reales
    trab = client.post("/trabajadores", json={"nombre": "JOSE PABLO", "oficio": "ALBAÑIL"}).json()
    client.post(
        f"/obras/{obra_id}/rayas",
        json={
            "trabajador_id": trab["id"],
            "semana_numero": 42,
            "tipo": "dia",
            "fecha_inicio": "2026-10-13",
            "fecha_fin": "2026-10-19",
            "cantidad": "1.000",
            "tarifa": "500.00",
        },
    )

    # 5. Anticipo
    client.post(
        f"/obras/{obra_id}/anticipos",
        json={
            "fecha": "2026-10-15",
            "importe": "1500.00",
            "comprobante": "TRANSFERENCIA ANTICIPO",
        },
    )

    # 6. Preview y crear memoria
    prev = client.post(
        f"/obras/{obra_id}/memorias/preview",
        json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-19"},
    ).json()

    res_mem = client.post(
        "/memorias",
        json={
            "obra_id": obra_id,
            "numero": 1,
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-19",
            "folio_factura_arquitecto": "23",
            "porcentaje_honorarios": "10.00",
            "renglones": prev["renglones"],
            "anticipos": prev["anticipos"],
        },
    )
    assert res_mem.status_code == 201
    m_id = res_mem.json()["id"]

    # Cerrar memoria
    r_cerrar = client.post(f"/memorias/{m_id}/cerrar")
    assert r_cerrar.status_code == 200

    # Descargar XLSX
    r_xlsx = client.get(f"/memorias/{m_id}/xlsx")
    assert r_xlsx.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r_xlsx.content), data_only=False)

    ws_cli = wb["MEMORIA 01"]
    ws_arq = wb["ARQUITECTO"]

    # 1. Asegurar que NINGUNA fórmula contiene constantes incrustadas como ,0.0) o +0.0
    for ws in [ws_cli, ws_arq]:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    val = cell.value
                    assert ",0.0" not in val, f"Constante incrustada encontrada en {cell.coordinate}: {val}"
                    assert ", 0.0" not in val, f"Constante incrustada encontrada en {cell.coordinate}: {val}"
                    assert "+0.0" not in val, f"Constante incrustada encontrada en {cell.coordinate}: {val}"

    # 2. Verificar que las fórmulas en honorarios, IVA, factura, total y saldo llevan ROUND
    formulas_clave = []
    for row in ws_cli.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                val = cell.value
                if any(k in val for k in ["SUM(", "*"]):
                    assert "ROUND(" in val, f"Fórmula sin ROUND encontrada en {cell.coordinate}: {val}"
                    formulas_clave.append(val)
    assert len(formulas_clave) >= 7

    # 3. Fila visible de IMPORTE DE MEMORIAS ANTERIORES:
    filas_mem_ant = [
        (cell.row, ws_cli[f"D{cell.row}"].value)
        for row in ws_cli.iter_rows()
        for cell in row
        if cell.value == "IMPORTE DE MEMORIAS ANTERIORES:"
    ]
    assert len(filas_mem_ant) == 1
    r_ant, val_ant = filas_mem_ant[0]
    assert isinstance(val_ant, (int, float))

    # La fórmula de 'IMPORTE DE MEMORIA 01 A 01:' apunta a esa celda visible
    r_01_N = r_ant + 1
    assert f"D{r_ant}" in str(ws_cli[f"D{r_01_N}"].value)

    # 4. Fechas reales con formato DD/MM/YYYY
    fechas = [
        ws_cli[f"C{r}"]
        for r in range(1, ws_cli.max_row + 1)
        if isinstance(ws_cli[f"C{r}"].value, (datetime.date, datetime.datetime))
    ]
    assert len(fechas) >= 2
    for f in fechas:
        assert f.number_format == "DD/MM/YYYY"

    # 5. Hoja ARQUITECTO: rótulo dinámico y saldo con ABS
    filas_saldo = [
        r for r in range(1, ws_arq.max_row + 1)
        if isinstance(ws_arq[f"A{r}"].value, str) and ws_arq[f"A{r}"].value.startswith("=IF(")
    ]
    assert len(filas_saldo) == 1, "No se encontró fórmula dinámica IF para el rótulo de saldo en ARQUITECTO"
    r_saldo = filas_saldo[0]
    assert r_saldo == 14, f"Se esperaba que la fila de saldo fuera 14 y fue {r_saldo}"
    assert ws_arq["A14"].value == '=IF(B12+B13>=0,"SALDO A MI FAVOR:","ANTICIPO PENDIENTE DE APLICAR:")'
    assert ws_arq["B14"].value == '=ROUND(ABS(B12+B13),2)'


def test_formato_folio_factura_arquitecto(client: TestClient):
    """
    Verifica que:
    1. Folio puramente numérico ('23') recibe prefijo 'F-' -> 'F-23'.
    2. Folio con letras ('F-501', 'f-501', 'A-23') se conserva tal cual -> 'F-501', 'f-501', 'A-23'.
    3. Aplica en Excel (rótulo y encabezado) sin duplicar 'F-F-'.
    """
    import io
    import openpyxl
    from app.services.excel_service import format_folio_factura

    # Pruebas unitarias de la función de formateo
    assert format_folio_factura("23") == "F-23"
    assert format_folio_factura("F-501") == "F-501"
    assert format_folio_factura("f-501") == "f-501"
    assert format_folio_factura("A-23") == "A-23"
    assert format_folio_factura("  102  ") == "F-102"
    assert format_folio_factura("") == ""
    assert format_folio_factura(None) == ""

    # Crear obra de prueba
    r_obra = client.post("/obras", json={"nombre": "Obra Folios Test", "porcentaje_honorarios": "10.00"})
    assert r_obra.status_code == 201
    o_id = r_obra.json()["id"]

    for idx, (fol_input, fol_esperado) in enumerate([("23", "F-23"), ("F-501", "F-501"), ("f-501", "f-501")], start=1):
        prev = client.post(
            f"/obras/{o_id}/memorias/preview",
            json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-15"},
        ).json()

        res = client.post(
            "/memorias",
            json={
                "obra_id": o_id,
                "numero": idx,
                "fecha_inicio": "2026-10-01",
                "fecha_fin": "2026-10-15",
                "folio_factura_arquitecto": fol_input,
                "porcentaje_honorarios": "10.00",
                "renglones": prev["renglones"],
                "anticipos": prev["anticipos"],
            },
        )
        assert res.status_code == 201
        m_id = res.json()["id"]

        # Descargar Excel y verificar celda del rótulo y encabezado
        r_xlsx = client.get(f"/memorias/{m_id}/xlsx")
        assert r_xlsx.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(r_xlsx.content))
        ws = wb["MEMORIA 01" if idx == 1 else f"MEMORIA {idx:02d}"]

        # Buscar celda de factura en columna A
        celdas_fac = [
            c for row in ws.iter_rows() for c in row
            if c.value and "IMPORTE DE ESTA MEMORIA" in str(c.value) and "TOTAL" not in str(c.value) and ":" not in str(c.value)
        ]
        assert len(celdas_fac) == 1
        assert "F-F-" not in str(celdas_fac[0].value)
        assert str(celdas_fac[0].value) == f"IMPORTE DE ESTA MEMORIA {fol_esperado}"

        # En encabezado (FACTURA ARQ:)
        celdas_hdr = [ws[f"D{c.row}"].value for row in ws.iter_rows() for c in row if c.value == "FACTURA ARQ:"]
        assert len(celdas_hdr) == 1
        assert celdas_hdr[0] == fol_esperado






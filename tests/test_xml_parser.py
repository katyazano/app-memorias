from datetime import date
from decimal import Decimal

import pytest

from app.services.xml_parser import CfdiParseError, extract_cfdi_xml, resumir_concepto

UUID = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"


def cfdi(
    *, attrs='Serie="A" Folio="1234" FormaPago="03" MetodoPago="PUE"', uuid=UUID, total="1160.00",
    subtotal="1000.00", conceptos=None, emisor='Rfc="CEM120304AB1" Nombre="CEMEX SA DE CV"', ns="cfdi",
    timbre=True,
) -> bytes:
    conceptos = conceptos if conceptos is not None else [
        '<cfdi:Concepto Cantidad="10.000000" Unidad="Pieza" Descripcion="Varilla 3/8" Importe="1000.00">'
        '<cfdi:Impuestos><cfdi:Traslados><cfdi:Traslado Importe="160.00"/></cfdi:Traslados></cfdi:Impuestos>'
        "</cfdi:Concepto>"
    ]
    tim = f'<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" UUID="{uuid}"/>' if timbre else ""
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" {attrs} Fecha="2026-10-08T12:30:00" '
        f'SubTotal="{subtotal}" Total="{total}">'
        f"<cfdi:Emisor {emisor}/>"
        f'<cfdi:Conceptos>{"".join(conceptos)}</cfdi:Conceptos>'
        f"<cfdi:Complemento>{tim}</cfdi:Complemento>"
        f"</cfdi:Comprobante>"
    ).encode("utf-8")


def test_extrae_campos_basicos():
    d = extract_cfdi_xml(cfdi())
    assert d.uuid == UUID
    assert d.serie == "A" and d.folio == "1234"
    assert d.fecha == date(2026, 10, 8)
    assert d.subtotal == Decimal("1000.00")
    assert d.total == Decimal("1160.00")
    assert d.rfc_emisor == "CEM120304AB1"
    assert d.nombre_emisor == "CEMEX SA DE CV"
    assert d.forma_pago == "03" and d.metodo_pago_sat == "PUE"


def test_usa_total_con_iva_y_retenciones_sin_sumar_impuestos():
    # Total ya trae IVA 16% y retención: se toma tal cual.
    d = extract_cfdi_xml(cfdi(subtotal="1000.00", total="1123.33"))
    assert d.total == Decimal("1123.33")


def test_comprobante_serie_y_folio():
    assert extract_cfdi_xml(cfdi()).comprobante == "A 1234"
    assert extract_cfdi_xml(cfdi(attrs='Serie="FLC" Folio="90648"')).comprobante == "FLC 90648"
    assert extract_cfdi_xml(cfdi(attrs='Folio="77"')).comprobante == "77"
    assert extract_cfdi_xml(cfdi(attrs='Serie="B"')).comprobante == "B"


def test_comprobante_sin_serie_ni_folio_usa_ultimos_7_del_uuid():
    d = extract_cfdi_xml(cfdi(attrs='FormaPago="03"'))
    assert d.comprobante == "4567890"
    assert d.comprobante == UUID[-7:]


@pytest.mark.parametrize("total_val,esperado,requiere", [
    ("2000.01", "transferencia", False),
    ("5000.00", "transferencia", False),
    ("2000.00", None, True),
    ("1999.99", None, True),
    ("500.00", None, True),
])
def test_metodo_pago_sugerido_por_total(total_val, esperado, requiere):
    d = extract_cfdi_xml(cfdi(total=total_val))
    assert d.metodo_pago_sugerido == esperado
    assert d.requiere_decision_metodo_pago == requiere


def test_concepto_cantidad_unidad_descripcion():
    d = extract_cfdi_xml(cfdi())
    assert d.concepto_sugerido == "10 Pieza Varilla 3/8"


def test_concepto_varios_y_truncado_a_80_y_otros():
    cs = [f'<cfdi:Concepto Cantidad="2.500000" Unidad="Kilo" Descripcion="Material numero {i} " />' for i in range(20)]
    d = extract_cfdi_xml(cfdi(conceptos=cs))
    assert len(d.concepto_sugerido) <= 80
    assert d.concepto_sugerido.endswith("Y OTROS")
    assert d.concepto_sugerido.startswith("2.5 Kilo Material numero 0, 2.5 Kilo Material numero 1")


def test_resumir_concepto_vacio():
    assert resumir_concepto([]) == "Materiales / Servicios"


def test_no_confunde_conceptos_de_impuestos():
    # El Traslado/Retención anidados no son conceptos de primer nivel.
    assert len(extract_cfdi_xml(cfdi()).conceptos) == 1


def test_funciona_con_cfdi_33():
    xml = cfdi().replace(b"http://www.sat.gob.mx/cfd/4", b"http://www.sat.gob.mx/cfd/3")
    assert extract_cfdi_xml(xml).total == Decimal("1160.00")


@pytest.mark.parametrize(
    "xml,msg",
    [
        (b"esto no es xml", "XML válido"),
        (b"<root/>", "no es un CFDI"),
        (cfdi(timbre=False), "no está timbrado"),
        (cfdi(uuid="NO-ES-UUID"), "formato válido"),
        (cfdi(emisor='Nombre="Sin RFC"'), "RFC del emisor"),
    ],
)
def test_xml_invalidos_se_rechazan(xml, msg):
    with pytest.raises(CfdiParseError, match=msg):
        extract_cfdi_xml(xml)

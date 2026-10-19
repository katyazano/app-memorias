"""Lectura de CFDI 3.3 / 4.0.

Reglas:
- `Total` ya incluye IVA y retenciones: NO se suman impuestos.
- Sin regex "adivinadora": un XML inválido o sin timbrar se rechaza con
  `CfdiParseError` (un UUID inventado rompería la detección de duplicados).
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from app.types import money

UUID_RE = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$")
MAX_CONCEPTO = 120

LIMITE_TRANSFERENCIA = Decimal("2000.00")


class CfdiParseError(ValueError):
    """El archivo no es un CFDI utilizable."""


@dataclass
class CfdiData:
    uuid: str
    fecha: date
    serie: Optional[str]
    folio: Optional[str]
    subtotal: Decimal
    total: Decimal
    forma_pago: Optional[str]
    metodo_pago_sat: Optional[str]
    rfc_emisor: str
    nombre_emisor: str
    comprobante: str
    concepto_sugerido: str
    conceptos: List[str] = field(default_factory=list)
    metodo_pago_sugerido: Optional[str] = None
    requiere_decision_metodo_pago: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "fecha": self.fecha.isoformat(),
            "serie": self.serie,
            "folio": self.folio,
            "subtotal": str(self.subtotal),
            "total": str(self.total),
            "forma_pago": self.forma_pago,
            "metodo_pago_sat": self.metodo_pago_sat,
            "rfc_emisor": self.rfc_emisor,
            "nombre_emisor": self.nombre_emisor,
            "comprobante": self.comprobante,
            "concepto_sugerido": self.concepto_sugerido,
            "conceptos": self.conceptos,
            "metodo_pago_sugerido": self.metodo_pago_sugerido,
            "requiere_decision_metodo_pago": self.requiere_decision_metodo_pago,
        }


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _attr(elem: ET.Element, name: str) -> str:
    """Atributo sin distinguir mayúsculas (CFDI usa PascalCase)."""
    for k, v in elem.attrib.items():
        if k.lower() == name.lower():
            return (v or "").strip()
    return ""


def _decimal(value: str, campo: str) -> Decimal:
    try:
        return money(Decimal(value))
    except (InvalidOperation, ValueError):
        raise CfdiParseError(f"El atributo {campo} no es un número válido: '{value}'.")


def _cantidad_txt(raw: str) -> str:
    """'10.000000' -> '10', '2.500000' -> '2.5'."""
    try:
        d = Decimal(raw)
    except (InvalidOperation, ValueError):
        return raw
    txt = format(d.normalize(), "f")
    return txt


def resumir_concepto(conceptos: List[Dict[str, str]], limite: int = MAX_CONCEPTO) -> str:
    """'cantidad unidad descripcion' por concepto, unidos con '; ', máx. `limite`."""
    partes = []
    for c in conceptos:
        txt = " ".join(p for p in (_cantidad_txt(c["cantidad"]) if c["cantidad"] else "", c["unidad"], c["descripcion"]) if p)
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt:
            partes.append(txt)
    resumen = "; ".join(partes) or "Materiales / Servicios"
    if len(resumen) > limite:
        resumen = resumen[: limite - 3].rstrip() + "..."
    return resumen


def extract_cfdi_xml(xml_bytes: bytes) -> CfdiData:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise CfdiParseError(f"El archivo no es un XML válido: {exc}")

    if _local(root.tag) != "comprobante":
        raise CfdiParseError("El XML no es un CFDI (no se encontró el nodo Comprobante).")

    # --- UUID (TimbreFiscalDigital) ---
    uuid_val = ""
    for el in root.iter():
        if _local(el.tag) == "timbrefiscaldigital":
            uuid_val = _attr(el, "UUID").upper()
            break
    if not uuid_val:
        raise CfdiParseError("El CFDI no está timbrado (no tiene UUID en TimbreFiscalDigital).")
    if not UUID_RE.match(uuid_val):
        raise CfdiParseError(f"El UUID del CFDI no tiene un formato válido: '{uuid_val}'.")

    # --- Comprobante ---
    raw_total = _attr(root, "Total")
    if not raw_total:
        raise CfdiParseError("El CFDI no trae el atributo Total.")
    total = _decimal(raw_total, "Total")
    raw_sub = _attr(root, "SubTotal")
    subtotal = _decimal(raw_sub, "SubTotal") if raw_sub else total

    raw_fecha = _attr(root, "Fecha")
    try:
        fecha = datetime.fromisoformat(raw_fecha).date() if raw_fecha else date.today()
    except ValueError:
        raise CfdiParseError(f"La Fecha del CFDI no es válida: '{raw_fecha}'.")

    serie = _attr(root, "Serie") or None
    folio = _attr(root, "Folio") or None
    forma_pago = _attr(root, "FormaPago") or None
    metodo_pago_sat = _attr(root, "MetodoPago") or None

    # --- Emisor ---
    rfc_emisor = nombre_emisor = ""
    for el in root.iter():
        if _local(el.tag) == "emisor":
            rfc_emisor = _attr(el, "Rfc").upper()
            nombre_emisor = _attr(el, "Nombre")
            break
    if not rfc_emisor:
        raise CfdiParseError("El CFDI no trae el RFC del emisor.")

    # --- Conceptos (solo los de primer nivel, no los de impuestos/retenciones) ---
    conceptos: List[Dict[str, str]] = []
    for nodo in root:
        if _local(nodo.tag) == "conceptos":
            for c in nodo:
                if _local(c.tag) == "concepto":
                    conceptos.append(
                        {
                            "cantidad": _attr(c, "Cantidad"),
                            "unidad": _attr(c, "Unidad"),
                            "descripcion": _attr(c, "Descripcion"),
                        }
                    )

    if serie or folio:
        comprobante = " ".join(p for p in (serie, folio) if p)
    else:
        comprobante = uuid_val[-7:]

    return CfdiData(
        uuid=uuid_val,
        fecha=fecha,
        serie=serie,
        folio=folio,
        subtotal=subtotal,
        total=total,
        forma_pago=forma_pago,
        metodo_pago_sat=metodo_pago_sat,
        rfc_emisor=rfc_emisor,
        nombre_emisor=nombre_emisor or rfc_emisor,
        comprobante=comprobante,
        concepto_sugerido=resumir_concepto(conceptos),
        conceptos=[resumir_concepto([c], 255) for c in conceptos],
        metodo_pago_sugerido="transferencia" if total > LIMITE_TRANSFERENCIA else None,
        requiere_decision_metodo_pago=total <= LIMITE_TRANSFERENCIA,
    )

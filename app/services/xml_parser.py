"""Lectura de CFDI 3.3 / 4.0 y utilidades de normalización de conceptos y proveedores.

Reglas:
- `Total` ya incluye IVA y retenciones: NO se suman impuestos.
- Sin regex "adivinadora": un XML inválido o sin timbrar se rechaza con
  `CfdiParseError` (un UUID inventado rompería la detección de duplicados).
- Resumen de conceptos: sin unidades 'NA'/'ACT'/'H87', máximo 2 partidas y 'Y OTROS',
  con límite estricto de ~80 caracteres y corte en límite de palabra.
- Alias de proveedor: corte en límite de palabra y sin preposiciones finales
  (ej. 'DE LA TORRE MATERIALES PARA CONSTRUCCION' -> 'DE LA TORRE MATERIALES').
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from app.types import money

UUID_RE = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$")
MAX_CONCEPTO = 80

LIMITE_TRANSFERENCIA = Decimal("2000.00")

UNIDADES_IGNORADAS = {"NA", "N/A", "ACT", "H87"}
PREPOSICIONES = {
    "A", "AL", "DE", "DEL", "LA", "LAS", "EL", "LOS", "EN",
    "PARA", "POR", "CON", "SIN", "SOBRE", "HACIA", "DESDE", "HASTA", "ENTRE", "Y", "E", "O", "U"
}

SUFIJOS_SOCIEDAD = [
    r"\bS\.?A\.?\s+DE\s+C\.?V\.?\b",
    r"\bS\.?A\.?P\.?I\.?\s+DE\s+C\.?V\.?\b",
    r"\bS\.?\s*DE\s+R\.?L\.?\s+DE\s+C\.?V\.?\b",
    r"\bS\.?A\.?\b",
    r"\bS\.?C\.?\b",
    r"\bS\.?A\.?S\.?\b",
    r"\bS\.?C\.?P\.?\b",
    r"\bS\.?N\.?C\.?\b",
    r"\bS\.?E\.?N\.?C\.?\b",
    r"\bS\.?P\.?R\.?\s+DE\s+R\.?L\.?\b",
    r"\bSOCIEDAD\s+ANONIMA\s+DE\s+CAPITAL\s+VARIABLE\b",
    r"\bSOCIEDAD\s+DE\s+RESPONSABILIDAD\s+LIMITADA\b",
    r"\bSOCIEDAD\s+CIVIL\b",
]


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
    """Resume los conceptos de la factura:
    - Sin unidades genéricas 'NA', 'ACT', 'H87'.
    - Máximo 2 partidas y agrega ' Y OTROS' si hay más.
    - Respeta límite de caracteres (~80), cortando en límite de palabra
      sin dejar preposiciones ni signos huérfanos al final.
    """
    items: List[str] = []
    for c in conceptos:
        cant = _cantidad_txt(c.get("cantidad", "")) if c.get("cantidad") else ""
        uni = (c.get("unidad") or "").strip()
        if uni.upper() in UNIDADES_IGNORADAS:
            uni = ""
        desc = (c.get("descripcion") or "").strip()
        tokens = [p for p in (cant, uni, desc) if p]
        txt = re.sub(r"\s+", " ", " ".join(tokens)).strip()
        if txt:
            items.append(txt)

    if not items:
        return "Materiales / Servicios"

    if len(items) <= 2:
        texto_base = ", ".join(items)
        sufijo = ""
    else:
        texto_base = ", ".join(items[:2])
        sufijo = " Y OTROS"

    candidato = f"{texto_base}{sufijo}"
    if len(candidato) <= limite:
        return candidato

    # Si excede el límite, truncar en límite de palabra reservando espacio para el sufijo
    max_base = limite - len(sufijo)
    palabras = texto_base.split()
    res: List[str] = []
    curr_len = 0
    for p in palabras:
        adicional = len(p) if not res else (len(p) + 1)
        if curr_len + adicional <= max_base:
            res.append(p)
            curr_len += adicional
        else:
            break

    # Evitar terminar en preposiciones o puntuación
    while res and (res[-1].rstrip(",.;").upper() in PREPOSICIONES or res[-1] in {",", ";", "-"}):
        res.pop()

    texto_truncado = " ".join(res).rstrip(",.; ")
    return f"{texto_truncado}{sufijo}"


def sugerir_alias(razon_social: str, max_len: int = 32) -> str:
    """Genera una sugerencia de alias comercial memorable a partir de la razón social.

    Reglas:
    - Elimina regímenes societarios (S.A. DE C.V., S. DE R.L., etc.).
    - Trunca en límite de palabra si excede ~32 caracteres.
    - Nunca termina en preposición ni conjunción (ej. PARA, DE, Y).
    Ejemplo: 'DE LA TORRE MATERIALES PARA CONSTRUCCION' -> 'DE LA TORRE MATERIALES'
    """
    if not razon_social:
        return ""

    limpio = razon_social.strip()

    for suf in SUFIJOS_SOCIEDAD:
        limpio = re.sub(suf, "", limpio, flags=re.IGNORECASE)

    # Limpiar puntuación sobrante y espacios repetidos
    limpio = re.sub(r"[,.;:\-_]+$", "", limpio).strip()
    limpio = re.sub(r"\s+", " ", limpio).strip()

    if len(limpio) <= max_len:
        palabras = limpio.split()
        while palabras and palabras[-1].upper() in PREPOSICIONES:
            palabras.pop()
        return " ".join(palabras).rstrip(",.; ") or limpio

    # Truncar en límite de palabra sin partir palabras
    palabras = limpio.split()
    seleccionadas: List[str] = []
    curr_len = 0
    for p in palabras:
        adicional = len(p) if not seleccionadas else (len(p) + 1)
        if curr_len + adicional <= max_len:
            seleccionadas.append(p)
            curr_len += adicional
        else:
            break

    # Evitar terminar en preposición o conjunción
    while seleccionadas and seleccionadas[-1].upper() in PREPOSICIONES:
        seleccionadas.pop()

    resultado = " ".join(seleccionadas).rstrip(",.; ")
    return resultado or limpio[:max_len].strip()


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

import re
import uuid
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any, Dict, List, Optional


def extract_cfdi_xml(xml_bytes: bytes) -> Dict[str, Any]:
    """
    Extrae la información fiscal estructurada de un archivo CFDI XML (SAT CFDI 4.0 / 3.3).
    Utiliza xml.etree.ElementTree con soporte para múltiples espacios de nombres SAT.
    
    Retorna:
    {
        "comprobante": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
        "fecha": "YYYY-MM-DD",
        "importe": 1234.56,
        "concepto": "Descripción combinada de conceptos",
        "is_parsed_automatically": True
    }
    """
    try:
        # Decodificar manejando posibles BOM o codificaciones UTF-8 / Latin-1
        try:
            xml_text = xml_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            xml_text = xml_bytes.decode("latin1", errors="ignore")

        root = ET.fromstring(xml_text)
    except Exception as e:
        # Si falla el parseo XML estricto, intentar extracción por regex de respaldo
        return _fallback_regex_xml_extraction(xml_bytes)

    # 1. Extraer Fecha e Importe del nodo raíz (cfdi:Comprobante)
    # Los atributos del nodo raíz pueden venir con o sin mayúsculas
    raw_fecha = root.attrib.get("Fecha") or root.attrib.get("fecha") or ""
    fecha = raw_fecha.split("T")[0] if "T" in raw_fecha else (raw_fecha[:10] if raw_fecha else str(date.today()))

    raw_total = root.attrib.get("Total") or root.attrib.get("total") or "0.00"
    try:
        importe = float(raw_total)
    except (ValueError, TypeError):
        importe = 0.0

    # 2. Extraer Conceptos (cfdi:Conceptos -> cfdi:Concepto)
    conceptos_list: List[str] = []
    
    # Búsqueda independiente de namespaces iterando todos los elementos
    for elem in root.iter():
        tag_lower = elem.tag.lower()
        if tag_lower.endswith("concepto") and not tag_lower.endswith("conceptos"):
            desc = elem.attrib.get("Descripcion") or elem.attrib.get("descripcion")
            if desc and desc.strip():
                conceptos_list.append(desc.strip())

    concepto = ", ".join(conceptos_list) if conceptos_list else "Materiales / Servicios de Construcción"
    # Limitar longitud para compatibilidad con la base de datos
    concepto = concepto[:255]

    # 3. Extraer Proveedor / Emisor (cfdi:Emisor -> Nombre, Rfc)
    proveedor_nombre = ""
    proveedor_rfc = ""
    for elem in root.iter():
        tag_lower = elem.tag.lower()
        if tag_lower.endswith("emisor"):
            proveedor_nombre = elem.attrib.get("Nombre") or elem.attrib.get("nombre") or ""
            proveedor_rfc = elem.attrib.get("Rfc") or elem.attrib.get("rfc") or ""
            if proveedor_nombre or proveedor_rfc:
                break

    proveedor_final = proveedor_nombre.strip() if proveedor_nombre else (proveedor_rfc.strip() if proveedor_rfc else "PROVEEDOR GENERAL")

    # 4. Extraer Folio Fiscal (UUID) desde el TimbreFiscalDigital en Complemento
    comprobante_uuid: Optional[str] = None
    for elem in root.iter():
        if elem.tag.lower().endswith("timbrefiscaldigital"):
            uuid_val = elem.attrib.get("UUID") or elem.attrib.get("uuid")
            if uuid_val:
                comprobante_uuid = uuid_val.strip().upper()
                break

    # Si no se encontró en el nodo TimbreFiscalDigital, buscar patrón UUID en el texto completo
    if not comprobante_uuid:
        uuid_match = re.search(
            r'\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b',
            xml_text,
        )
        if uuid_match:
            comprobante_uuid = uuid_match.group(1).upper()
        else:
            comprobante_uuid = f"CFDI-{date.today().year}-{uuid.uuid4().hex[:8].upper()}"

    return {
        "comprobante": comprobante_uuid,
        "fecha": fecha if fecha else str(date.today()),
        "importe": importe,
        "concepto": concepto,
        "proveedor": proveedor_final,
        "rfc_emisor": proveedor_rfc.strip(),
        "is_parsed_automatically": True,
    }


def _fallback_regex_xml_extraction(xml_bytes: bytes) -> Dict[str, Any]:
    """Extracción de respaldo con expresiones regulares si el XML estuviera mal formado."""
    text = xml_bytes.decode("latin1", errors="ignore")
    
    # UUID
    uuid_match = re.search(r'UUID="([0-9a-fA-F\-]{36})"', text, re.IGNORECASE)
    comprobante = uuid_match.group(1).upper() if uuid_match else f"CFDI-{uuid.uuid4().hex[:8].upper()}"

    # Fecha
    fecha_match = re.search(r'Fecha="(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
    fecha = fecha_match.group(1) if fecha_match else str(date.today())

    # Total
    total_match = re.search(r'Total="([\d\.]+)"', text, re.IGNORECASE)
    try:
        importe = float(total_match.group(1)) if total_match else 0.0
    except Exception:
        importe = 0.0

    # Conceptos
    desc_matches = re.findall(r'Descripcion="([^"]+)"', text, re.IGNORECASE)
    concepto = ", ".join(desc_matches)[:255] if desc_matches else "Materiales / Servicios"

    # Emisor / Proveedor
    emisor_match = re.search(r'<(?:[a-zA-Z0-9]+:)?Emisor[^>]*Nombre="([^"]+)"', text, re.IGNORECASE)
    if not emisor_match:
        emisor_match = re.search(r'Nombre="([^"]+)"', text, re.IGNORECASE)
    proveedor = emisor_match.group(1).strip() if emisor_match else "PROVEEDOR GENERAL"

    return {
        "comprobante": comprobante,
        "fecha": fecha,
        "importe": importe,
        "concepto": concepto,
        "proveedor": proveedor,
        "is_parsed_automatically": True,
    }

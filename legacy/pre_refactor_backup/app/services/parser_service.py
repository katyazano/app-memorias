import io
import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

SPANISH_MONTHS = {
    "enero": 1, "ene": 1,
    "febrero": 2, "feb": 2,
    "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6,
    "julio": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "septiembre": 9, "sep": 9, "sept": 9, "set": 9,
    "octubre": 10, "oct": 10,
    "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12
}


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    """Extract plain text from in-memory PDF bytes using pypdf, pdfplumber, or fitz."""
    texts = []

    # 1. Try pypdf (lightweight & fast)
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        py_text = "\n".join([page.extract_text() or "" for page in reader.pages])
        if py_text.strip():
            texts.append(py_text)
    except Exception:
        pass

    # 2. Try pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            p_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
            if p_text.strip():
                texts.append(p_text)
    except Exception:
        pass

    # 3. Try PyMuPDF (fitz)
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        fz_text = "\n".join([page.get_text() or "" for page in doc])
        if fz_text.strip():
            texts.append(fz_text)
    except Exception:
        pass

    # 4. Built-in Pure-Python FlateDecode stream decompressor (zero dependencies)
    try:
        import zlib
        stream_matches = re.finditer(b'stream\r?\n(.*?)\r?\nendstream', file_bytes, re.DOTALL)
        for m in stream_matches:
            raw_chunk = m.group(1)
            try:
                decomp = zlib.decompress(raw_chunk)
            except Exception:
                try:
                    decomp = zlib.decompress(raw_chunk, -15)
                except Exception:
                    decomp = raw_chunk
            # Find Tj and TJ operators
            tjs = re.findall(rb'\((.*?)\)\s*Tj', decomp, re.DOTALL)
            for tj in tjs:
                try:
                    texts.append(tj.decode("latin1", errors="ignore"))
                except Exception:
                    pass
            tj_arrays = re.findall(rb'\[(.*?)\]\s*TJ', decomp, re.DOTALL)
            for arr in tj_arrays:
                parts = re.findall(rb'\((.*?)\)', arr, re.DOTALL)
                for p in parts:
                    try:
                        texts.append(p.decode("latin1", errors="ignore"))
                    except Exception:
                        pass
    except Exception:
        pass

    # 5. Fallback: Search directly in Latin-1 / UTF-8 decoded bytes (for Cadena Original / XML)
    try:
        raw_decoded = file_bytes.decode("latin1", errors="ignore")
        if "||" in raw_decoded or "CFDI" in raw_decoded or "Folio" in raw_decoded:
            texts.append(raw_decoded)
    except Exception:
        pass

    if texts:
        return "\n\n--- PDF STREAM ---\n\n".join(texts)

    return ""


def normalize_text(text: str) -> str:
    """Normalize unicode hyphens, dashes, and extra whitespace."""
    if not text:
        return ""
    text = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2212]', '-', text)
    return text


def extract_comprobante(text: str) -> Optional[str]:
    """
    Extracts the Folio Fiscal (UUID) as comprobante.
    Format: 8-4-4-4-12 hex characters (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX).
    """
    text_norm = normalize_text(text)

    # 1. Cadena Original Complemento SAT ||1.1|UUID|
    match = re.search(r'\|\|1\.1\|([0-9a-fA-F\-_\s]{32,45})\|', text_norm)
    if match:
        raw_uuid = re.sub(r'[^0-9a-fA-F]', '', match.group(1))
        if len(raw_uuid) >= 32:
            u = raw_uuid[:32]
            return f"{u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}".upper()

    # 2. Labeled Folio Fiscal / UUID / Folio SAT
    labeled_matches = re.findall(
        r'(?:Folio\s*Fiscal|UUID|Folio\s*SAT|Foliofiscal)[\s:]*([0-9a-fA-F\-\s]{32,60})',
        text_norm,
        re.IGNORECASE
    )
    for m in labeled_matches:
        raw_uuid = re.sub(r'[^0-9a-fA-F]', '', m)
        if len(raw_uuid) >= 32:
            u = raw_uuid[:32]
            if not u.startswith("0000100000"):  # Exclude SAT certificate serial numbers
                return f"{u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}".upper()

    # 3. Standard formatted UUID: 8-4-4-4-12
    uuid_pattern = r'\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b'
    matches = re.findall(uuid_pattern, text_norm, re.IGNORECASE)
    for m in matches:
        if not m.startswith("00000000"):
            return m.upper()

    # 4. Multi-line formatted UUID pattern with newlines/spaces between groups
    multiline_uuid = re.search(
        r'\b([0-9a-fA-F]{8})[-\s\n\r]+([0-9a-fA-F]{4})[-\s\n\r]+([0-9a-fA-F]{4})[-\s\n\r]+([0-9a-fA-F]{4})[-\s\n\r]+([0-9a-fA-F]{12})\b',
        text_norm
    )
    if multiline_uuid:
        parts = multiline_uuid.groups()
        return f"{parts[0]}-{parts[1]}-{parts[2]}-{parts[3]}-{parts[4]}".upper()

    return None


def parse_standard_date(date_str: str) -> Optional[str]:
    """Parse various date representations to standardized YYYY-MM-DD."""
    if not date_str:
        return None
    date_str = normalize_text(date_str.strip())

    # ISO / Timestamp: 2026-02-13 or 2026-02-13T09:01:29 or 2025-07-31 13:51:47
    iso_match = re.search(r'\b(20\d{2})[-/](\d{2})[-/](\d{2})\b', date_str)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}"

    # DD/MM/YYYY or DD-MM-YYYY
    dmy_match = re.search(r'\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b', date_str)
    if dmy_match:
        day = int(dmy_match.group(1))
        month = int(dmy_match.group(2))
        year = int(dmy_match.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # Spanish text date: "13 de febrero de 2026" or "13/feb/2026"
    spanish_match = re.search(r'(\d{1,2})\s*(?:de|/|-)\s*([a-zA-ZáéíóúÁÉÍÓÚ]+)\s*(?:de|/|-)?\s*(20\d{2})', date_str, re.IGNORECASE)
    if spanish_match:
        day = int(spanish_match.group(1))
        month_name = spanish_match.group(2).lower()
        year = int(spanish_match.group(3))
        month = SPANISH_MONTHS.get(month_name)
        if month and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    return None


def extract_fecha(text: str) -> Optional[str]:
    """Extracts the invoice date normalized to YYYY-MM-DD."""
    text_norm = normalize_text(text)

    # 1. Check Cadena Original for date timestamp
    cadena_match = re.search(r'\|(20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\|', text_norm)
    if cadena_match:
        return cadena_match.group(1).split("T")[0]

    # 2. Check for explicit labeled dates
    date_patterns = [
        r'(?:Fecha\s*y\s*Hora\s*de\s*emisi[oó]n|Fecha\s*de\s*emisi[oó]n|Fecha\s*Emisi[oó]n|Fecha\s*y\s*hora|Fechayhoradeemisi[oó]n)[\s:]*([^\n\r\|]{0,35})',
        r'(?:Fecha\s*de\s*certificaci[oó]n|Fecha\s*Certificaci[oó]n)[\s:]*([^\n\r\|]{0,35})',
        r'(?:Fecha|fechayhorade)[\s:]*([^\n\r\|]{0,35})',
    ]

    for pat in date_patterns:
        matches = re.finditer(pat, text_norm, re.IGNORECASE)
        for m in matches:
            val = m.group(1).strip()
            if val:
                parsed = parse_standard_date(val)
                if parsed:
                    return parsed
            snippet = text_norm[m.end() : m.end() + 40]
            parsed = parse_standard_date(snippet)
            if parsed:
                return parsed

    # 3. Fallback: Search any ISO YYYY-MM-DD date
    generic_iso = re.findall(r'\b(20\d{2})[-/](\d{2})[-/](\d{2})(?:[T\s]|\b)', text_norm)
    if generic_iso:
        for y, m, d in generic_iso:
            if 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
                return f"{y}-{m}-{d}"

    # 4. Fallback: Search DD/MM/YYYY
    generic_dmy = re.findall(r'\b(\d{1,2})[/](\d{1,2})[/](20\d{2})(?:[T\s]|\b)', text_norm)
    if generic_dmy:
        for d, m, y in generic_dmy:
            if 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
                return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    return None


def extract_importe(text: str) -> Optional[float]:
    """Extracts the Total invoice amount as a float."""
    text_norm = normalize_text(text)

    # 1. Extract from Cadena Original CFDI 4.0 if available
    cadena_match = re.search(
        r'\|(?:MXN|USD|EUR|PESOS?)\|(?:\d+(?:\.\d+)?\|)?([0-9]+\.[0-9]{2})\|[IEPNT]\|',
        text_norm,
        re.IGNORECASE
    )
    if cadena_match:
        try:
            return float(cadena_match.group(1))
        except ValueError:
            pass

    # 2. Look for Total lines
    total_patterns = [
        r'(?<!Sub)(?<!Sub\s)\b(?:Total\s*Facturado|TOTAL|Total)\s*[:]?\s*(?:MXN\s*)?\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2}))\b',
        r'(?<!Sub)(?<!Sub\s)\b(?:TOTAL|Total)\s*[:]?\s*(?:MXN\s*)?\$?\s*([0-9]+\.[0-9]{2})\b',
    ]

    for pat in total_patterns:
        matches = re.findall(pat, text_norm, re.IGNORECASE)
        if matches:
            val_str = matches[-1].replace(",", "")
            try:
                return float(val_str)
            except ValueError:
                continue

    return None


def clean_doubled_text(s: str) -> str:
    """Cleans doubled characters resulting from overlapping font glyphs (e.g. CFDI8)."""
    words = s.split()
    cleaned_words = []
    for w in words:
        if len(w) >= 4 and all(w[i] == w[i+1] for i in range(0, len(w)-1, 2)):
            cleaned_words.append("".join([w[i] for i in range(0, len(w), 2)]))
        else:
            cleaned_words.append(w)
    return " ".join(cleaned_words)


def extract_conceptos(text: str) -> List[str]:
    """Extracts item descriptions / conceptos from invoice text or Cadena Original."""
    text_norm = normalize_text(text)
    conceptos: List[str] = []

    # 1. Try parsing from Cadena Original (CFDI 4.0 format)
    cadena_40 = re.search(r'\|\|4\.0\|(.*)', text_norm, re.DOTALL)
    if cadena_40:
        raw_cadena = cadena_40.group(1).replace("\n", "").replace("\r", "")
        parts = raw_cadena.split("||")[0].split("|")
        for i, part in enumerate(parts):
            if re.fullmatch(r'\d{8}', part) and i + 1 < len(parts):
                best_candidate = None
                for candidate in parts[i+1 : min(i+8, len(parts))]:
                    c_clean = candidate.strip()
                    if not c_clean or re.fullmatch(r'[\d\.\-]+', c_clean):
                        continue
                    if re.match(r'^(?:Tasa|Cuota|Exento|PUE|PPD|MXN|USD|KGM|KG|E48|SRV|H87|PZA|XBJ|XSA|XBX|MTQ|ACT|LOTE|Contado|Transferencia|Efectivo|01|02|03|04|I|E|P|N)$', c_clean, re.IGNORECASE):
                        continue
                    if len(c_clean) > 3 and not re.fullmatch(r'^[A-Z0-9]{2,7}$', c_clean):
                        best_candidate = c_clean
                        break
                    elif not best_candidate and len(c_clean) > 2:
                        best_candidate = c_clean
                
                if best_candidate and best_candidate not in conceptos:
                    conceptos.append(best_candidate)

    if conceptos:
        return conceptos

    # 2. Table parsing from lines
    lines = text_norm.split("\n")
    in_concepts = False
    captured_lines = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        desc_inline_match = re.match(r'^(?:Descripci[oó]n|Concepto\s*/\s*Descripci[oó]n)\s+(.+)$', line_clean, re.IGNORECASE)
        if desc_inline_match:
            item_desc = desc_inline_match.group(1).strip()
            item_desc = re.sub(r'\$\s*[\d,]+\.\d{2}.*$', '', item_desc).strip()
            if item_desc and item_desc not in captured_lines and not re.search(r'^(?:Factor|Cuota|Tasa|Importe|IVA|ISR)\b', item_desc, re.IGNORECASE):
                captured_lines.append(item_desc)
                continue

        if re.search(r'\b(?:DESCRIPCI[OÓ]N|Conceptos|Articulo|Concepto\s*/\s*Descripci[oó]n|Cantidad\s+Clave|Cantidad\s+Unidad|Almacen\s+Cant|UNIDAD\s+DE\s+MEDIDA)\b', line_clean, re.IGNORECASE):
            in_concepts = True
            continue

        if in_concepts:
            if re.search(r'\b(?:Subtotal|SUB\s*TOTAL|Sub\s*Total|Sub\-Total|TOTAL\b|Total\s*Facturado|Impuestos\s*trasladados|Impuestos\s*retenidos|Impuestos\s*Trasladados|Moneda|Forma\s*de\s*pago|M[eé]todo\s*de\s*pago|Importe\s*Total|TOTAL\s*CON\s*LETRA|Sello\s*Digital|Cadena\s*Original|Efectos\s*Fiscales|Favor\s*depositar|CFDI\s*Relacionados)\b', line_clean, re.IGNORECASE):
                break

            if re.search(r'(?:Clave\s*del\s*producto|Clave\s*de\s*unidad|Valor\s*unitario|Objeto\s*impuesto|ObjetoImpuesto|No\.\s*identificaci[oó]n|N[uú]mero\s*de\s*pedimento|cuenta\s*predial|Tipo\s*Factor|Tasa\s*o\s*Cuota|Cuota\s*Importe|Imp\.\s*IVA|Clave\s*SAT|ClaveProdServ|Unid\.Medida|Datos\s*SAT|Desglose\s*de\s*impuestos|Documentos\s*Relacionados|Observaciones|Promocion|STOCK\s*Peso|Base:)', line_clean, re.IGNORECASE):
                continue

            clean_item = re.sub(r'^[A-Z0-9\-_/]+\s+\d+\.?\d*\s+\d{8}\s+[A-Z0-9\-_/]+\s+[A-Z0-9\-_/]+\s+', '', line_clean)
            clean_item = re.sub(r'^\d{8}\s+[A-Z0-9\-_/]+\s+\d+\.?\d*\s+[A-Z0-9\-_/]+\s+[A-Z0-9\-_/]+\s+', '', clean_item)
            clean_item = re.sub(r'^\d{8}\s+\d+\s+[A-Z0-9\-_/]+\s+[A-Z0-9\-_/]+\s+', '', clean_item)
            clean_item = re.sub(r'^\d+\.?\d*\s+[A-Z0-9\-_/]+\s+[A-Z0-9\-_/]+\s+\d{8}\s+', '', clean_item)
            clean_item = re.sub(r'^\d+\.?\d*\s+[A-Z0-9\-_/]+\s+[A-Z0-9\-_/]+\s+', '', clean_item)
            clean_item = re.sub(r'^\d+\.?\d*\s+[A-Z0-9\-_/]+\s+', '', clean_item)
            clean_item = re.sub(r'^\d+\s+\d+\s+Unidad\s+de\s+Servicio\s+\d+\s+', '', clean_item)
            clean_item = re.sub(r'^\d+\s+N/A\s+Unidad\s+de\s+Servicio\s+\d+\s+', '', clean_item)
            clean_item = re.sub(r'^\d+\s+', '', clean_item)
            clean_item = re.sub(r'\$\s*[\d,]+\.\d{2}.*$', '', clean_item).strip()
            clean_item = re.sub(r'[\d,]+\.\d{2}\s+[\d,]+\.\d{2}.*$', '', clean_item).strip()
            clean_item = re.sub(r'^(?:Descripción|Concepto)\s*', '', clean_item, flags=re.IGNORECASE).strip()

            clean_item = clean_doubled_text(clean_item)

            if clean_item and len(clean_item) > 3 and not re.match(r'^[\d\s\$,\.\-%/\(\):]+$', clean_item):
                if clean_item not in captured_lines and not re.search(r'^(?:IVA|ISR|IEPS|Impuesto|Tasa|Base|Traslado|Retenci[oó]n|Factor|Cuota|Importe)\b', clean_item, re.IGNORECASE):
                    captured_lines.append(clean_item)

    return captured_lines if captured_lines else ["Materiales / Servicios de Construcción"]


def extract_invoice_data(file_bytes: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Main invoice extraction pipeline adapted for backend processing.
    Extracts structured CFDI data from PDF bytes and maps to database schema fields.
    """
    try:
        raw_text = extract_text_from_pdf_bytes(file_bytes)
    except Exception:
        raw_text = ""

    comprobante = extract_comprobante(raw_text)
    fecha_str = extract_fecha(raw_text)
    importe = extract_importe(raw_text)
    conceptos_list = extract_conceptos(raw_text) if raw_text else ["Materiales y Suministros"]

    # Normalize fields for Invoice schema
    invoice_number = comprobante if comprobante else f"INV-{date.today().year}-{uuid.uuid4().hex[:6].upper()}"
    
    if fecha_str:
        try:
            date_issued = date.fromisoformat(fecha_str)
        except ValueError:
            date_issued = date.today()
    else:
        date_issued = date.today()

    if importe is not None and importe > 0:
        amount = Decimal(str(round(importe, 2)))
    else:
        amount = Decimal("0.00")

    # Combine description string and truncate to 255 chars if needed
    concept = ", ".join(conceptos_list)[:250] if conceptos_list else "Materiales / Servicios"

    return {
        "invoice_number": invoice_number,
        "concept": concept,
        "amount": amount,
        "date_issued": date_issued,
        "is_parsed_automatically": True,
    }

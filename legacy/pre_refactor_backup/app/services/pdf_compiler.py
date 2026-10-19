"""
Servicio de Compilación de PDF para Memorias de Obra.
Renderiza la plantilla HTML/CSS oficial de Memoria de Obra con Jinja2
y la compila a formato PDF utilizando WeasyPrint con fallback automático a xhtml2pdf.
"""

import io
import logging
from pathlib import Path
from typing import Any, Dict

import jinja2

logger = logging.getLogger(__name__)

# Configuración del entorno de plantillas Jinja2
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)


def currency_filter(val: Any) -> str:
    """Formatea números como moneda $#,##0.00"""
    if val is None:
        return "$0.00"
    try:
        return f"${float(val):,.2f}"
    except (ValueError, TypeError):
        return f"${val}"


jinja_env.filters["currency"] = currency_filter


def render_memoria_html(report_data: Dict[str, Any]) -> str:
    """
    Renderiza la plantilla HTML 'memoria.html' con los datos provistos.
    """
    template = jinja_env.get_template("memoria.html")
    return template.render(**report_data)


def generate_memoria_pdf(report_data: Dict[str, Any]) -> bytes:
    """
    Compila los datos de la memoria de obra en un documento PDF en memoria.
    Intenta utilizar WeasyPrint (renderizado CSS3 de alta fidelidad);
    si las librerías del sistema no están disponibles, utiliza xhtml2pdf como respaldo.
    """
    html_content = render_memoria_html(report_data)

    # 1. Intentar WeasyPrint
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        logger.info("PDF de Memoria generado exitosamente con WeasyPrint.")
        return pdf_bytes
    except Exception as exc:
        logger.warning(
            "WeasyPrint no disponible o falló (%s). Utilizando xhtml2pdf como respaldo...",
            exc,
        )

    # 2. Respaldo xhtml2pdf
    try:
        from xhtml2pdf import pisa

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            src=html_content,
            dest=pdf_buffer,
            encoding="utf-8",
        )
        if pisa_status.err:
            raise RuntimeError(f"Error al generar PDF con xhtml2pdf (código de error: {pisa_status.err})")

        pdf_bytes = pdf_buffer.getvalue()
        logger.info("PDF de Memoria generado exitosamente con xhtml2pdf (%d bytes).", len(pdf_bytes))
        return pdf_bytes
    except Exception as exc:
        logger.error("Error crítico al compilar PDF con xhtml2pdf: %s", exc)
        raise RuntimeError(f"No se pudo generar el documento PDF de la memoria: {exc}") from exc

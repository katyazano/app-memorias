"""Servicio para la generación de archivos PDF de memorias de gastos utilizando Playwright.

Genera el documento PDF a partir de la ruta /memorias/{id}/imprimir servida por FastAPI
utilizando el navegador del sistema (msedge, chrome, o chromium).
Configuración: Tamaño Carta, márgenes de 12 mm, printBackground=True, sin encabezados ni pies de Chrome.
"""
import logging
from typing import Optional

from playwright.sync_api import sync_playwright

logger = logging.getLogger("app.pdf")


def generar_pdf_memoria(memoria_id: int, base_url: str = "http://127.0.0.1:8000") -> bytes:
    """Genera el PDF de la memoria cargando su ruta /memorias/{id}/imprimir en Playwright."""
    url = f"{base_url.rstrip('/')}/memorias/{memoria_id}/imprimir"
    logger.info(f"Iniciando generación de PDF para memoria #{memoria_id} desde {url}")

    canales = ["msedge", "chrome", None]
    ultimo_error: Optional[Exception] = None

    with sync_playwright() as p:
        browser = None
        canal_usado = None

        for canal in canales:
            try:
                kw = {"headless": True}
                if canal:
                    kw["channel"] = canal
                browser = p.chromium.launch(**kw)
                canal_usado = canal or "chromium"
                logger.info(f"Navegador lanzado exitosamente con canal='{canal_usado}'")
                break
            except Exception as e:
                logger.warning(f"No se pudo iniciar navegador con canal='{canal}': {e}")
                ultimo_error = e

        if not browser:
            mensaje = (
                "No se encontró ningún navegador disponible para generar el PDF. "
                "Se requiere Microsoft Edge, Google Chrome, o instalar Chromium ejecutando "
                "'playwright install chromium'."
            )
            if ultimo_error:
                mensaje += f" Detalle: {ultimo_error}"
            raise RuntimeError(mensaje)

        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                device_scale_factor=2,
            )
            page = context.new_page()

            # Navegar a la hoja de impresión
            page.goto(url, wait_until="commit", timeout=25000)

            # Esperar a que el selector del contenido esté montado
            try:
                page.wait_for_selector('h1:has-text("MEMORIA")', timeout=20000)
            except Exception:
                # Si falló, verificar si hay un mensaje de error en la página
                body_text = page.inner_text("body")
                if "Error al cargar la memoria" in body_text:
                    raise RuntimeError(f"Error en la aplicación web: {body_text[:200]}")
                raise

            # Esperar a que desaparezca cualquier spinner de carga
            try:
                page.wait_for_selector(".animate-spin", state="detached", timeout=15000)
            except Exception:
                pass

            # Esperar a que la red esté inactiva (fuentes, estilos)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Pequeña pausa para asegurar el cálculo completo de estilos de impresión
            page.wait_for_timeout(400)

            # Generar PDF en tamaño Carta con 12mm de margen y fondo impreso
            pdf_bytes = page.pdf(
                format="Letter",
                margin={
                    "top": "12mm",
                    "bottom": "12mm",
                    "left": "12mm",
                    "right": "12mm",
                },
                print_background=True,
                display_header_footer=False,
            )

            logger.info(f"PDF generado exitosamente ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        finally:
            browser.close()

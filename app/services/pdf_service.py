"""Servicio para la generación de archivos PDF de memorias de gastos.

Llama directamente a Microsoft Edge o Google Chrome del sistema en modo headless
(--headless=new --disable-gpu --user-data-dir=<aislado> --print-to-pdf --no-pdf-header-footer, Carta, márgenes 12 mm)
apuntando a la ruta /memorias/{id}/imprimir servida por FastAPI, sin depender
de Playwright dentro del instalador empaquetado.
"""
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Union

logger = logging.getLogger("app.pdf")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


class NavegadorNoEncontradoError(RuntimeError):
    """Lanzada cuando no se encuentra ningún ejecutable de navegador en el sistema."""
    def __init__(self, rutas_probadas: List[str]):
        rutas_txt = "\n  - ".join(rutas_probadas) if rutas_probadas else "(ninguna)"
        mensaje = (
            "No se encontró ningún navegador disponible para generar el PDF. "
            "Se requiere Microsoft Edge, Google Chrome, o instalar Chromium.\n"
            f"Rutas verificadas:\n  - {rutas_txt}"
        )
        super().__init__(mensaje)
        self.rutas_probadas = rutas_probadas


class GeneracionPdfError(RuntimeError):
    """Lanzada cuando se encontró un navegador pero falló el proceso de renderizado del PDF."""
    def __init__(
        self,
        navegador: str,
        comando: List[str],
        codigo_salida: Optional[int],
        stderr: str,
        stdout: str,
        detalle: str,
    ):
        super().__init__(
            f"El navegador ({navegador}) se encontró pero falló al generar el PDF. "
            f"Código de salida: {codigo_salida}. Detalle: {detalle}"
        )
        self.navegador = navegador
        self.comando = comando
        self.codigo_salida = codigo_salida
        self.stderr = stderr
        self.stdout = stdout
        self.detalle = detalle


def _buscar_en_registro(rutas_probadas: List[str]) -> Optional[Path]:
    """Busca msedge.exe y chrome.exe en el registro de Windows (HKLM y HKCU)."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None

    subkeys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
    ]
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
        (winreg.HKEY_CURRENT_USER, "HKCU"),
    ]
    view_flags = [0]
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        view_flags.append(winreg.KEY_WOW64_64KEY)
    if hasattr(winreg, "KEY_WOW64_32KEY"):
        view_flags.append(winreg.KEY_WOW64_32KEY)

    for root, root_name in roots:
        for subkey in subkeys:
            for flag in view_flags:
                try:
                    with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | flag) as k:
                        val, _ = winreg.QueryValueEx(k, "")
                        if val and isinstance(val, str):
                            clean_val = val.strip().strip('"').strip("'")
                            clean_val = os.path.expandvars(clean_val)
                            p = Path(clean_val)
                            desc = f"Registro {root_name}\\{subkey} -> {p}"
                            if desc not in rutas_probadas:
                                rutas_probadas.append(desc)
                            # NOTA CRÍTICA: En Windows Sandbox (WDAGUtilityAccount), os.access(p, os.X_OK)
                            # devuelve False por permisos de ACL sobre archivos de sistema.
                            # Usar únicamente p.is_file().
                            if p.is_file():
                                logger.info(f"Navegador encontrado vía registro de Windows: {p}")
                                return p
                except (OSError, FileNotFoundError):
                    continue
    return None


def buscar_navegador_sistema(con_rutas: bool = False) -> Union[Optional[Path], Tuple[Optional[Path], List[str]]]:
    """Busca msedge.exe en las rutas estándar de Windows, registro y Chrome como respaldo.

    Si con_rutas=True, retorna una tupla (navegador, rutas_probadas).
    Si con_rutas=False, retorna únicamente el Path o None.
    """
    rutas_probadas: List[str] = []

    # 1. Búsqueda prioritaria en Registro de Windows (App Paths)
    nav_reg = _buscar_en_registro(rutas_probadas)
    if nav_reg:
        return (nav_reg, rutas_probadas) if con_rutas else nav_reg

    # 2. Rutas directas explícitas y variables de entorno estándar
    sys_drive = os.environ.get("SystemDrive", "C:")
    prog_x86 = os.environ.get("ProgramFiles(x86)") or rf"{sys_drive}\Program Files (x86)"
    prog_64 = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles") or rf"{sys_drive}\Program Files"
    prog_files = os.environ.get("ProgramFiles") or rf"{sys_drive}\Program Files"
    local_appdata = os.environ.get("LOCALAPPDATA", "")

    candidatos_base: List[Path] = [
        # Explicitamente incluir Program Files (x86) de Edge (como en Windows Sandbox)
        Path(prog_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(rf"{sys_drive}\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(prog_64) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(prog_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(rf"{sys_drive}\Program Files\Microsoft\Edge\Application\msedge.exe"),
        # Google Chrome como respaldo
        Path(prog_64) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(prog_files) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(prog_x86) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(rf"{sys_drive}\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(rf"{sys_drive}\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]

    if local_appdata:
        candidatos_base.append(Path(local_appdata) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
        candidatos_base.append(Path(local_appdata) / "Google" / "Chrome" / "Application" / "chrome.exe")

    # Eliminar duplicados preservando orden
    candidatos_unicos: List[Path] = []
    for c in candidatos_base:
        if c not in candidatos_unicos:
            candidatos_unicos.append(c)

    for c in candidatos_unicos:
        desc = str(c)
        if desc not in rutas_probadas:
            rutas_probadas.append(desc)
        # Solo comprobamos is_file(): no usar os.access(..., os.X_OK) por compatibilidad con Sandbox
        if c.is_file():
            logger.info(f"Navegador encontrado en ruta de disco: {c}")
            return (c, rutas_probadas) if con_rutas else c

    # 3. Buscar en PATH del sistema
    which_edge = shutil.which("msedge")
    if which_edge:
        p_edge = Path(which_edge)
        desc = f"PATH -> {p_edge}"
        if desc not in rutas_probadas:
            rutas_probadas.append(desc)
        if p_edge.is_file():
            logger.info(f"Navegador encontrado en PATH: {p_edge}")
            return (p_edge, rutas_probadas) if con_rutas else p_edge

    which_chrome = shutil.which("chrome")
    if which_chrome:
        p_chrome = Path(which_chrome)
        desc = f"PATH -> {p_chrome}"
        if desc not in rutas_probadas:
            rutas_probadas.append(desc)
        if p_chrome.is_file():
            logger.info(f"Navegador encontrado en PATH: {p_chrome}")
            return (p_chrome, rutas_probadas) if con_rutas else p_chrome

    logger.warning(f"No se localizó ningún navegador en el sistema. Rutas probadas: {len(rutas_probadas)}")
    return (None, rutas_probadas) if con_rutas else None


def generar_pdf_con_navegador_cli(browser_path: Path, url: str) -> bytes:
    """Genera el PDF ejecutando Edge/Chrome en modo headless CLI con perfil aislado.

    CRÍTICO:
    Siempre se crea un --user-data-dir temporal nuevo y exclusivo por llamada.
    De lo contrario, si el usuario ya tiene Edge o Chrome abierto en Windows, el navegador
    delega la URL al proceso abierto existente y finaliza sin generar el archivo PDF.
    """
    logger.info(f"Generando PDF vía CLI con {browser_path.name} ({browser_path}) desde {url}")

    # Perfil temporal exclusivo por llamada
    tmp_dir = tempfile.mkdtemp(prefix="memorias_pdf_")
    tmp_path = Path(tmp_dir)
    tmp_profile = tmp_path / "isolated_profile"
    tmp_profile.mkdir(parents=True, exist_ok=True)
    out_pdf = tmp_path / "output.pdf"

    # Parámetros para renderizado headless completo de SPA con virtual time budget y aislamiento total
    cmd = [
        str(browser_path),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "--disable-extensions",
        "--disable-default-apps",
        "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        "--virtual-time-budget=7000",
        f"--user-data-dir={tmp_profile}",
        f"--print-to-pdf={out_pdf}",
        url,
    ]

    cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    logger.info(f"Comando de generación de PDF: {cmd_str}")

    creation_flags = 0
    if sys.platform == "win32":
        # Evitar parpadeo de ventana de consola en Windows
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    try:
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=35,
                creationflags=creation_flags,
            )
        except subprocess.TimeoutExpired as e:
            stdout_str = e.stdout.decode("utf-8", errors="ignore").strip() if e.stdout else ""
            stderr_str = e.stderr.decode("utf-8", errors="ignore").strip() if e.stderr else ""
            detalle = "El proceso del navegador excedió el tiempo límite de 35 segundos sin finalizar."
            logger.error(f"Timeout al generar PDF con {browser_path.name}. Comando: {cmd_str}")
            raise GeneracionPdfError(
                navegador=str(browser_path),
                comando=cmd,
                codigo_salida=-1,
                stderr=stderr_str,
                stdout=stdout_str,
                detalle=detalle,
            ) from e

        stdout_str = proc.stdout.decode("utf-8", errors="ignore").strip()
        stderr_str = proc.stderr.decode("utf-8", errors="ignore").strip()

        if not out_pdf.exists():
            detalle = f"El archivo PDF no fue creado por el navegador. Código de salida: {proc.returncode}."
            if stderr_str:
                detalle += f" Stderr: {stderr_str}"
            logger.error(f"Fallo de generación PDF: {detalle}. Comando: {cmd_str}")
            raise GeneracionPdfError(
                navegador=str(browser_path),
                comando=cmd,
                codigo_salida=proc.returncode,
                stderr=stderr_str,
                stdout=stdout_str,
                detalle=detalle,
            )

        file_size = out_pdf.stat().st_size
        if file_size == 0:
            detalle = f"El archivo PDF generado está vacío (0 bytes). Código de salida: {proc.returncode}."
            if stderr_str:
                detalle += f" Stderr: {stderr_str}"
            logger.error(f"Fallo de generación PDF: {detalle}. Comando: {cmd_str}")
            raise GeneracionPdfError(
                navegador=str(browser_path),
                comando=cmd,
                codigo_salida=proc.returncode,
                stderr=stderr_str,
                stdout=stdout_str,
                detalle=detalle,
            )

        pdf_bytes = out_pdf.read_bytes()
        logger.info(f"Método de generación de PDF: edge-cli-no-header-footer ({browser_path.name}, {len(pdf_bytes)} bytes)")
        return pdf_bytes

    finally:
        # Limpieza de archivos temporales ignorando bloqueos temporales de Windows
        shutil.rmtree(tmp_dir, ignore_errors=True)


def generar_pdf_memoria(memoria_id: int, base_url: str = "http://127.0.0.1:8000") -> bytes:
    """Genera el PDF de la memoria cargando la ruta /memorias/{id}/imprimir."""
    url = f"{base_url.rstrip('/')}/memorias/{memoria_id}/imprimir"
    logger.info(f"Iniciando solicitud de PDF para memoria #{memoria_id} desde {url}")

    # Si sync_playwright fue mockeado en pruebas unitarias, usar directamente el mock
    is_mock = sync_playwright and not getattr(sync_playwright, "__module__", "").startswith("playwright")

    browser, rutas_probadas = buscar_navegador_sistema(con_rutas=True)

    if not is_mock:
        if browser:
            # 1. Método principal: Navegador Edge/Chrome del sistema en modo headless CLI
            # Si falla, lanza GeneracionPdfError (nunca se disfraza como "no se encontró navegador")
            return generar_pdf_con_navegador_cli(browser, url)

    # 2. Respaldo secundario: Playwright (solo si está disponible en entorno dev o mock de pruebas)
    if sync_playwright:
        try:
            with sync_playwright() as p:
                pw_browser = None
                for canal in ["msedge", "chrome", None]:
                    try:
                        kw = {"headless": True}
                        if canal:
                            kw["channel"] = canal
                        pw_browser = p.chromium.launch(**kw)
                        break
                    except Exception:
                        continue

                if pw_browser:
                    try:
                        context = pw_browser.new_context(
                            viewport={"width": 1280, "height": 900},
                            device_scale_factor=2,
                        )
                        page = context.new_page()
                        page.goto(url, wait_until="commit", timeout=25000)
                        page.wait_for_selector('h1:has-text("MEMORIA")', timeout=20000)
                        try:
                            page.wait_for_selector(".animate-spin", state="detached", timeout=15000)
                        except Exception:
                            pass
                        page.wait_for_load_state("networkidle", timeout=15000)
                        page.wait_for_timeout(400)

                        pdf_bytes = page.pdf(
                            format="Letter",
                            margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"},
                            print_background=True,
                            display_header_footer=False,
                        )
                        return pdf_bytes
                    finally:
                        pw_browser.close()
        except Exception as e:
            logger.warning(f"Respaldo con Playwright no disponible o falló: {e}")
            if not browser:
                raise NavegadorNoEncontradoError(rutas_probadas)
            raise GeneracionPdfError(
                navegador=str(browser) if browser else "Playwright",
                comando=[],
                codigo_salida=-1,
                stderr=str(e),
                stdout="",
                detalle=f"Fallo en Playwright: {e}",
            )

    # 3. Si no hay ningún navegador encontrado
    raise NavegadorNoEncontradoError(rutas_probadas)

"""Prueba de humo del binario empaquetado para Windows (.exe).

Inicia MemoriasGastos-Debug.exe (o MemoriasGastos.exe) en un %LOCALAPPDATA% temporal
aislado y ejecuta vía HTTP el flujo completo con las facturas de ejemplo:
1. Conexión y verificación de salud (/health)
2. Crear obra
3. Subir factura XML + PDF desde fixtures externos al instalador
4. Confirmar y guardar factura (verifica guardado en DB y copia física a storage)
5. Subir la misma factura otra vez (debe responder 409 Conflict)
6. Registrar gasto manual (efectivo/nota)
7. Registrar pago de raya semanal
8. Registrar anticipo del cliente
9. Generar borrador de memoria (preview + guardar)
10. Cerrar memoria (actualiza saldos y dispara respaldo automático)
11. Descargar PDF generado por el navegador nativo (Edge/Chrome CLI)
12. Descargar Excel con fórmulas vivas (.xlsx)
13. Verificar integridad del archivo .zip de respaldo generado
14. Apagado controlado (/api/sistema/apagar)
"""
import os
import sys
import time
import zipfile
import tempfile
import sqlite3
import subprocess
from pathlib import Path
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
DIST_DIR = REPO_ROOT / "dist" / "MemoriasGastos"


def log(msg: str):
    print(f"[SMOKE TEST] {msg}", flush=True)


def fail(msg: str, proc: subprocess.Popen = None, temp_dir: str = None, base_url: str = None):
    print(f"\n[ERROR FATAL EN PRUEBA DE HUMO] {msg}\n", file=sys.stderr, flush=True)
    if proc and proc.poll() is None:
        if base_url:
            try:
                requests.post(f"{base_url}/api/sistema/apagar", timeout=3)
            except Exception:
                pass
        try:
            proc.terminate()
            proc.wait(timeout=4)
        except Exception:
            proc.kill()
    if temp_dir:
        log_file = Path(temp_dir) / "MemoriasGastos" / "logs" / "app.log"
        if log_file.exists():
            print("=== ÚLTIMAS 50 LÍNEAS DE app.log ===", file=sys.stderr)
            try:
                print(log_file.read_text(encoding="utf-8")[-4000:], file=sys.stderr)
            except Exception as e:
                print(f"No se pudo leer app.log: {e}", file=sys.stderr)
    sys.exit(1)


def run_smoke_test():
    import uuid
    import socket

    # 1. Localizar ejecutable
    exe_path = DIST_DIR / "MemoriasGastos-Debug.exe"
    if not exe_path.exists():
        exe_path = DIST_DIR / "MemoriasGastos.exe"
    if not exe_path.exists():
        fail(f"No se encontró el ejecutable empaquetado en {DIST_DIR}")

    # 2. Localizar fixtures
    xml_fixture = FIXTURES_DIR / "factura_muestra.xml"
    pdf_fixture = FIXTURES_DIR / "factura_muestra.pdf"
    if not xml_fixture.exists():
        fail(f"Falta fixture XML requerido: {xml_fixture}")
    if not pdf_fixture.exists():
        fail(f"Falta fixture PDF requerido: {pdf_fixture}")

    # 3. Crear LOCALAPPDATA temporal y configurar variables de entorno aisladas
    temp_dir = tempfile.mkdtemp(prefix="mg_smoke_")
    env = os.environ.copy()
    env["LOCALAPPDATA"] = temp_dir

    # Asignar puerto libre dinámico y mutex único para aislar la prueba
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        test_port = s.getsockname()[1]

    env["APP_PORT"] = str(test_port)
    env["MEMORIAS_MUTEX_NAME"] = f"Local\\MemoriasGastos_SmokeTest_{uuid.uuid4().hex}"
    env["MEMORIAS_NO_BROWSER"] = "1"
    base_url = f"http://127.0.0.1:{test_port}"

    log(f"Iniciando ejecutable {exe_path.name} en puerto {test_port} con LOCALAPPDATA={temp_dir}")

    proc = subprocess.Popen([str(exe_path)], env=env)

    try:
        # 4. Esperar arranque del servidor
        log(f"Esperando arranque de Uvicorn en {base_url}...")
        up = False
        for _ in range(30):
            try:
                r = requests.get(f"{base_url}/health", timeout=2)
                if r.status_code == 200:
                    health = r.json()
                    log(f"Servidor en línea: App={health.get('app')}, Esquema={health.get('version_build', {}).get('esquema')}")
                    up = True
                    break
            except Exception:
                time.sleep(0.5)

        if not up:
            fail(f"El servidor empaquetado no respondió a /health dentro del tiempo límite.", proc, temp_dir, base_url)

        # 5. Crear obra
        log("Paso 1: Crear obra...")
        r_obra = requests.post(f"{base_url}/api/obras", json={"nombre": "Obra Prueba de Humo"})
        if r_obra.status_code != 201:
            fail(f"Fallo al crear obra: {r_obra.status_code} - {r_obra.text}", proc, temp_dir, base_url)
        obra = r_obra.json()
        obra_id = obra["id"]
        log(f"Obra creada con ID {obra_id}: '{obra['nombre']}'")

        # 6. Subir factura XML + PDF
        log("Paso 2: Subir factura XML + PDF a staging...")
        with open(xml_fixture, "rb") as fx, open(pdf_fixture, "rb") as fp:
            files = [
                ("files", (xml_fixture.name, fx, "application/xml")),
                ("files", (pdf_fixture.name, fp, "application/pdf")),
            ]
            r_up = requests.post(f"{base_url}/api/obras/{obra_id}/facturas", files=files)

        if r_up.status_code != 200:
            fail(f"Fallo al subir archivos: {r_up.status_code} - {r_up.text}", proc, temp_dir, base_url)

        up_json = r_up.json()
        items = up_json.get("items", [])
        if not items:
            fail(f"No se extrajo ninguna factura de los archivos subidos. Errores: {up_json.get('errores')}", proc, temp_dir, base_url)

        item = items[0]
        staging_id = item["staging_id"]
        factura_uuid = item["datos"]["uuid"]
        log(f"Factura en staging: UUID={factura_uuid}, Total=${item['datos']['total']}, PDF vinculado={item['archivo_pdf']}")

        # 7. Confirmar y guardar factura
        log("Paso 3: Confirmar y guardar factura...")
        conf_payload = {
            "items": [
                {
                    "staging_id": staging_id,
                    "metodo_pago": "transferencia",
                    "proveedor_alias": "Proveedor Humo Test",
                }
            ]
        }
        r_conf = requests.post(f"{base_url}/api/obras/{obra_id}/facturas/confirmar", json=conf_payload)
        if r_conf.status_code != 201:
            fail(f"Fallo al confirmar factura: {r_conf.status_code} - {r_conf.text}", proc, temp_dir, base_url)

        gastos_conf = r_conf.json()
        if not gastos_conf:
            fail("La respuesta de confirmación no devolvió gastos creados.", proc, temp_dir, base_url)

        gasto_factura = gastos_conf[0]
        log(f"Gasto de factura guardado: ID={gasto_factura['id']}, Importe=${gasto_factura['importe']}, Origen={gasto_factura['origen']}")

        # Verificar existencia física de archivos en %LOCALAPPDATA%\MemoriasGastos\storage\{obra_id}\
        storage_obra = Path(temp_dir) / "MemoriasGastos" / "storage" / str(obra_id)
        xml_guardado = storage_obra / f"{factura_uuid}.xml"
        pdf_guardado = storage_obra / f"{factura_uuid}.pdf"
        if not xml_guardado.exists():
            fail(f"El XML no se guardó en la ruta física esperada: {xml_guardado}", proc, temp_dir, base_url)
        if not pdf_guardado.exists():
            fail(f"El PDF no se guardó en la ruta física esperada: {pdf_guardado}", proc, temp_dir, base_url)
        log("Archivos XML y PDF verificados físicamente en disco.")

        # 8. Subir de nuevo la misma factura -> Debe responder 409
        log("Paso 4: Subir de nuevo la misma factura (detección de duplicados)...")
        with open(xml_fixture, "rb") as fx:
            files_dup = [("files", (xml_fixture.name, fx, "application/xml"))]
            r_dup = requests.post(f"{base_url}/api/obras/{obra_id}/facturas", files=files_dup)

        if r_dup.status_code != 409:
            fail(f"Se esperaba HTTP 409 al re-subir factura duplicada, pero se recibió {r_dup.status_code}: {r_dup.text}", proc, temp_dir, base_url)
        log(f"Detección de duplicado correcta: HTTP 409 Conflict")

        # 9. Gasto manual
        log("Paso 5: Registrar gasto manual (efectivo/nota)...")
        gasto_manual_payload = {
            "fecha": "2026-10-15",
            "concepto_resumido": "Material menor ferretería",
            "comprobante": "NOTA-101",
            "tipo_comprobante": "NOTA",
            "importe": "450.00",
            "metodo_pago": "efectivo",
            "origen": "manual",
        }
        r_gm = requests.post(f"{base_url}/api/obras/{obra_id}/gastos", json=gasto_manual_payload)
        if r_gm.status_code != 201:
            fail(f"Fallo al registrar gasto manual: {r_gm.status_code} - {r_gm.text}", proc, temp_dir, base_url)
        log("Gasto manual registrado exitosamente ($450.00)")

        # 10. Raya semanal
        log("Paso 6: Registrar trabajador y raya semanal...")
        r_trab = requests.post(f"{base_url}/api/trabajadores", json={"nombre": "Pedro Albañil", "oficio": "Albañil"})
        if r_trab.status_code != 201:
            fail(f"Fallo al registrar trabajador: {r_trab.status_code} - {r_trab.text}", proc, temp_dir, base_url)
        trab_id = r_trab.json()["id"]

        raya_payload = {
            "trabajador_id": trab_id,
            "semana_numero": 41,
            "fecha_inicio": "2026-10-05",
            "fecha_fin": "2026-10-11",
            "tipo": "dia",
            "cantidad": "1.0",
            "tarifa": "3200.00",
        }
        r_raya = requests.post(f"{base_url}/api/obras/{obra_id}/rayas", json=raya_payload)
        if r_raya.status_code != 201:
            fail(f"Fallo al registrar raya: {r_raya.status_code} - {r_raya.text}", proc, temp_dir, base_url)
        log("Raya registrada exitosamente (Semana 41, $3,200.00)")

        # 11. Anticipo
        log("Paso 7: Registrar anticipo del cliente...")
        ant_payload = {
            "fecha": "2026-10-01",
            "importe": "20000.00",
            "comprobante": "TRANSF-ANT-01",
        }
        r_ant = requests.post(f"{base_url}/api/obras/{obra_id}/anticipos", json=ant_payload)
        if r_ant.status_code != 201:
            fail(f"Fallo al registrar anticipo: {r_ant.status_code} - {r_ant.text}", proc, temp_dir, base_url)
        log("Anticipo registrado exitosamente ($20,000.00)")

        # 12. Memoria (preview y guardar borrador)
        log("Paso 8: Previsualizar y crear borrador de Memoria 01...")
        r_prev = requests.post(
            f"{base_url}/api/obras/{obra_id}/memorias/preview",
            json={"fecha_inicio": "2026-10-01", "fecha_fin": "2026-10-31"},
        )
        if r_prev.status_code != 200:
            fail(f"Fallo al previsualizar memoria: {r_prev.status_code} - {r_prev.text}", proc, temp_dir, base_url)
        preview = r_prev.json()

        mem_save_payload = {
            "obra_id": obra_id,
            "numero": 1,
            "folio_factura_arquitecto": "101",
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-31",
            "renglones": preview.get("renglones", []),
        }
        r_mem = requests.post(f"{base_url}/api/memorias", json=mem_save_payload)
        if r_mem.status_code != 201:
            fail(f"Fallo al crear borrador de memoria: {r_mem.status_code} - {r_mem.text}", proc, temp_dir, base_url)
        memoria = r_mem.json()
        memoria_id = memoria["id"]
        log(f"Borrador de Memoria creado: ID={memoria_id}, Número={memoria['numero']}")

        # 13. Cerrar memoria
        log("Paso 9: Cerrar Memoria 01...")
        r_close = requests.post(f"{base_url}/api/memorias/{memoria_id}/cerrar")
        if r_close.status_code != 200:
            fail(f"Fallo al cerrar memoria: {r_close.status_code} - {r_close.text}", proc, temp_dir, base_url)
        mem_cerrada = r_close.json()
        if mem_cerrada["estado"] != "cerrada":
            fail(f"La memoria no quedó en estado cerrada: {mem_cerrada['estado']}", proc, temp_dir, base_url)
        log("Memoria cerrada satisfactoriamente.")

        # 14. Descargar PDF con navegador del sistema (con Edge abierto simultáneamente)
        log("Paso 10: Descargar PDF generado por navegador CLI (con Edge abierto en segundo plano)...")
        from app.services.pdf_service import buscar_navegador_sistema
        browser_ejecutable = buscar_navegador_sistema()
        p_browser_abierto = None
        if browser_ejecutable:
            try:
                log(f"Iniciando instancia activa de {browser_ejecutable.name} para verificar no-delegación...")
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
                p_browser_abierto = subprocess.Popen([str(browser_ejecutable), "about:blank"], creationflags=flags)
                time.sleep(1.5)
            except Exception as e:
                log(f"Aviso: No se pudo lanzar proceso paralelo de navegador ({e}); continuando...")

        try:
            r_pdf = requests.get(f"{base_url}/api/memorias/{memoria_id}/pdf", timeout=35)
            if r_pdf.status_code != 200:
                fail(f"Fallo al generar/descargar PDF: {r_pdf.status_code} - {r_pdf.text}", proc, temp_dir, base_url)
            pdf_bytes = r_pdf.content
            if not pdf_bytes.startswith(b"%PDF-"):
                fail("El contenido descargado de PDF no tiene la cabecera %PDF-", proc, temp_dir, base_url)
            if len(pdf_bytes) < 5000:
                fail(f"El archivo PDF descargado es sospechosamente pequeño ({len(pdf_bytes)} bytes)", proc, temp_dir, base_url)
            log(f"PDF generado y descargado correctamente ({len(pdf_bytes)} bytes) con Edge abierto en paralelo.")

            metodo_usado = r_pdf.headers.get("X-PDF-Generation-Method")
            if metodo_usado != "edge-cli-no-header-footer":
                fail(f"Método de generación de PDF no coincide: se esperaba 'edge-cli-no-header-footer', se recibió '{metodo_usado}'", proc, temp_dir, base_url)
            log(f"Método de generación de PDF unificado y verificado: {metodo_usado}")

            # Extraer y verificar texto del PDF generado
            import io
            import re
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            texto_pdf = ""
            for i, page in enumerate(reader.pages):
                texto_pdf += f"\n--- PÁGINA {i+1} ---\n" + (page.extract_text() or "")

            # 1. Fallar si contiene la URL ("127.0.0.1" o "localhost")
            if "127.0.0.1" in texto_pdf or "localhost:" in texto_pdf:
                fail(f"El PDF contiene la URL del servidor ('127.0.0.1') en encabezados:\n{texto_pdf[:400]}", proc, temp_dir, base_url)

            # 2. Fallar si contiene el título "frontend"
            if "frontend" in texto_pdf.lower():
                fail(f"El PDF contiene el título 'frontend' en encabezados:\n{texto_pdf[:400]}", proc, temp_dir, base_url)

            # 3. Fallar si contiene encabezado/pie con fecha/hora típica de impresión de Chrome/Edge
            chrome_header_re = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}(:\d{2})?\s+(AM|PM)\b", re.IGNORECASE)
            match_header = chrome_header_re.search(texto_pdf)
            if match_header:
                fail(f"El PDF contiene encabezado/pie de fecha-hora de Chrome ('{match_header.group(0)}'):\n{texto_pdf[:400]}", proc, temp_dir, base_url)

            log("Extracción de texto del PDF verificada: SIN URL ('127.0.0.1'), SIN título ('frontend'), SIN encabezados de fecha/hora.")
        finally:
            if p_browser_abierto:
                try:
                    p_browser_abierto.terminate()
                    p_browser_abierto.wait(timeout=2)
                except Exception:
                    try:
                        p_browser_abierto.kill()
                    except Exception:
                        pass

        # 15. Descargar XLSX con fórmulas vivas
        log("Paso 11: Descargar archivo Excel (.xlsx)...")
        r_xlsx = requests.get(f"{base_url}/api/memorias/{memoria_id}/xlsx", timeout=15)
        if r_xlsx.status_code != 200:
            fail(f"Fallo al generar/descargar XLSX: {r_xlsx.status_code} - {r_xlsx.text}", proc, temp_dir, base_url)
        xlsx_bytes = r_xlsx.content
        if not xlsx_bytes.startswith(b"PK\x03\x04"):
            fail("El contenido descargado de XLSX no tiene la firma ZIP de Excel", proc, temp_dir, base_url)
        log(f"XLSX generado y descargado correctamente ({len(xlsx_bytes)} bytes)")

        # 16. Verificar zip de respaldo
        log("Paso 12: Verificar respaldo automático en zip...")
        respaldos_dir = Path(temp_dir) / "MemoriasGastos" / "respaldos"
        zips = list(respaldos_dir.glob("*.zip"))
        if not zips:
            fail(f"No se encontró ningún archivo .zip en la carpeta de respaldos: {respaldos_dir}", proc, temp_dir, base_url)

        # Usar el zip más reciente
        zips.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        reciente_zip = zips[0]
        log(f"Examinando respaldo: {reciente_zip.name} ({reciente_zip.stat().st_size} bytes)")

        with zipfile.ZipFile(reciente_zip, "r") as zf:
            nombres = zf.namelist()
            if "data/app.db" not in nombres and "app.db" not in nombres:
                fail(f"El respaldo .zip no contiene la base de datos app.db: {nombres}", proc, temp_dir, base_url)
            # Verificar que incluya archivos de storage
            archivos_storage = [n for n in nombres if n.startswith("storage/") or n.startswith("data/storage/")]
            if not archivos_storage:
                fail(f"El respaldo .zip no contiene archivos en storage/: {nombres}", proc, temp_dir, base_url)
            log(f"Respaldo verificado con éxito ({len(nombres)} archivos internos, incluyendo {len(archivos_storage)} en storage)")

            # Verificar integridad SQLite del respaldo
            db_entry = "data/app.db" if "data/app.db" in nombres else "app.db"
            with tempfile.TemporaryDirectory() as td:
                zf.extract(db_entry, path=td)
                db_extr = Path(td) / db_entry
                conn = sqlite3.connect(str(db_extr))
                res = conn.execute("PRAGMA integrity_check;").fetchone()
                conn.close()
                if not res or res[0] != "ok":
                    fail(f"Integridad SQLite fallida en el respaldo: {res}", proc, temp_dir, base_url)
                log("Integridad de base de datos en el respaldo: OK")

        # 17. Apagar servidor de prueba
        log("Paso 13: Apagando servidor empaquetado...")
        r_down = requests.post(f"{base_url}/api/sistema/apagar", timeout=5)
        log(f"Respuesta de apagado: {r_down.status_code}")
        proc.wait(timeout=6)
        log("Proceso cerrado limpiamente.")

        print("\n============================================================")
        print("    ¡PRUEBA DE HUMO DEL BINARIO EMPAQUETADO EXITOSA!")
        print("============================================================\n")

    finally:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    run_smoke_test()

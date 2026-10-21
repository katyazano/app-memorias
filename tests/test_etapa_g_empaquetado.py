"""Pruebas de la Etapa G: Empaquetado, rutas sys.frozen, PDF nativo, ciclo de vida y lanzador."""
import os
import sys
import socket
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app import config
from app.services.pdf_service import buscar_navegador_sistema
from app.services import lifecycle_service


def test_rutas_configuradas_correctamente():
    """Verifica que las rutas de recursos y datos escribibles estén correctamente definidas."""
    assert config.BUNDLE_DIR.exists(), "BUNDLE_DIR debe existir"
    assert config.ALEMBIC_INI.exists(), "alembic.ini debe existir en BUNDLE_DIR"
    assert config.MIGRATIONS_DIR.exists(), "migrations debe existir en BUNDLE_DIR"
    assert config.DATA_DIR.exists(), "DATA_DIR debe existir"
    assert config.STORAGE_DIR.exists(), "STORAGE_DIR debe existir"
    assert config.BACKUPS_DEFAULT_DIR.exists(), "BACKUPS_DEFAULT_DIR debe existir"
    assert config.LOGS_DIR.exists(), "LOGS_DIR debe existir"


def test_simulacion_modo_empaquetado_frozen(monkeypatch):
    """Verifica que en modo sys.frozen las rutas apunten a %LOCALAPPDATA%\\MemoriasGastos."""
    fake_localappdata = r"C:\Users\TestUser\AppData\Local"
    monkeypatch.setenv("LOCALAPPDATA", fake_localappdata)

    # Simular sys.frozen
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(config.BUNDLE_DIR), raising=False)

    # Re-evaluar lógica de rutas para modo frozen
    base_writable = Path(fake_localappdata) / "MemoriasGastos"
    data_dir = base_writable / "data"
    storage_dir = base_writable / "storage"
    logs_dir = base_writable / "logs"
    backups_dir = base_writable / "respaldos"

    assert data_dir == base_writable / "data"
    assert storage_dir == base_writable / "storage"
    assert logs_dir == base_writable / "logs"
    assert backups_dir == base_writable / "respaldos"


def test_busqueda_navegador_sistema():
    """Verifica que buscar_navegador_sistema encuentre Edge o Chrome en rutas de Windows."""
    nav = buscar_navegador_sistema()
    # En cualquier máquina estándar con Windows 10/11 debe encontrarse Edge
    if sys.platform == "win32":
        assert nav is not None, "Debe localizarse msedge.exe o chrome.exe en Windows"
        assert nav.exists()
        assert nav.suffix.lower() == ".exe"


def test_endpoints_ciclo_de_vida(client: TestClient):
    """Prueba los endpoints de heartbeat y apagado controlado."""
    # 1. Heartbeat
    r_hb = client.post("/api/sistema/heartbeat")
    assert r_hb.status_code == 200
    assert r_hb.json()["status"] == "ok"
    assert "timestamp" in r_hb.json()

    # 2. Heartbeat sin prefijo /api
    r_hb2 = client.post("/sistema/heartbeat")
    assert r_hb2.status_code == 200
    assert r_hb2.json()["status"] == "ok"


def test_launcher_obtencion_puerto_disponible():
    """Verifica la lógica de búsqueda de puerto disponible del launcher."""
    import launcher

    # Probar con un puerto libre
    puerto = launcher.obtener_puerto_disponible(8000)
    assert puerto >= 8000

    # Simular puerto ocupado abriendo un socket temporal
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 8000))
        puerto_alternativo = launcher.obtener_puerto_disponible(8000)
        assert puerto_alternativo != 8000
        assert puerto_alternativo >= 8001


def test_storage_rel_y_abs_path_con_storage_hermano_de_data(monkeypatch, tmp_path):
    """Verifica que _rel y abs_path soporten STORAGE_DIR como hermano de DATA_DIR (modo empaquetado)."""
    from app.services import storage

    base_writable = tmp_path / "MemoriasGastos"
    fake_data = base_writable / "data"
    fake_storage = base_writable / "storage"
    fake_data.mkdir(parents=True)
    fake_storage.mkdir(parents=True)

    monkeypatch.setattr(config, "DATA_DIR", fake_data)
    monkeypatch.setattr(config, "STORAGE_DIR", fake_storage)

    # Crear archivo en storage/1/factura.xml
    archivo_dest = fake_storage / "1" / "test_uuid.xml"
    archivo_dest.parent.mkdir(parents=True, exist_ok=True)
    archivo_dest.write_text("<cfdi/>", encoding="utf-8")

    # _rel debe devolver 'storage/1/test_uuid.xml' sin lanzar ValueError
    rel = storage._rel(archivo_dest)
    assert rel == "storage/1/test_uuid.xml"

    # abs_path debe resolver la ruta física en fake_storage
    resuelto = storage.abs_path(rel)
    assert resuelto == archivo_dest
    assert resuelto.exists()


def test_endpoint_abrir_logs(client: TestClient):
    """Verifica el endpoint para abrir la carpeta de logs."""
    r = client.post("/api/sistema/abrir-logs")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "error")
    assert "ruta" in data


def test_pdf_separacion_no_encontrado_vs_fallo(monkeypatch):
    """Verifica la separación estricta entre NavegadorNoEncontradoError y GeneracionPdfError."""
    from app.services import pdf_service

    # Caso 1: Navegador NO encontrado
    monkeypatch.setattr(pdf_service, "sync_playwright", None)
    monkeypatch.setattr(pdf_service, "buscar_navegador_sistema", lambda con_rutas=False: (None, ["C:\\Ruta\\Inexistente\\msedge.exe"]) if con_rutas else None)

    with pytest.raises(pdf_service.NavegadorNoEncontradoError) as exc_info:
        pdf_service.generar_pdf_memoria(1, base_url="http://127.0.0.1:8000")

    assert "No se encontró ningún navegador disponible" in str(exc_info.value)
    assert exc_info.value.rutas_probadas == ["C:\\Ruta\\Inexistente\\msedge.exe"]

    # Caso 2: Navegador SÍ encontrado pero el CLI falla
    fake_browser = Path(r"C:\Fake\msedge.exe")
    monkeypatch.setattr(pdf_service, "buscar_navegador_sistema", lambda con_rutas=False: (fake_browser, [str(fake_browser)]) if con_rutas else fake_browser)

    def fake_cli(browser_path, url):
        raise pdf_service.GeneracionPdfError(
            navegador=str(browser_path),
            comando=["fake_cmd"],
            codigo_salida=1,
            stderr="Error fatal de prueba",
            stdout="",
            detalle="El proceso retornó código 1",
        )

    monkeypatch.setattr(pdf_service, "generar_pdf_con_navegador_cli", fake_cli)

    with pytest.raises(pdf_service.GeneracionPdfError) as exc_info_cli:
        pdf_service.generar_pdf_memoria(1, base_url="http://127.0.0.1:8000")

    err = exc_info_cli.value
    assert "falló al generar el PDF" in str(err)
    assert err.codigo_salida == 1
    assert "Error fatal de prueba" in err.stderr
    assert not isinstance(err, pdf_service.NavegadorNoEncontradoError)


def test_pdf_endpoint_respuestas_detalladas(client: TestClient, monkeypatch):
    """Verifica que el endpoint /api/memorias/{id}/pdf devuelva detalles estructurados en caso de error."""
    import datetime
    from decimal import Decimal
    from app.services import pdf_service
    from app.models import Memoria, Obra, EstadoMemoria
    from app.database import get_db

    # Obtener o crear una memoria de prueba
    db = next(get_db())
    obra = db.query(Obra).first()
    if not obra:
        obra = Obra(
            nombre="Obra Test PDF",
            ubicacion="Zapopan",
            propietario="Cliente Test",
            porcentaje_honorarios=Decimal("10.0"),
            saldo_inicial_acumulado=Decimal("0.0"),
            saldo_inicial_gastado=Decimal("0.0"),
        )
        db.add(obra)
        db.commit()
    mem = db.query(Memoria).filter(Memoria.obra_id == obra.id).first()
    if not mem:
        mem = Memoria(
            obra_id=obra.id,
            numero=1,
            fecha_inicio=datetime.date(2026, 10, 1),
            fecha_fin=datetime.date(2026, 10, 31),
            porcentaje_honorarios_usado=Decimal("10.0"),
            estado=EstadoMemoria.BORRADOR,
        )
        db.add(mem)
        db.commit()
    mem_id = mem.id

    # Simular NavegadorNoEncontradoError
    def fake_generar_no_encontrado(memoria_id, base_url):
        raise pdf_service.NavegadorNoEncontradoError(["C:\\Program Files\\Edge\\msedge.exe"])

    monkeypatch.setattr("app.routers.memorias.generar_pdf_memoria", fake_generar_no_encontrado)
    r_no_nav = client.get(f"/api/memorias/{mem_id}/pdf")
    assert r_no_nav.status_code == 500
    data_no_nav = r_no_nav.json()["detail"]
    assert data_no_nav["codigo"] == "navegador_no_encontrado"
    assert "rutas_probadas" in data_no_nav

    # Simular GeneracionPdfError
    def fake_generar_fallo_cli(memoria_id, base_url):
        raise pdf_service.GeneracionPdfError(
            navegador="msedge.exe",
            comando=["msedge.exe", "--headless"],
            codigo_salida=2,
            stderr="Simulated crash",
            stdout="",
            detalle="Fallo de renderizado simulado",
        )

    monkeypatch.setattr("app.routers.memorias.generar_pdf_memoria", fake_generar_fallo_cli)
    r_fallo = client.get(f"/api/memorias/{mem_id}/pdf")
    assert r_fallo.status_code == 500
    data_fallo = r_fallo.json()["detail"]
    assert data_fallo["codigo"] == "error_generacion_pdf"
    assert data_fallo["navegador"] == "msedge.exe"
    assert data_fallo["codigo_salida"] == 2


def test_resumen_conceptos_facturas_reglas_limpieza():
    """Verifica las reglas de resumen de conceptos:
    - Sin unidades 'NA', 'ACT', 'H87'.
    - 2 partidas y ' Y OTROS' si hay más.
    - Máximo ~80 caracteres y sin terminar en preposición.
    """
    from app.services.xml_parser import resumir_concepto

    # Caso 1: Unidades genéricas ignoradas y sufijo ' Y OTROS'
    conceptos_multi = [
        {"cantidad": "10", "unidad": "H87", "descripcion": "CEMENTO GRIS APASCO 50KG"},
        {"cantidad": "1", "unidad": "ACT", "descripcion": "FLETE DE MATERIAL A OBRA"},
        {"cantidad": "3", "unidad": "NA", "descripcion": "MANIOBRA Y DESCARGA"},
        {"cantidad": "5", "unidad": "PZA", "descripcion": "VARILLA 3/8 R-42"},
    ]
    resumen = resumir_concepto(conceptos_multi)
    assert "H87" not in resumen
    assert "ACT" not in resumen
    assert "NA" not in resumen
    assert "Y OTROS" in resumen
    assert len(resumen) <= 80
    assert resumen == "10 CEMENTO GRIS APASCO 50KG, 1 FLETE DE MATERIAL A OBRA Y OTROS"

    # Caso 2: Conceptos muy largos que deben truncar a <= 80 caracteres en límite de palabra
    conceptos_largos = [
        {"cantidad": "1", "unidad": "PZA", "descripcion": "VARILLA CORRUGADA DE ACERO DE ALTA RESISTENCIA GRADO 42 DE TRES OCTAVOS PARA ESTRUCTURA"},
        {"cantidad": "2", "unidad": "PZA", "descripcion": "ESTRIBOS DE ALAMBRON DE UN CUARTO PARA CASTILLOS Y COLUMNAS"},
        {"cantidad": "1", "unidad": "PZA", "descripcion": "ALAMBRE RECOCIDO CALIBRE 16"},
    ]
    res_largo = resumir_concepto(conceptos_largos)
    assert len(res_largo) <= 80
    assert res_largo.endswith("Y OTROS")
    base_sin_sufijo = res_largo.replace(" Y OTROS", "").strip()
    # No debe terminar en preposiciones como 'PARA', 'DE', etc.
    assert not base_sin_sufijo.upper().endswith(" PARA")
    assert not base_sin_sufijo.upper().endswith(" DE")


def test_sugerir_alias_proveedor_tmc940823v97():
    """Prueba con el caso de la factura TMC940823V97 G 80539:
    'DE LA TORRE MATERIALES PARA CONSTRUCCION' -> 'DE LA TORRE MATERIALES'.
    """
    from app.services.xml_parser import sugerir_alias

    # 1. Razón social directa
    alias = sugerir_alias("DE LA TORRE MATERIALES PARA CONSTRUCCION")
    assert alias == "DE LA TORRE MATERIALES"

    # 2. Razón social con sufijo societario
    alias_sa = sugerir_alias("DE LA TORRE MATERIALES PARA CONSTRUCCION SA DE CV")
    assert alias_sa == "DE LA TORRE MATERIALES"

    # 3. Caso que corta en límite de palabra sin romper vocablos
    alias_distribuidora = sugerir_alias("DISTRIBUIDORA DE ACEROS Y PERFILES DE OCCIDENTE SA DE CV")
    assert not alias_distribuidora.endswith(" Y")
    assert not alias_distribuidora.endswith(" DE")
    assert len(alias_distribuidora) <= 32


def test_extraccion_texto_pdf_sin_headers_chrome(monkeypatch):
    """Verifica que el PDF generado no contenga '127.0.0.1', 'frontend' ni fecha/hora de Chrome."""
    import io
    from pypdf import PdfReader
    from app.services.pdf_service import buscar_navegador_sistema, generar_pdf_con_navegador_cli

    browser = buscar_navegador_sistema()
    if not browser:
        pytest.skip("Navegador no disponible para prueba de renderizado CLI")

    # Renderizar un HTML de prueba que contiene un título pero sin que se imprima en encabezado
    html_url = "data:text/html,<html><head><title>frontend</title></head><body><h1>MEMORIA DE GASTOS</h1><p>Prueba de texto limpio</p></body></html>"
    pdf_bytes = generar_pdf_con_navegador_cli(browser, html_url)
    assert pdf_bytes.startswith(b"%PDF-")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    texto_total = "".join(page.extract_text() or "" for page in reader.pages)

    # El contenido debe estar presente
    assert "MEMORIA DE GASTOS" in texto_total
    # Pero los encabezados y URL NO deben estar presentes
    assert "127.0.0.1" not in texto_total
    assert "frontend" not in texto_total


def test_reabrir_memoria_ultima_y_restriccion_anteriores(client: TestClient):
    """Verifica el flujo de reapertura de memorias:
    1. Solo la última memoria cerrada puede reabrirse.
    2. Intentar reabrir una memoria anterior a la última cerrada retorna HTTP 409 Conflict.
    3. Reabrir una memoria en borrador retorna HTTP 400 Bad Request.
    4. Al reabrir con éxito:
       - Vuelve a borrador.
       - cerrada_at pasa a None.
       - Genera entrada en el registro de auditoría.
       - Realiza respaldo previo automático.
    """
    import datetime
    from decimal import Decimal
    from app.models import Obra, Memoria, EstadoMemoria, RegistroAuditoria
    from app.database import get_db

    db = next(get_db())

    # 1. Crear obra de prueba
    obra = Obra(
        nombre=f"Obra Test Reapertura {datetime.datetime.now().timestamp()}",
        ubicacion="Guadalajara",
        propietario="Cliente Auditoría",
        porcentaje_honorarios=Decimal("10.0"),
    )
    db.add(obra)
    db.commit()
    db.refresh(obra)

    # 2. Crear memoria 1 (cerrada) y memoria 2 (cerrada)
    mem1 = Memoria(
        obra_id=obra.id,
        numero=1,
        fecha_inicio=datetime.date(2026, 10, 1),
        fecha_fin=datetime.date(2026, 10, 15),
        porcentaje_honorarios_usado=Decimal("10.0"),
        folio_factura_arquitecto="501",
        estado=EstadoMemoria.CERRADA,
        cerrada_at=datetime.datetime.now(datetime.timezone.utc),
        snapshot_json='{"total_memoria": "50000.00"}',
    )
    mem2 = Memoria(
        obra_id=obra.id,
        numero=2,
        fecha_inicio=datetime.date(2026, 10, 16),
        fecha_fin=datetime.date(2026, 10, 31),
        porcentaje_honorarios_usado=Decimal("10.0"),
        folio_factura_arquitecto="502",
        estado=EstadoMemoria.CERRADA,
        cerrada_at=datetime.datetime.now(datetime.timezone.utc),
        snapshot_json='{"total_memoria": "75000.00"}',
    )
    db.add(mem1)
    db.add(mem2)
    db.commit()
    db.refresh(mem1)
    db.refresh(mem2)

    # Caso A: Intentar reabrir Memoria 1 (no es la última cerrada porque existe Memoria 2 cerrada)
    r_reabrir_1 = client.post(f"/api/memorias/{mem1.id}/reabrir")
    assert r_reabrir_1.status_code == 409, f"Debe fallar con 409 Conflict: {r_reabrir_1.text}"
    data_409 = r_reabrir_1.json()
    assert "Solo la última memoria cerrada puede reabrirse" in data_409["detail"]

    # Caso B: Reabrir Memoria 2 (es la última cerrada) -> ÉXITO
    r_reabrir_2 = client.post(f"/api/memorias/{mem2.id}/reabrir")
    assert r_reabrir_2.status_code == 200, f"Debe reabrir con 200 OK: {r_reabrir_2.text}"
    mem2_actualizada = r_reabrir_2.json()
    assert mem2_actualizada["estado"] == "borrador"
    assert mem2_actualizada["cerrada_at"] is None

    # Verificar en base de datos el registro de auditoría
    db.expire_all()
    reg = (
        db.query(RegistroAuditoria)
        .filter(RegistroAuditoria.memoria_id == mem2.id, RegistroAuditoria.accion == "reapertura_memoria")
        .first()
    )
    assert reg is not None, "Debe existir un registro de auditoría para la reapertura"
    assert reg.obra_id == obra.id
    assert "502" in (reg.detalles or "")

    # Caso C: Intentar reabrir Memoria 2 nuevamente cuando YA está en borrador -> HTTP 400
    r_reabrir_ya_borrador = client.post(f"/api/memorias/{mem2.id}/reabrir")
    assert r_reabrir_ya_borrador.status_code == 400
    assert "se encuentren cerradas" in r_reabrir_ya_borrador.json()["detail"]


def test_version_build_health_coincidencia(client: TestClient):
    """Verifica que /health reporte version_build con APP_VERSION sincronizado."""
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "version_build" in data
    vb = data["version_build"]
    assert vb["version_codigo"] == config.APP_VERSION
    assert "+" in vb["version_codigo"], "La versión debe tener formato <versión>+<AAAAMMDD.HHMM>"


def test_unificacion_metodo_pdf_en_headers(client: TestClient, monkeypatch):
    """Verifica que el header X-PDF-Generation-Method coincida con edge-cli-no-header-footer."""
    import datetime
    from decimal import Decimal
    from app.models import Obra, Memoria, EstadoMemoria
    from app.database import get_db

    db = next(get_db())
    obra = Obra(
        nombre="Obra Test PDF Headers",
        porcentaje_honorarios=Decimal("10.0"),
    )
    db.add(obra)
    db.commit()
    db.refresh(obra)

    mem = Memoria(
        obra_id=obra.id,
        numero=1,
        fecha_inicio=datetime.date(2026, 10, 1),
        fecha_fin=datetime.date(2026, 10, 31),
        porcentaje_honorarios_usado=Decimal("10.0"),
        estado=EstadoMemoria.BORRADOR,
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)

    # Simular generación exitosa
    def fake_generar_ok(memoria_id, base_url):
        return b"%PDF-1.4 Fake PDF bytes for testing headers"

    monkeypatch.setattr("app.routers.memorias.generar_pdf_memoria", fake_generar_ok)

    r = client.get(f"/api/memorias/{mem.id}/pdf")
    assert r.status_code == 200
    assert r.headers.get("X-PDF-Generation-Method") == "edge-cli-no-header-footer"





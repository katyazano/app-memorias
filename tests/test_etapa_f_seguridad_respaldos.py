"""Pruebas de la Etapa F: Uso diario, seguridad y respaldos automáticos."""
import os
import zipfile
import tempfile
from pathlib import Path
from datetime import date
import pytest
from fastapi.testclient import TestClient

from app import config
from app.services.backup_service import (
    crear_respaldo_seguro,
    rotar_respaldos,
    listar_respaldos,
    validar_archivo_respaldo,
    verificar_respaldo_diario,
    get_backup_dir,
)
from app.models import Obra, Memoria, EstadoMemoria, EstadoObra, Configuracion
from app.database import SessionLocal


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_seguridad_host_estricto_loopback():
    """Verifica que app.config.HOST sea estrictamente loopback (127.0.0.1) y jamás 0.0.0.0."""
    assert config.HOST in ("127.0.0.1", "localhost")
    assert config.HOST != "0.0.0.0"


def test_archivos_lanzadores_existen():
    """Verifica que los archivos .bat para el uso diario existan y contengan comandos en español."""
    base = config.BASE_DIR
    iniciar_bat = base / "Iniciar Memorias.bat"
    detener_bat = base / "Detener Memorias.bat"
    directo_bat = base / "Crear Acceso Directo.bat"
    manual_md = base / "MANUAL.md"

    assert iniciar_bat.exists(), "Iniciar Memorias.bat debe existir"
    assert detener_bat.exists(), "Detener Memorias.bat debe existir"
    assert directo_bat.exists(), "Crear Acceso Directo.bat debe existir"
    assert manual_md.exists(), "MANUAL.md debe existir"

    content_iniciar = iniciar_bat.read_text(encoding="utf-8", errors="ignore")
    assert "8000" in content_iniciar
    assert "localhost:8000" in content_iniciar

    content_detener = detener_bat.read_text(encoding="utf-8", errors="ignore")
    assert "8000" in content_detener

    content_manual = manual_md.read_text(encoding="utf-8")
    assert "Iniciar Memorias.bat" in content_manual
    assert "BORRAR TODO" in content_manual
    assert "10 copias" in content_manual


def test_backup_service_crear_y_validar_respaldo(db_session):
    """Verifica la generación de respaldo ZIP con sqlite3 backup API y su validación."""
    zip_path, nombre = crear_respaldo_seguro(db_session, origen="test")
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"
    assert nombre.startswith("respaldo_test_")

    # Validar integridad
    valido, mensaje = validar_archivo_respaldo(zip_path)
    assert valido is True
    assert "verificado" in mensaje.lower()

    # Verificar contenido interno
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "data/app.db" in namelist or "app.db" in namelist

    # Limpiar
    if zip_path.exists():
        zip_path.unlink()


def test_rotacion_respaldos_a_10_copias():
    """Verifica que la función de rotación conserve exactamente un máximo de 10 copias."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Crear 15 archivos dummy
        archivos = []
        for i in range(15):
            f = tmp_path / f"respaldo_test_{i:02d}.zip"
            f.write_text("dummy", encoding="utf-8")
            archivos.append(f)

        # Ejecutar rotación a 10
        eliminados = rotar_respaldos(tmp_path, max_copias=10)
        assert len(eliminados) == 5

        restantes = [f for f in tmp_path.iterdir() if f.suffix == ".zip"]
        assert len(restantes) == 10


def test_verificar_respaldo_diario(db_session):
    """Verifica que el respaldo diario se ejecute la primera vez y no se repita en el mismo día."""
    # Limpiar clave previa si existe
    db_session.query(Configuracion).filter(
        Configuracion.clave == "ultimo_respaldo_diario_fecha"
    ).delete()
    db_session.commit()

    # Primera vez: debe retornar True y generar respaldo
    primer_intento = verificar_respaldo_diario(db_session)
    assert primer_intento is True

    # Segunda vez el mismo día: debe retornar False sin duplicar
    segundo_intento = verificar_respaldo_diario(db_session)
    assert segundo_intento is False


def test_api_respaldos_endpoints(client: TestClient, db_session):
    """Prueba los endpoints de respaldos en la API."""
    # 1. Listar respaldos
    res_list = client.get("/configuracion/sistema/respaldos")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert "carpeta_actual" in data_list
    assert "respaldos" in data_list

    # 2. Generar respaldo manual
    res_gen = client.post("/configuracion/sistema/respaldos/generar")
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["status"] == "ok"
    nombre_creado = gen_data["nombre"]

    # 3. Descargar el respaldo creado
    res_descarga = client.get(f"/configuracion/sistema/respaldos/descargar/{nombre_creado}")
    assert res_descarga.status_code == 200
    assert len(res_descarga.content) > 0

    # 4. Intento con nombre de archivo no válido debe retornar 400
    res_bad_name = client.get("/configuracion/sistema/respaldos/descargar/archivo_malicioso.txt")
    assert res_bad_name.status_code == 400

    # 5. Archivo inexistente debe retornar 404
    res_not_found = client.get("/configuracion/sistema/respaldos/descargar/respaldo_inexistente_1234.zip")
    assert res_not_found.status_code == 404


def test_api_restablecer_datos_vacios(client: TestClient, db_session):
    """Prueba el restablecimiento a datos vacíos con validación de 'BORRAR TODO'."""
    # 1. Crear una obra de prueba
    obra = Obra(nombre="Obra Para Borrar", ubicacion="Guadalajara", propietario="Cliente Test", estado=EstadoObra.EN_CURSO)
    db_session.add(obra)
    db_session.commit()

    assert db_session.query(Obra).count() > 0

    # 2. Intentar restablecer con confirmación incorrecta -> Error 422
    res_bad = client.post("/configuracion/sistema/restablecer-datos-vacios", json={"confirmacion": "borrar"})
    assert res_bad.status_code == 422
    assert "BORRAR TODO" in res_bad.json()["detail"]

    # 3. Restablecer con 'BORRAR TODO' -> Éxito 200
    res_ok = client.post("/configuracion/sistema/restablecer-datos-vacios", json={"confirmacion": "BORRAR TODO"})
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "ok"
    assert "respaldo_previo" in res_ok.json()

    # 4. Verificar que la base de datos de obras quedó vacía
    assert db_session.query(Obra).count() == 0


def test_cierre_memoria_genera_respaldo_automatico(client: TestClient, db_session):
    """Verifica que cerrar una memoria genere automáticamente un respaldo con origen cierre_memoria."""
    from decimal import Decimal
    from app.services.memoria_service import cerrar_memoria, guardar_memoria
    from app.schemas import MemoriaGuardar, RenglonEdit
    from app.models import Gasto, MetodoPago, OrigenGasto

    obra = Obra(nombre="Obra Auto Respaldo", porcentaje_honorarios=Decimal("10.00"), estado=EstadoObra.EN_CURSO)
    db_session.add(obra)
    db_session.commit()

    gasto = Gasto(
        obra_id=obra.id,
        concepto_resumido="Materiales",
        comprobante="F-100",
        tipo_comprobante="FACTURA",
        importe=Decimal("1500.00"),
        metodo_pago=MetodoPago.TRANSFERENCIA,
        origen=OrigenGasto.MANUAL,
        fecha=date(2026, 10, 15),
    )
    db_session.add(gasto)
    db_session.commit()

    memoria_data = MemoriaGuardar(
        obra_id=obra.id,
        fecha_inicio=date(2026, 10, 1),
        fecha_fin=date(2026, 10, 31),
        numero=1,
        renglones=[
            RenglonEdit(ref_tipo="gasto", ref_id=gasto.id, categoria="transferencia", incluido=True)
        ],
    )
    mem = guardar_memoria(db_session, memoria_data)
    db_session.commit()

    # Cerrar memoria
    cerrada = cerrar_memoria(db_session, mem.id)
    assert cerrada.estado == EstadoMemoria.CERRADA

    # Verificar que en la carpeta de respaldos existe uno con origen cierre_memoria
    respaldos = listar_respaldos(db_session)
    cierres = [r for r in respaldos if "cierre" in r["nombre"]]
    assert len(cierres) > 0

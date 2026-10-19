import json
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import pandas as pd
import requests
import streamlit as st

# ==========================================
# Configuración y Estilos de la Aplicación
# ==========================================
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="Control de Obras & Memorias",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos visuales limpios y modernos
st.markdown(
    """
    <style>
    .main-title {
        font-size: 26px;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 4px;
    }
    .sub-title {
        font-size: 14px;
        color: #64748B;
        margin-bottom: 20px;
    }
    .metric-container {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================
# Funciones Cliente para Comunicación con la API
# ==========================================
def api_get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    """Realiza una petición GET al backend con manejo de errores en español."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=12)
        if response.status_code == 200:
            return response.json()
        st.error(f"⚠️ Error del servidor ({response.status_code}) al consultar `{endpoint}`: {response.text}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"❌ No se puede conectar con el servidor backend en **{API_BASE_URL}**. Verifique que FastAPI esté en ejecución.")
        return None
    except Exception as e:
        st.error(f"❌ Ocurrió un error inesperado al consultar `{endpoint}`: {str(e)}")
        return None


def api_get_binary(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[bytes]:
    """Realiza una petición GET para descargar contenido binario (PDF) del backend."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=25)
        if response.status_code == 200:
            return response.content
        st.error(f"⚠️ Error al generar documento PDF ({response.status_code}): {response.text}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"❌ No se pudo conectar con el backend en **{API_BASE_URL}**.")
        return None
    except Exception as e:
        st.error(f"❌ Error al descargar PDF: {str(e)}")
        return None


def api_post_binary(endpoint: str, payload: Any) -> Optional[bytes]:
    """Realiza una petición POST enviando un cuerpo JSON para recibir contenido binario (PDF)."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.content
        st.error(f"⚠️ Error al generar documento PDF ({response.status_code}): {response.text}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"❌ No se pudo conectar con el backend en **{API_BASE_URL}**.")
        return None
    except Exception as e:
        st.error(f"❌ Error al descargar PDF: {str(e)}")
        return None


def api_post(endpoint: str, payload: Any) -> Optional[Any]:
    """Realiza una petición POST enviando un cuerpo JSON."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code in (200, 201):
            return response.json()
        st.error(f"⚠️ Error del servidor ({response.status_code}) al registrar en `{endpoint}`: {response.text}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"❌ No se pudo establecer conexión con el backend en **{API_BASE_URL}**.")
        return None
    except Exception as e:
        st.error(f"❌ Error al enviar datos a `{endpoint}`: {str(e)}")
        return None


def api_patch(endpoint: str, payload: Any) -> Optional[Any]:
    """Realiza una petición PATCH enviando un cuerpo JSON para actualizar datos."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.patch(url, json=payload, timeout=15)
        if response.status_code in (200, 201):
            return response.json()
        st.error(f"⚠️ Error del servidor ({response.status_code}) al actualizar `{endpoint}`: {response.text}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"❌ No se pudo conectar con el servidor backend en **{API_BASE_URL}**.")
        return None
    except Exception as e:
        st.error(f"❌ Error al actualizar en `{endpoint}`: {str(e)}")
        return None


def api_delete(endpoint: str) -> bool:
    """Realiza una petición DELETE al backend para eliminar registros."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.delete(url, timeout=15)
        if response.status_code in (200, 204):
            return True
        st.error(f"⚠️ Error del servidor ({response.status_code}) al eliminar `{endpoint}`: {response.text}")
        return False
    except requests.exceptions.ConnectionError:
        st.error(f"❌ No se pudo conectar con el servidor backend en **{API_BASE_URL}**.")
        return False
    except Exception as e:
        st.error(f"❌ Error al eliminar en `{endpoint}`: {str(e)}")
        return False


def api_upload_invoices_batch(uploaded_files: list) -> Optional[List[Dict[str, Any]]]:
    """Envía un lote de archivos XML y PDF al endpoint POST /invoices/upload."""
    url = f"{API_BASE_URL}/invoices/upload"
    try:
        files_payload = [
            ("files", (f.name, f.getvalue(), "application/octet-stream"))
            for f in uploaded_files
        ]
        response = requests.post(url, files=files_payload, timeout=45)
        if response.status_code == 200:
            return response.json()
        st.error(f"⚠️ Error al procesar el lote de archivos ({response.status_code}): {response.text}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Error de conexión con el backend al subir los archivos.")
        return None
    except Exception as e:
        st.error(f"❌ Error al procesar archivos: {str(e)}")
        return None


# ==========================================
# Inicialización del Estado de Sesión
# ==========================================
if "selected_project_id" not in st.session_state:
    st.session_state["selected_project_id"] = None

if "selected_project_name" not in st.session_state:
    st.session_state["selected_project_name"] = "Ningún proyecto seleccionado"

if "temp_invoices_df" not in st.session_state:
    st.session_state["temp_invoices_df"] = pd.DataFrame()

if "memory_draft_invoices" not in st.session_state:
    st.session_state["memory_draft_invoices"] = []

if "memory_draft_payments" not in st.session_state:
    st.session_state["memory_draft_payments"] = []

if "memory_loaded_params" not in st.session_state:
    st.session_state["memory_loaded_params"] = {}


# ==========================================
# Barra Lateral de Navegación Global (Sidebar)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3233/3233483.png", width=60)
    st.title("Gestión de Obras")
    st.markdown("---")

    # 1. Selector de Proyecto Activo
    projects_data = api_get("/projects/")
    project_options = {}

    if projects_data:
        for p in projects_data:
            label = f"{p['name']} — Cliente: {p.get('client_name', 'N/A')}"
            project_options[label] = p["id"]

        selected_label = st.selectbox(
            "🏗️ Proyecto Activo",
            options=list(project_options.keys()),
            index=0,
            help="Seleccione la obra en la que desea cargar facturas, nómina o generar memorias.",
        )
        st.session_state["selected_project_id"] = project_options[selected_label]
        st.session_state["selected_project_name"] = selected_label
        st.success(f"Obra activa: **{selected_label.split(' — ')[0]}**")
    else:
        st.warning("No hay proyectos registrados en el sistema.")

    st.markdown("---")
    st.subheader("🧭 Menú de Vistas")
    selected_view = st.radio(
        "Seleccione un módulo:",
        options=[
            "🏗️ Gestión de Obras",
            "📥 Carga de Facturas",
            "👷 Empleados y Mano de Obra",
            "📝 Registro de Pagos y Notas",
            "📊 Generador de Memorias",
        ],
        index=0,
    )

    st.markdown("---")
    st.caption(f"Backend API: `{API_BASE_URL}`")


current_project_id = st.session_state.get("selected_project_id")


# =========================================================================
# VISTA 0: Gestión y Catálogo de Obras (CRUD Completo de Proyectos)
# =========================================================================
if selected_view == "🏗️ Gestión de Obras":
    st.markdown('<div class="main-title">🏗️ Gestión y Control de Obras</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Panel de administración para dar de alta nuevos proyectos, modificar información de clientes, supervisar estados de avance y gestionar el ciclo de vida de cada obra.</div>', unsafe_allow_html=True)

    # 1. Obtener todas las obras
    projects_list = api_get("/projects/") or []

    # Métricas de resumen general
    total_obras = len(projects_list)
    en_proceso = sum(1 for p in projects_list if p.get("status") == "in_progress")
    pausadas = sum(1 for p in projects_list if p.get("status") == "paused")
    concluidas = sum(1 for p in projects_list if p.get("status") == "completed")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("📦 Total Obras Registradas", total_obras)
    with col_m2:
        st.metric("🟢 En Construcción / Activas", en_proceso)
    with col_m3:
        st.metric("🟡 Pausadas / En Espera", pausadas)
    with col_m4:
        st.metric("🔵 Concluidas / Entregadas", concluidas)

    st.markdown("---")

    tab_catalogo, tab_crear, tab_editar, tab_eliminar = st.tabs([
        "📋 Catálogo y Balance de Obras",
        "➕ Registrar Nueva Obra",
        "✏️ Editar Información de Obra",
        "🗑️ Eliminar Obra",
    ])

    # --- PESTAÑA 1: CATÁLOGO Y BALANCE ---
    with tab_catalogo:
        st.markdown("#### 📋 Obras Registradas en el Sistema")
        if projects_list:
            status_map = {
                "in_progress": "🟢 En Proceso",
                "paused": "🟡 Pausada",
                "completed": "🔵 Concluida",
            }

            tabla_obras = []
            for p in projects_list:
                st_code = p.get("status", "in_progress")
                st_label = status_map.get(st_code, st_code)
                tabla_obras.append({
                    "ID": str(p.get("id")),
                    "Nombre de la Obra": p.get("name"),
                    "Cliente / Propietario": p.get("client_name"),
                    "Fecha de Inicio": p.get("start_date"),
                    "Estado": st_label,
                })

            df_obras = pd.DataFrame(tabla_obras)
            st.dataframe(
                df_obras,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": None,  # Ocultar UUID
                    "Nombre de la Obra": st.column_config.TextColumn("Nombre de la Obra", width="large"),
                    "Cliente / Propietario": st.column_config.TextColumn("Cliente / Propietario", width="medium"),
                    "Fecha de Inicio": st.column_config.DateColumn("Fecha de Inicio"),
                    "Estado": st.column_config.TextColumn("Estado Actual"),
                }
            )

            # Ficha rápida de la obra seleccionada
            st.markdown("---")
            st.markdown("#### 🔍 Ficha y Balance Acumulado por Obra")
            obra_dict = {f"{p['name']} (Cliente: {p.get('client_name')})": p for p in projects_list}
            sel_ficha_label = st.selectbox(
                "Seleccione una obra para consultar su balance histórico:",
                options=list(obra_dict.keys()),
                key="sel_ficha_obra"
            )
            sel_obra = obra_dict[sel_ficha_label]
            obra_id = sel_obra["id"]

            # Consultar balance general
            with st.spinner("Consultando balance acumulado de la obra..."):
                mem_full = api_get(
                    f"/projects/{obra_id}/memory",
                    params={"start_date": sel_obra.get("start_date", "2020-01-01"), "end_date": str(date.today() + timedelta(days=365))}
                )

            if mem_full:
                summ = mem_full.get("summary", {})
                col_b1, col_b2, col_b3, col_b4 = st.columns(4)
                with col_b1:
                    st.metric("📦 Facturas CFDI", f"${float(summ.get('total_invoices_amount', 0.0)):,.2f}", f"{summ.get('invoices_count', 0)} comprobantes")
                with col_b2:
                    st.metric("👷 Nómina y Pagos", f"${float(summ.get('total_payments_amount', 0.0)):,.2f}", f"{summ.get('payments_count', 0)} movimientos")
                with col_b3:
                    gastos_directos = float(summ.get('subtotal_transferencias', 0.0)) + float(summ.get('subtotal_efectivo', 0.0)) + float(summ.get('subtotal_rayas', 0.0))
                    st.metric("💵 Gastos Directos", f"${gastos_directos:,.2f}")
                with col_b4:
                    gran_tot = float(summ.get('gran_total_obra', 0.0) or summ.get('gran_total', 0.0))
                    st.metric("💰 Gran Total Acumulado", f"${gran_tot:,.2f}")
        else:
            st.info("No hay obras registradas actualmente. Utilice la pestaña **➕ Registrar Nueva Obra** para comenzar.")

    # --- PESTAÑA 2: REGISTRAR NUEVA OBRA ---
    with tab_crear:
        st.markdown("#### ➕ Alta de Nuevo Proyecto de Construcción")
        with st.form("form_alta_obra", clear_on_submit=True):
            col_cr1, col_cr2 = st.columns(2)
            with col_cr1:
                nuevo_nom = st.text_input("Nombre de la Obra / Proyecto:", placeholder="Ej. Residencia Puerta de Hierro")
                nuevo_cli = st.text_input("Nombre del Cliente / Propietario:", placeholder="Ej. Ing. Carlos Mendoza")
            with col_cr2:
                nueva_fecha = st.date_input("Fecha de Inicio de la Obra:", value=date.today())
                nuevo_estado = st.selectbox(
                    "Estado Inicial del Proyecto:",
                    options=[
                        ("in_progress", "🟢 En Proceso (Activa)"),
                        ("paused", "🟡 Pausada (En Espera)"),
                        ("completed", "🔵 Concluida"),
                    ],
                    format_func=lambda x: x[1],
                )

            btn_crear_obra = st.form_submit_button("🏗️ Registrar y Guardar Obra", type="primary", use_container_width=True)

            if btn_crear_obra:
                if not nuevo_nom.strip() or not nuevo_cli.strip():
                    st.error("Por favor proporcione el nombre de la obra y el nombre del cliente.")
                else:
                    payload = {
                        "name": nuevo_nom.strip(),
                        "client_name": nuevo_cli.strip(),
                        "start_date": str(nueva_fecha),
                        "status": nuevo_estado[0],
                    }
                    res_obra = api_post("/projects/", payload)
                    if res_obra:
                        st.toast("🎉 ¡Obra creada exitosamente!", icon="🏗️")
                        st.success(f"La obra **{res_obra.get('name')}** ha sido dada de alta con folio `{res_obra.get('id')}`.")
                        st.session_state["selected_project_id"] = res_obra.get("id")
                        st.session_state["selected_project_name"] = f"{res_obra.get('name')} — Cliente: {res_obra.get('client_name')}"
                        st.rerun()

    # --- PESTAÑA 3: EDITAR OBRA ---
    with tab_editar:
        st.markdown("#### ✏️ Modificar Información de una Obra Existente")
        if projects_list:
            edit_options = {f"{p['name']} (Cliente: {p.get('client_name')})": p for p in projects_list}
            sel_edit_label = st.selectbox(
                "Seleccione la obra que desea actualizar:",
                options=list(edit_options.keys()),
                key="sel_edit_obra"
            )
            obra_a_editar = edit_options[sel_edit_label]

            with st.form("form_editar_obra"):
                col_ed1, col_ed2 = st.columns(2)
                with col_ed1:
                    edit_nom = st.text_input("Nombre de la Obra:", value=obra_a_editar.get("name", ""))
                    edit_cli = st.text_input("Nombre del Cliente:", value=obra_a_editar.get("client_name", ""))
                with col_ed2:
                    try:
                        f_init = date.fromisoformat(obra_a_editar.get("start_date", str(date.today())))
                    except Exception:
                        f_init = date.today()
                    edit_fecha = st.date_input("Fecha de Inicio:", value=f_init)

                    status_idx = 0
                    if obra_a_editar.get("status") == "paused":
                        status_idx = 1
                    elif obra_a_editar.get("status") == "completed":
                        status_idx = 2

                    edit_estado = st.selectbox(
                        "Estado de la Obra:",
                        options=[
                            ("in_progress", "🟢 En Proceso (Activa)"),
                            ("paused", "🟡 Pausada (En Espera)"),
                            ("completed", "🔵 Concluida"),
                        ],
                        index=status_idx,
                        format_func=lambda x: x[1],
                    )

                btn_actualizar = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)

                if btn_actualizar:
                    patch_payload = {
                        "name": edit_nom.strip(),
                        "client_name": edit_cli.strip(),
                        "start_date": str(edit_fecha),
                        "status": edit_estado[0],
                    }
                    res_patch = api_patch(f"/projects/{obra_a_editar['id']}", patch_payload)
                    if res_patch:
                        st.toast("✅ ¡Obra actualizada correctamente!", icon="👍")
                        st.success(f"Se actualizaron los datos de la obra **{res_patch.get('name')}**.")
                        st.rerun()
        else:
            st.info("No hay obras disponibles para editar.")

    # --- PESTAÑA 4: ELIMINAR OBRA ---
    with tab_eliminar:
        st.markdown("#### 🗑️ Dar de Baja Definitiva una Obra")
        if projects_list:
            del_options = {f"{p['name']} (Cliente: {p.get('client_name')})": p for p in projects_list}
            sel_del_label = st.selectbox(
                "Seleccione la obra que desea eliminar:",
                options=list(del_options.keys()),
                key="sel_del_obra"
            )
            obra_a_eliminar = del_options[sel_del_label]

            st.warning(
                f"⚠️ **Atención:** Está a punto de eliminar la obra **{obra_a_eliminar.get('name')}**.\n\n"
                "Por integridad de la base de datos, esta acción también eliminará todas las facturas y pagos asociados a este proyecto. **Esta acción no se puede deshacer.**"
            )

            confirm_check = st.checkbox(
                f"He leído la advertencia y confirmo que deseo eliminar definitivamente la obra '{obra_a_eliminar.get('name')}'.",
                key="confirm_del_check"
            )

            if st.button("🗑️ Eliminar Obra Permanentemente", type="primary", disabled=not confirm_check):
                with st.spinner("Eliminando obra y registros asociados..."):
                    success = api_delete(f"/projects/{obra_a_eliminar['id']}")

                if success:
                    st.toast("🗑️ Obra eliminada exitosamente.", icon="🗑️")
                    st.success(f"La obra **{obra_a_eliminar.get('name')}** fue eliminada de la base de datos.")
                    if st.session_state.get("selected_project_id") == obra_a_eliminar["id"]:
                        st.session_state["selected_project_id"] = None
                        st.session_state["selected_project_name"] = "Ningún proyecto seleccionado"
                    st.rerun()
        else:
            st.info("No hay obras registradas para eliminar.")


# =========================================================================
# VISTA 1: Carga de Facturas (Dual Workflow: XML Exacto + PDF a S3)
# =========================================================================
elif selected_view == "📥 Carga de Facturas":
    st.markdown('<div class="main-title">📥 Centro de Carga de Facturas (XML + PDF)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Cargue los comprobantes fiscales de proveedores. Los archivos XML garantizan 100% de precisión y los PDFs se respaldan en la nube para auditoría visual.</div>', unsafe_allow_html=True)

    if not current_project_id:
        st.warning("⚠️ Debe seleccionar o dar de alta un Proyecto Activo en la barra lateral para continuar.")
    else:
        # Banner de instrucciones claras
        st.info("💡 **Extracción Inteligente**: Sube los archivos **XML** y **PDF** de tus facturas juntos (ej. `factura1.xml` y `factura1.pdf`). El sistema lee automáticamente el **Proveedor oficial**, **Folio**, **Concepto**, **Fecha** e **Importe** directamente del XML, y almacena el PDF en AWS S3.")

        uploaded_files = st.file_uploader(
            "Seleccione o arrastre los archivos XML y/o PDF:",
            type=["pdf", "xml"],
            accept_multiple_files=True,
            help="Puede seleccionar varios archivos simultáneamente. El sistema empareja automáticamente los XML y PDF con el mismo nombre y lee los proveedores del XML.",
        )

        # Botón de Procesamiento y Extracción
        if uploaded_files:
            if st.button("⚙️ Procesar y Extraer Facturas del XML", type="primary"):
                with st.spinner("Leyendo comprobantes XML y subiendo PDFs a S3..."):
                    parsed_response = api_upload_invoices_batch(uploaded_files)

                if parsed_response:
                    parsed_list = []
                    for item in parsed_response:
                        raw_fecha = item.get("fecha")
                        if not raw_fecha or str(raw_fecha).strip().lower() in ("none", "null", "", "nat"):
                            clean_fecha = date.today()
                        else:
                            try:
                                dt = pd.to_datetime(raw_fecha, errors="coerce")
                                clean_fecha = dt.date() if pd.notnull(dt) else date.today()
                            except Exception:
                                clean_fecha = date.today()

                        parsed_list.append({
                            "proveedor": str(item.get("proveedor") or "PROVEEDOR GENERAL"),
                            "comprobante": str(item.get("comprobante") or "CFDI-SIN-FOLIO"),
                            "concepto": str(item.get("concepto") or "Materiales / Servicios de Obra"),
                            "importe": float(item.get("importe", 0.0) or 0.0),
                            "fecha": clean_fecha,
                            "pdf_s3_url": item.get("pdf_s3_url", ""),
                            "s3_object_key": item.get("s3_object_key") or item.get("pdf_s3_url", ""),
                            "has_xml": "✅ XML" if item.get("has_xml") else "⚠️ Solo PDF",
                            "has_pdf": "✅ PDF en S3" if item.get("has_pdf") else "Sin PDF",
                            "is_parsed_automatically": True,
                            "project_id": current_project_id,
                        })

                    df = pd.DataFrame(parsed_list)
                    if not df.empty and "fecha" in df.columns:
                        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").fillna(pd.to_datetime(date.today())).dt.date
                    st.session_state["temp_invoices_df"] = df
                    st.toast(f"✅ ¡Se procesaron {len(parsed_list)} factura(s) con éxito!", icon="📋")

        # Tabla Interactiva para Revisión y Corrección de Datos
        if not st.session_state["temp_invoices_df"].empty:
            st.markdown("---")
            st.subheader("✏️ Revisión y Confirmación de Facturas")
            st.info("💡 **Edición Flexible**: El proveedor fue leído automáticamente del XML. Puede editar su nombre o cualquier otro dato directamente en la tabla antes de guardar.")

            edited_df = st.data_editor(
                st.session_state["temp_invoices_df"],
                key="editor_facturas",
                use_container_width=True,
                column_config={
                    "proveedor": st.column_config.TextColumn(
                        "Proveedor (Leído del XML)",
                        help="Nombre del proveedor extraído del XML. Puede editarlo si desea registrarlo con otro nombre.",
                        required=True,
                    ),
                    "comprobante": st.column_config.TextColumn("Folio Fiscal / UUID", required=True),
                    "concepto": st.column_config.TextColumn("Concepto / Descripción", required=True),
                    "importe": st.column_config.NumberColumn("Importe Total ($)", format="$%.2f", min_value=0.0, required=True),
                    "fecha": st.column_config.DateColumn("Fecha de Emisión", required=True),
                    "has_xml": st.column_config.TextColumn("Origen Fiscal", disabled=True),
                    "has_pdf": st.column_config.TextColumn("Respaldo S3", disabled=True),
                    "pdf_s3_url": st.column_config.LinkColumn("Enlace al PDF", disabled=True),
                    "s3_object_key": None,  # Ocultar campos técnicos
                    "is_parsed_automatically": None,
                    "supplier_id": None,
                    "project_id": None,
                },
                hide_index=True,
            )

            col_guardar, col_limpiar = st.columns([2, 5])
            with col_guardar:
                if st.button("💾 Confirmar y Guardar en Base de Datos", type="primary", use_container_width=True):
                    bulk_payload = []
                    for _, row in edited_df.iterrows():
                        s3_stored_val = str(row.get("s3_object_key") or row.get("pdf_s3_url") or "")
                        bulk_payload.append({
                            "comprobante": str(row["comprobante"]),
                            "proveedor": str(row["proveedor"]),
                            "concepto": str(row["concepto"]),
                            "importe": float(row["importe"]),
                            "fecha": str(row["fecha"]),
                            "pdf_s3_url": s3_stored_val,
                            "is_parsed_automatically": True,
                            "project_id": current_project_id,
                        })

                    guardar_res = api_post("/invoices/bulk", bulk_payload)
                    if guardar_res:
                        st.session_state["temp_invoices_df"] = pd.DataFrame()
                        st.toast("🎉 ¡Todas las facturas fueron guardadas exitosamente en la base de datos!", icon="✅")
                        st.success("✅ Facturas registradas satisfactoriamente con sus respectivos proveedores.")

            with col_limpiar:
                if st.button("🗑️ Descartar Lote Actual"):
                    st.session_state["temp_invoices_df"] = pd.DataFrame()
                    st.rerun()


# =========================================================================
# VISTA 2: Gestión de Empleados y Control de Nómina Acumulada
# =========================================================================
elif selected_view == "👷 Empleados y Mano de Obra":
    st.markdown('<div class="main-title">👷 Plantilla de Trabajadores y Control de Nómina</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Administre el catálogo de trabajadores, defina puestos y sueldos diarios pactados, y consulte la nómina total acumulada que se les ha pagado a la fecha.</div>', unsafe_allow_html=True)

    workers_summary = api_get("/workers/summary") or []

    # Métricas generales de la plantilla
    total_workers = len(workers_summary)
    total_nomina_acumulada = sum(float(w.get("total_payroll_accumulated", 0.0) or 0.0) for w in workers_summary)
    promedio_sueldo = (sum(float(w.get("daily_rate", 0.0) or 0.0) for w in workers_summary) / total_workers) if total_workers > 0 else 0.0

    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        st.metric("👷 Total Trabajadores en Plantilla", total_workers)
    with col_w2:
        st.metric("💰 Nómina Acumulada a la Fecha", f"${total_nomina_acumulada:,.2f}")
    with col_w3:
        st.metric("📊 Sueldo Diario Promedio", f"${promedio_sueldo:,.2f}")

    st.markdown("---")

    tab_w_lista, tab_w_alta, tab_w_pago, tab_w_edit = st.tabs([
        "📋 Plantilla y Nómina Acumulada",
        "➕ Registrar Nuevo Empleado",
        "💰 Pagar Nómina Directa",
        "✏️ Modificar o Dar de Baja",
    ])

    # --- PESTAÑA 1: PLANTILLA Y NÓMINA ACUMULADA ---
    with tab_w_lista:
        st.markdown("#### 📋 Catálogo de Empleados y Nómina Acumulada a la Fecha")
        if workers_summary:
            w_rows = []
            for w in workers_summary:
                w_rows.append({
                    "Nombre Completo": w.get("full_name"),
                    "Oficio / Rol": w.get("role"),
                    "Sueldo Diario ($)": float(w.get("daily_rate", 0.0)),
                    "Nómina Pagada a la Fecha ($)": float(w.get("total_payroll_accumulated", 0.0) or 0.0),
                    "Pagos Recibidos": int(w.get("total_payments_count", 0) or 0),
                    "Último Pago": str(w.get("last_payment_date") or "Sin pagos"),
                    "ID": str(w.get("id")),
                })
            df_workers = pd.DataFrame(w_rows)
            st.dataframe(
                df_workers,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Sueldo Diario ($)": st.column_config.NumberColumn("Sueldo Diario ($)", format="$%.2f"),
                    "Nómina Pagada a la Fecha ($)": st.column_config.NumberColumn("Nómina Acumulada ($)", format="$%.2f"),
                    "ID": None,
                },
            )
        else:
            st.info("No hay trabajadores registrados en el sistema. Utilice la pestaña siguiente para dar de alta.")

    # --- PESTAÑA 2: REGISTRAR EMPLEADO ---
    with tab_w_alta:
        st.markdown("#### ➕ Dar de Alta un Nuevo Empleado")
        with st.form("form_alta_empleado", clear_on_submit=True):
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                nuevo_emp_nombre = st.text_input("Nombre Completo del Trabajador:", placeholder="Ej. Carlos Méndez Salgado")
                nuevo_emp_rol = st.selectbox(
                    "Oficio o Puesto:",
                    [
                        "Maestro de Obra",
                        "Albañil",
                        "Fierrero",
                        "Electricista",
                        "Plomero",
                        "Carpintero de Obra",
                        "Pintor",
                        "Yesero / Tablaroquero",
                        "Herrero",
                        "Ayudante General",
                        "Operador de Maquinaria",
                    ],
                )
            with col_a2:
                nuevo_emp_tarifa = st.number_input("Sueldo o Tarifa Diaria Pactada ($):", min_value=0.0, value=400.0, step=50.0)

            btn_crear_emp = st.form_submit_button("💾 Guardar Trabajador en Catálogo", type="primary", use_container_width=True)
            if btn_crear_emp:
                if not nuevo_emp_nombre.strip():
                    st.error("El nombre del trabajador no puede estar vacío.")
                else:
                    emp_res = api_post("/workers/", {
                        "full_name": nuevo_emp_nombre.strip(),
                        "role": nuevo_emp_rol,
                        "daily_rate": nuevo_emp_tarifa,
                    })
                    if emp_res:
                        st.toast("🎉 ¡Trabajador dado de alta exitosamente!", icon="👷")
                        st.success(f"Trabajador **{emp_res.get('full_name')}** ({emp_res.get('role')}) registrado.")
                        st.rerun()

    # --- PESTAÑA 3: PAGAR NÓMINA DIRECTA ---
    with tab_w_pago:
        st.markdown("#### 💰 Registrar Dispersión de Nómina a Trabajador")
        if not current_project_id:
            st.warning("⚠️ Seleccione una Obra Activa en la barra lateral para imputar el gasto de nómina.")
        elif not workers_summary:
            st.warning("No hay empleados registrados en el catálogo.")
        else:
            w_pay_options = {f"{w['full_name']} — {w['role']} (${float(w['daily_rate']):,.2f}/día)": w for w in workers_summary}
            sel_w_label = st.selectbox("Seleccione el Trabajador:", options=list(w_pay_options.keys()))
            selected_worker_obj = w_pay_options[sel_w_label]

            with st.form("form_pago_directo_nomina", clear_on_submit=True):
                col_dp1, col_dp2 = st.columns(2)
                with col_dp1:
                    monto_defecto = float(selected_worker_obj.get("daily_rate", 350.0)) * 6.0
                    pago_nomina_monto = st.number_input("Monto de Raya / Sueldo ($):", min_value=1.0, value=monto_defecto, step=100.0)
                    pago_nomina_fecha = st.date_input("Fecha del Pago:", value=date.today())
                with col_dp2:
                    pago_nomina_desc = st.text_area(
                        "Concepto o Detalle de la Raya:",
                        value=f"Pago de raya semanal - Trabajo de {selected_worker_obj.get('role').lower()}",
                    )

                btn_pago_nom = st.form_submit_button("💰 Registrar Pago de Nómina", type="primary", use_container_width=True)
                if btn_pago_nom:
                    res_nom = api_post("/payments/", {
                        "project_id": current_project_id,
                        "worker_id": selected_worker_obj["id"],
                        "amount": pago_nomina_monto,
                        "payment_type": "payroll",
                        "date_paid": str(pago_nomina_fecha),
                        "description": pago_nomina_desc,
                    })
                    if res_nom:
                        st.toast("✅ ¡Nómina registrada y sumada al acumulado!", icon="🎉")
                        st.success(f"Pago de ${pago_nomina_monto:,.2f} registrado exitosamente a **{selected_worker_obj.get('full_name')}**.")
                        st.rerun()

    # --- PESTAÑA 4: EDITAR O DAR DE BAJA ---
    with tab_w_edit:
        st.markdown("#### ✏️ Actualizar o Eliminar Trabajador")
        if workers_summary:
            w_edit_options = {f"{w['full_name']} — {w['role']}": w for w in workers_summary}
            sel_w_edit_label = st.selectbox("Seleccione trabajador para actualizar:", options=list(w_edit_options.keys()), key="sel_w_edit")
            worker_target = w_edit_options[sel_w_edit_label]

            with st.form("form_editar_worker"):
                col_we1, col_we2 = st.columns(2)
                with col_we1:
                    edit_w_name = st.text_input("Nombre Completo:", value=worker_target.get("full_name"))
                    edit_w_role = st.text_input("Oficio / Rol:", value=worker_target.get("role"))
                with col_we2:
                    edit_w_rate = st.number_input("Sueldo Diario ($):", min_value=0.0, value=float(worker_target.get("daily_rate", 0.0)), step=50.0)

                btn_guardar_w = st.form_submit_button("💾 Guardar Cambios", type="primary")
                if btn_guardar_w:
                    res_pw = api_patch(f"/workers/{worker_target['id']}", {
                        "full_name": edit_w_name.strip(),
                        "role": edit_w_role.strip(),
                        "daily_rate": edit_w_rate,
                    })
                    if res_pw:
                        st.toast("✅ Trabajador actualizado con éxito.", icon="👍")
                        st.rerun()

            st.markdown("---")
            if st.button("🗑️ Eliminar Trabajador del Catálogo", type="secondary"):
                if api_delete(f"/workers/{worker_target['id']}"):
                    st.toast("🗑️ Trabajador eliminado.", icon="🗑️")
                    st.rerun()
        else:
            st.info("No hay trabajadores para gestionar.")


# =========================================================================
# VISTA 3: Registro de Pagos, Transferencias y Notas de Efectivo
# =========================================================================
elif selected_view == "📝 Registro de Pagos y Notas":
    st.markdown('<div class="main-title">📝 Registro de Transferencias y Notas en Efectivo</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Registre pagos directos por transferencia bancaria y notas de gastos menores o caja chica en efectivo.</div>', unsafe_allow_html=True)

    if not current_project_id:
        st.warning("⚠️ Por favor seleccione una Obra Activa en la barra lateral.")
    else:
        tab_transf, tab_notas = st.tabs([
            "🏦 Transferencias Bancarias",
            "📋 Notas Generales / Efectivo",
        ])

        # --- PESTAÑA 1: TRANSFERENCIAS ---
        with tab_transf:
            st.markdown("#### Registro de Transferencias y Pagos Bancarios Directos")
            with st.form("form_transferencia", clear_on_submit=True):
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    monto_transf = st.number_input("Monto de la Transferencia ($):", min_value=1.0, value=5000.00, step=500.0)
                    fecha_transf = st.date_input("Fecha de Transferencia:", value=date.today(), key="f_transf")

                with col_t2:
                    concepto_transf = st.text_area("Detalle / Referencia Bancaria:", value="Anticipo para renta de retroexcavadora CAT 416")

                btn_transf = st.form_submit_button("🏦 Registrar Transferencia Bancaria", type="primary", use_container_width=True)

                if btn_transf:
                    payload = {
                        "project_id": current_project_id,
                        "worker_id": None,
                        "amount": float(monto_transf),
                        "payment_type": "bank_transfer",
                        "date_paid": str(fecha_transf),
                        "description": concepto_transf,
                    }
                    res = api_post("/payments/", payload)
                    if res:
                        st.toast("✅ ¡Transferencia bancaria registrada exitosamente!", icon="🎉")
                        st.success(f"Transferencia guardada con éxito (Folio: `{res.get('id')}`).")

        # --- PESTAÑA 2: NOTAS GENERALES ---
        with tab_notas:
            st.markdown("#### Registro de Notas de Gasto Menor y Caja Chica")
            with st.form("form_nota", clear_on_submit=True):
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    monto_nota = st.number_input("Importe del Gasto ($):", min_value=0.0, value=150.00, step=20.0)
                    fecha_nota = st.date_input("Fecha del Gasto:", value=date.today(), key="f_nota")

                with col_g2:
                    concepto_nota = st.text_area("Concepto / Justificación:", value="Compra de combustible para generador eléctrico y garrafones de agua")

                btn_nota = st.form_submit_button("📋 Registrar Nota de Gasto", type="primary", use_container_width=True)

                if btn_nota:
                    payload = {
                        "project_id": current_project_id,
                        "worker_id": None,
                        "amount": float(monto_nota),
                        "payment_type": "manual_note",
                        "date_paid": str(fecha_nota),
                        "description": concepto_nota,
                    }
                    res = api_post("/payments/", payload)
                    if res:
                        st.toast("✅ ¡Nota de gasto registrada exitosamente!", icon="🎉")
                        st.success(f"Nota guardada con éxito (Folio: `{res.get('id')}`).")


# =========================================================================
# VISTA 4: Generador de Memorias Interactivas (Memory Dashboard)
# =========================================================================
elif selected_view == "📊 Generador de Memorias":
    st.markdown('<div class="main-title">📊 Generador de Memoria de Obra (Bi-Semanal)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Filtre por periodo, seleccione o deseleccione gastos, incluya pagos de otras obras con el buscador, previsualice y compile el PDF oficial con el formato del arquitecto.</div>', unsafe_allow_html=True)

    if not current_project_id:
        st.warning("⚠️ Por favor seleccione una Obra Activa en la barra lateral.")
    else:
        # Parámetros del Reporte
        with st.container():
            col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 1, 2])
            with col_f1:
                fecha_defecto_inicio = date.today() - timedelta(days=14)
                fecha_inicio = st.date_input("Fecha de Inicio:", value=fecha_defecto_inicio, key="mem_f_ini")

            with col_f2:
                fecha_fin = st.date_input("Fecha de Fin:", value=date.today(), key="mem_f_fin")

            with col_f3:
                num_memoria = st.text_input("No. Memoria:", value="01", key="mem_num")

            with col_f4:
                ubicacion_obra = st.text_input("Ubicación de la Obra:", value="Zapopan, Jalisco", key="mem_loc")

        col_btn_load, _ = st.columns([2, 3])
        with col_btn_load:
            btn_cargar_periodo = st.button("🔍 Cargar Gastos del Periodo", type="primary", use_container_width=True)

        # Si el usuario hace clic en cargar periodo, consultamos la API
        if btn_cargar_periodo:
            with st.spinner("Consultando comprobantes fiscales y dispersiones del periodo..."):
                mem_raw = api_get(
                    f"/projects/{current_project_id}/memory",
                    params={
                        "start_date": str(fecha_inicio),
                        "end_date": str(fecha_fin),
                        "memoria_number": num_memoria,
                        "location": ubicacion_obra,
                    },
                )

            if mem_raw:
                # 1. Facturas
                draft_inv = []
                for inv in mem_raw.get("invoices", []):
                    sup = inv.get("supplier") or {}
                    draft_inv.append({
                        "incluir": True,
                        "id": inv.get("id"),
                        "comprobante": str(inv.get("invoice_number") or ""),
                        "proveedor": str(sup.get("name") or "PROVEEDOR GENERAL"),
                        "concepto": str(inv.get("concept") or ""),
                        "fecha": inv.get("date_issued"),
                        "importe": float(inv.get("amount", 0.0)),
                        "pdf_s3_url": inv.get("pdf_s3_url", ""),
                        "obra_origen": st.session_state["selected_project_name"].split(" — ")[0],
                        "es_externo": False,
                    })

                # 2. Pagos
                draft_pay = []
                for p in mem_raw.get("payments", []):
                    worker = p.get("worker") or {}
                    draft_pay.append({
                        "incluir": True,
                        "id": p.get("id"),
                        "payment_type": p.get("payment_type"),
                        "beneficiario": worker.get("full_name") or "N/A",
                        "concepto": str(p.get("description") or "PAGO"),
                        "fecha": p.get("date_paid"),
                        "importe": float(p.get("amount", 0.0)),
                        "obra_origen": st.session_state["selected_project_name"].split(" — ")[0],
                        "es_externo": False,
                    })

                st.session_state["memory_draft_invoices"] = draft_inv
                st.session_state["memory_draft_payments"] = draft_pay
                st.session_state["memory_loaded_params"] = {
                    "start_date": str(fecha_inicio),
                    "end_date": str(fecha_fin),
                    "memoria_number": num_memoria,
                    "location": ubicacion_obra,
                }
                st.toast(f"✅ Cargados: {len(draft_inv)} facturas y {len(draft_pay)} pagos.", icon="📋")

        # --- SECCIÓN INTERACTIVA DE EDICIÓN Y FILTRADO ---
        if st.session_state.get("memory_draft_invoices") is not None or st.session_state.get("memory_draft_payments") is not None:
            raw_draft_inv = st.session_state.get("memory_draft_invoices", [])
            raw_draft_pay = st.session_state.get("memory_draft_payments", [])

            st.markdown("---")

            # BUSCADOR DE PAGOS DE OTRAS OBRAS
            with st.expander("🔍 **Buscar y Agregar Pagos de Otras Obras a esta Memoria**"):
                st.info("💡 Si realizó un gasto con fondos de otra obra o desea transferir un desembolso a esta memoria, búsquelo aquí para incorporarlo.")
                col_bus1, col_bus2 = st.columns([3, 1])
                with col_bus1:
                    busq_query = st.text_input("Buscar por concepto, trabajador u obra de origen:", placeholder="Ej. renta, cemento, Carlos Méndez, Obra Norte...")
                with col_bus2:
                    st.write("")
                    st.write("")
                    btn_buscar_ext = st.button("Buscar Pagos Externos")

                if btn_buscar_ext and busq_query.strip():
                    ext_results = api_get(
                        "/payments/search",
                        params={
                            "q": busq_query.strip(),
                            "exclude_project_id": current_project_id,
                            "limit": 20,
                        },
                    )
                    st.session_state["search_ext_results"] = ext_results or []

                found_ext = st.session_state.get("search_ext_results", [])
                if found_ext:
                    ext_options = {}
                    for p_ext in found_ext:
                        p_proj_nom = p_ext.get("project", {}).get("name") if p_ext.get("project") else "Otra Obra"
                        w_nom = p_ext.get("worker", {}).get("full_name") if p_ext.get("worker") else ""
                        lbl = f"[{p_proj_nom}] ({p_ext['payment_type']}) {p_ext.get('description', '')} {f'- {w_nom}' if w_nom else ''} | ${float(p_ext['amount']):,.2f} ({p_ext['date_paid']})"
                        ext_options[lbl] = p_ext

                    sel_ext_label = st.selectbox("Seleccione el pago a incorporar:", options=list(ext_options.keys()))
                    if st.button("➕ Agregar este Pago a la Memoria Actual"):
                        item_to_add = ext_options[sel_ext_label]
                        p_proj_nom = item_to_add.get("project", {}).get("name") if item_to_add.get("project") else "Otra Obra"
                        w_nom = item_to_add.get("worker", {}).get("full_name") if item_to_add.get("worker") else "N/A"

                        st.session_state["memory_draft_payments"].append({
                            "incluir": True,
                            "id": item_to_add.get("id"),
                            "payment_type": item_to_add.get("payment_type"),
                            "beneficiario": w_nom,
                            "concepto": str(item_to_add.get("description") or "PAGO EXTERNO"),
                            "fecha": item_to_add.get("date_paid"),
                            "importe": float(item_to_add.get("amount", 0.0)),
                            "obra_origen": f"{p_proj_nom} (Externa)",
                            "es_externo": True,
                        })
                        st.toast("✅ Pago externo agregado a la memoria.", icon="🎉")
                        st.rerun()

            st.markdown("#### ✏️ Selección y Edición de Gastos de la Memoria")
            st.caption("Active o desactive las casillas de verificación para incluir o excluir gastos. Puede editar conceptos e importes en tiempo real antes de descargar.")

            # Tablas interactivas con st.data_editor
            df_invoices = pd.DataFrame(raw_draft_inv) if raw_draft_inv else pd.DataFrame(columns=["incluir", "comprobante", "proveedor", "concepto", "fecha", "importe", "obra_origen"])
            if not df_invoices.empty and "fecha" in df_invoices.columns:
                df_invoices["fecha"] = pd.to_datetime(df_invoices["fecha"], errors="coerce").fillna(pd.to_datetime(date.today())).dt.date

            # Separar pagos por categoría para las pestañas
            df_payments_all = pd.DataFrame(raw_draft_pay) if raw_draft_pay else pd.DataFrame(columns=["incluir", "payment_type", "beneficiario", "concepto", "fecha", "importe", "obra_origen", "es_externo"])
            if not df_payments_all.empty and "fecha" in df_payments_all.columns:
                df_payments_all["fecha"] = pd.to_datetime(df_payments_all["fecha"], errors="coerce").fillna(pd.to_datetime(date.today())).dt.date

            df_transf = df_payments_all[df_payments_all["payment_type"].astype(str).str.lower().isin(["bank_transfer", "bank_transfers"])].copy() if not df_payments_all.empty else pd.DataFrame()
            df_notas = df_payments_all[df_payments_all["payment_type"].astype(str).str.lower().isin(["manual_note", "manual_notes"])].copy() if not df_payments_all.empty else pd.DataFrame()
            df_rayas = df_payments_all[df_payments_all["payment_type"].astype(str).str.lower().isin(["payroll", "payrolls"])].copy() if not df_payments_all.empty else pd.DataFrame()

            tab_inv, tab_tr, tab_nt, tab_ry = st.tabs([
                f"📦 Facturas de Proveedores ({len(df_invoices)})",
                f"🏦 Transferencias Bancarias ({len(df_transf)})",
                f"📋 Notas y Efectivo ({len(df_notas)})",
                f"👷 Nómina / Rayas ({len(df_rayas)})",
            ])

            # Editor 1: Facturas
            with tab_inv:
                if not df_invoices.empty:
                    edited_inv = st.data_editor(
                        df_invoices,
                        key="editor_mem_invoices",
                        use_container_width=True,
                        column_config={
                            "incluir": st.column_config.CheckboxColumn("Incluir", help="Marque para incluir en la memoria", default=True),
                            "comprobante": st.column_config.TextColumn("Folio Fiscal / UUID", required=True),
                            "proveedor": st.column_config.TextColumn("Proveedor", disabled=False, help="Puede editar el nombre del proveedor si lo desea"),
                            "concepto": st.column_config.TextColumn("Concepto Resumido", required=True),
                            "fecha": st.column_config.DateColumn("Fecha", required=True),
                            "importe": st.column_config.NumberColumn("Importe Total ($)", format="$%.2f", min_value=0.0, required=True),
                            "obra_origen": st.column_config.TextColumn("Obra Origen", disabled=True),
                            "id": None,
                            "pdf_s3_url": None,
                            "es_externo": None,
                        },
                        hide_index=True,
                    )
                else:
                    st.info("Sin facturas registradas en este periodo.")
                    edited_inv = pd.DataFrame()

            # Editor 2: Transferencias
            with tab_tr:
                if not df_transf.empty:
                    edited_transf = st.data_editor(
                        df_transf,
                        key="editor_mem_transf",
                        use_container_width=True,
                        column_config={
                            "incluir": st.column_config.CheckboxColumn("Incluir", default=True),
                            "concepto": st.column_config.TextColumn("Referencia / Concepto", required=True),
                            "fecha": st.column_config.DateColumn("Fecha", required=True),
                            "importe": st.column_config.NumberColumn("Importe ($)", format="$%.2f", min_value=0.0, required=True),
                            "obra_origen": st.column_config.TextColumn("Obra Origen", disabled=True),
                            "es_externo": st.column_config.CheckboxColumn("Gasto Externo", disabled=True),
                            "id": None,
                            "payment_type": None,
                            "beneficiario": None,
                        },
                        hide_index=True,
                    )
                else:
                    st.info("Sin transferencias en este periodo.")
                    edited_transf = pd.DataFrame()

            # Editor 3: Notas de efectivo
            with tab_nt:
                if not df_notas.empty:
                    edited_notas = st.data_editor(
                        df_notas,
                        key="editor_mem_notas",
                        use_container_width=True,
                        column_config={
                            "incluir": st.column_config.CheckboxColumn("Incluir", default=True),
                            "concepto": st.column_config.TextColumn("Concepto / Justificación", required=True),
                            "fecha": st.column_config.DateColumn("Fecha", required=True),
                            "importe": st.column_config.NumberColumn("Importe ($)", format="$%.2f", min_value=0.0, required=True),
                            "obra_origen": st.column_config.TextColumn("Obra Origen", disabled=True),
                            "es_externo": st.column_config.CheckboxColumn("Gasto Externo", disabled=True),
                            "id": None,
                            "payment_type": None,
                            "beneficiario": None,
                        },
                        hide_index=True,
                    )
                else:
                    st.info("Sin notas de efectivo en este periodo.")
                    edited_notas = pd.DataFrame()

            # Editor 4: Nómina / Rayas
            with tab_ry:
                if not df_rayas.empty:
                    edited_rayas = st.data_editor(
                        df_rayas,
                        key="editor_mem_rayas",
                        use_container_width=True,
                        column_config={
                            "incluir": st.column_config.CheckboxColumn("Incluir", default=True),
                            "beneficiario": st.column_config.TextColumn("Trabajador / Beneficiario", disabled=True),
                            "concepto": st.column_config.TextColumn("Detalle / Observaciones", required=True),
                            "fecha": st.column_config.DateColumn("Fecha", required=True),
                            "importe": st.column_config.NumberColumn("Importe ($)", format="$%.2f", min_value=0.0, required=True),
                            "obra_origen": st.column_config.TextColumn("Obra Origen", disabled=True),
                            "es_externo": st.column_config.CheckboxColumn("Gasto Externo", disabled=True),
                            "id": None,
                            "payment_type": None,
                        },
                        hide_index=True,
                    )
                else:
                    st.info("Sin pagos de nómina en este periodo.")
                    edited_rayas = pd.DataFrame()

            # ==========================================
            # RECÁLCULO FINANCIERO DINÁMICO EN VIVO
            # ==========================================
            # Filtramos solo los elementos con incluir == True
            inv_sel = edited_inv[edited_inv["incluir"] == True] if not edited_inv.empty and "incluir" in edited_inv.columns else pd.DataFrame()
            transf_sel = edited_transf[edited_transf["incluir"] == True] if not edited_transf.empty and "incluir" in edited_transf.columns else pd.DataFrame()
            notas_sel = edited_notas[edited_notas["incluir"] == True] if not edited_notas.empty and "incluir" in edited_notas.columns else pd.DataFrame()
            rayas_sel = edited_rayas[edited_rayas["incluir"] == True] if not edited_rayas.empty and "incluir" in edited_rayas.columns else pd.DataFrame()

            # Fórmulas contables exactas del arquitecto
            calc_subtotal_transf = float(transf_sel["importe"].sum()) if not transf_sel.empty else 0.0
            calc_subtotal_efectivo = (float(inv_sel["importe"].sum()) if not inv_sel.empty else 0.0) + (float(notas_sel["importe"].sum()) if not notas_sel.empty else 0.0)
            calc_subtotal_rayas = float(rayas_sel["importe"].sum()) if not rayas_sel.empty else 0.0

            calc_honorarios = round((calc_subtotal_transf + calc_subtotal_efectivo + calc_subtotal_rayas) * 0.10, 2)
            calc_subtotal_fac_arq = calc_subtotal_rayas + calc_honorarios
            calc_iva = round(calc_subtotal_fac_arq * 0.16, 2)
            calc_importe_fac_arq = calc_subtotal_fac_arq + calc_iva
            calc_saldo_a_favor = calc_importe_fac_arq + calc_subtotal_efectivo
            calc_gran_total_obra = calc_subtotal_transf + calc_saldo_a_favor

            st.markdown("---")
            st.subheader(f"📑 Resumen Financiero Dinámico (Gastos Seleccionados)")

            # Tarjetas de subtotales
            st.markdown("##### 💵 Subtotales por Categoría de Gasto")
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("🟧 Transferencias Bancarias", f"${calc_subtotal_transf:,.2f}")
            with m2:
                st.metric("🟦 Notas y Facturas en Efectivo", f"${calc_subtotal_efectivo:,.2f}")
            with m3:
                st.metric("🟨 Nómina (Rayas)", f"${calc_subtotal_rayas:,.2f}")

            # Tarjetas de honorarios y liquidación
            st.markdown("##### 📐 Liquidación de Honorarios y Facturación")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Honorarios 10%", f"${calc_honorarios:,.2f}")
            with c2:
                st.metric("IVA 16%", f"${calc_iva:,.2f}")
            with c3:
                st.metric("Total Factura Arq. (F-XXX)", f"${calc_importe_fac_arq:,.2f}")
            with c4:
                st.metric("Cobrado / Saldo a mi Favor", f"${calc_saldo_a_favor:,.2f}")

            st.markdown(
                f"""
                <div style="background-color: #F8FAFC; border: 2px solid #E2E8F0; border-radius: 8px; padding: 14px; margin: 12px 0;">
                    <h3 style="margin: 0; color: #0F172A;"><b>Importe de esta Memoria (Gran Total):</b> <span style="color: #C00000;">${calc_gran_total_obra:,.2f}</span></h3>
                    <p style="margin: 4px 0 0 0; color: #475569; font-size: 13px;"><b>Subtotal Directo de Obra:</b> ${(calc_subtotal_transf + calc_subtotal_efectivo + calc_subtotal_rayas):,.2f} | <b>Periodo:</b> {fecha_inicio} al {fecha_fin}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ==========================================
            # DESCARGA DEL PDF OFICIAL PERSONALIZADO
            # ==========================================
            st.markdown("---")
            col_pdf_act, col_json_act = st.columns([1, 1])

            # Construimos el payload con los ítems confirmados
            payload_custom = {
                "memoria_number": num_memoria,
                "location": ubicacion_obra,
                "start_date": str(fecha_inicio),
                "end_date": str(fecha_fin),
                "invoices": [
                    {
                        "id": str(r.get("id")) if r.get("id") else None,
                        "invoice_number": str(r.get("comprobante")),
                        "concept": str(r.get("concepto")),
                        "amount": float(r.get("importe")),
                        "date_issued": str(r.get("fecha")),
                        "supplier_name": str(r.get("proveedor")),
                        "pdf_s3_url": str(r.get("pdf_s3_url") or ""),
                    }
                    for _, r in inv_sel.iterrows()
                ] if not inv_sel.empty else [],
                "payments": [
                    {
                        "id": str(r.get("id")) if r.get("id") else None,
                        "payment_type": str(r.get("payment_type")),
                        "description": str(r.get("concepto")),
                        "amount": float(r.get("importe")),
                        "date_paid": str(r.get("fecha")),
                        "worker_name": str(r.get("beneficiario")) if r.get("beneficiario") != "N/A" else None,
                        "project_name": str(r.get("obra_origen")),
                        "is_external": bool(r.get("es_externo", False)),
                    }
                    for _, r in pd.concat([transf_sel, notas_sel, rayas_sel]).iterrows()
                ] if not (transf_sel.empty and notas_sel.empty and rayas_sel.empty) else [],
            }

            with col_pdf_act:
                if st.button("📄 Generar y Descargar Memoria PDF Oficial (con selección actual)", type="primary", use_container_width=True):
                    with st.spinner("Compilando documento PDF oficial con el formato del arquitecto..."):
                        pdf_bytes = api_post_binary(
                            f"/projects/{current_project_id}/memory/download-custom",
                            payload_custom,
                        )

                    if pdf_bytes:
                        st.download_button(
                            label="⬇️ Haga clic aquí para guardar el archivo PDF compilado",
                            data=pdf_bytes,
                            file_name=f"Memoria_{num_memoria}_{st.session_state['selected_project_name'].split(' — ')[0].replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True,
                        )
                    else:
                        st.error("No se pudo compilar el PDF. Verifique que los campos obligatorios contengan datos válidos.")

            with col_json_act:
                st.download_button(
                    label="💾 Descargar Respaldo de Selección (JSON)",
                    data=json.dumps(payload_custom, indent=2, ensure_ascii=False),
                    file_name=f"Memoria_{num_memoria}_Respaldo.json",
                    mime="application/json",
                    type="secondary",
                    use_container_width=True,
                )

# Sistema de Memorias de Gastos de Obra (Backend REST)

Backend 100% local para arquitectos y administradores de obra. Gestiona obras, facturas CFDI (XML + PDF), rayas (nóminas de trabajadores), pagos manuales y memorias de gastos quincenales con congelamiento de snapshots y cálculo exacto de honorarios en `Decimal`.

---

## 🛠️ Stack Tecnológico

- **Lenguaje**: Python 3.11+ / 3.12
- **Base de Datos**: SQLite local (archivo único en `./data/app.db` con WAL y foreign keys activadas)
- **ORM & Migraciones**: SQLAlchemy 2.0 (síncrono) + Alembic
- **API Framework**: FastAPI & Pydantic V2
- **Almacenamiento de Comprobantes**: Local en `./data/storage/{obra_id}/{UUID}.[xml|pdf]`
- **Parser CFDI**: Parseo directo de XML SAT 3.3/4.0 (extracción de Total, Serie, Folio, RFC, Forma de Pago)
- **Pruebas**: Pytest (38 pruebas unitarias e integrales)

---

## 🚀 Inicio Rápido (Un solo comando)

### 1. Activar entorno virtual
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Ejecutar el servidor
Con un solo comando se crean las carpetas requeridas, se aplican las migraciones de Alembic y se inicia el servidor:
```bash
python run.py
```

- **Documentación Swagger interactiva**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 3. Ejecutar Pruebas
```bash
pytest -v
```

---

## 📂 Estructura del Proyecto

```text
├── app/
│   ├── config.py              # Variables de entorno y rutas locales (./data)
│   ├── database.py            # Motor SQLite y sesión SQLAlchemy
│   ├── models.py              # 8 modelos de datos (Obra, Proveedor, Gasto, Factura, etc.)
│   ├── schemas.py             # Esquemas Pydantic V2 para validación y serialización
│   ├── types.py               # Tipos DecimalText y redondeo monetario exacto
│   ├── main.py                # Aplicación FastAPI, CORS y lifespan con Alembic
│   ├── routers/               # Endpoints REST modulares
│   │   ├── obras.py           # CRUD de obras y memorias asociadas
│   │   ├── proveedores.py     # CRUD de proveedores y alias comercial
│   │   ├── trabajadores.py    # CRUD de trabajadores y pagos acumulados
│   │   ├── anticipos.py       # CRUD de anticipos
│   │   ├── rayas.py           # Pagos de nómina/raya
│   │   ├── gastos.py          # Gastos manuales, notas y búsqueda cruzada
│   │   ├── facturas.py        # Subida CFDI XML/PDF, staging, revisión y confirmación
│   │   └── memorias.py        # Preview, borrador, cierre congelado y stubs de exportación
│   └── services/              # Lógica pura de negocio y utilidades
│       ├── memoria_calculo.py # Módulo puro de cálculo financiero (Decimal)
│       ├── memoria_service.py # Servicio de persistencia y congelamiento de snapshots
│       ├── xml_parser.py      # Parser robusto de XML CFDI SAT
│       ├── storage.py         # Manejo de archivos locales y staging temporal
│       └── number_to_words.py # Conversión de importes a letras (pesos mexicanos)
├── migrations/                # Migraciones versionadas de Alembic
├── tests/                     # Suite de pruebas unitarias y de integración
├── legacy/                    # Respaldos del código anterior y frontend Streamlit
├── data/                      # Base de datos y archivos locales (ignorado en git)
├── run.py                     # Script de arranque en un solo comando
├── requirements.txt           # Dependencias Python
└── pyproject.toml             # Configuración del paquete y herramientas
```

---

## 🔒 Reglas Financieras y de Integridad

1. **Decimal estricto**: Todo el dinero se almacena y calcula con `Decimal` a 2 decimales (`ROUND_HALF_UP`), sin conversiones intermedias por `float`.
2. **Snapshot congelado**: Al cerrar una memoria (`POST /memorias/{id}/cerrar`), los renglones y totales quedan congelados en `snapshot_json`. Modificaciones posteriores a los gastos vivos no alteran la memoria cerrada.
3. **Facturas**: Los importes de gastos provenientes de XML quedan protegidos contra edición manual para asegurar coincidencia con el SAT. Facturas duplicadas por UUID son rechazadas con error HTTP 409 indicando en qué obra y fecha fueron registradas.

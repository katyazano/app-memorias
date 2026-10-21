# ETAPA G: Empaquetado para Windows (.exe) - Memorias de Gastos

Este documento detalla la arquitectura de empaquetado, el ciclo de vida de la aplicación, el procedimiento de compilación automática y la guía paso a paso para verificar el instalador en una máquina limpia (Windows Sandbox) sin dependencias previas de Python ni Node.js.

---

## 1. Arquitectura del Empaquetado

La aplicación fue diseñada para ejecutarse como una aplicación de escritorio nativa para Windows, cumpliendo con la separación estricta entre **archivos de solo lectura** (código, plantillas, frontend compilado) y **archivos de datos escribibles del usuario** (base de datos, almacenamiento de comprobantes, respaldos y registros).

### 1.1 Rutas y Aislamiento de Datos

La aplicación detecta automáticamente si corre en modo empaquetado (`sys.frozen == True`) o en modo desarrollo:

| Componente | Modo Empaquetado (`sys.frozen`) | Modo Desarrollo (`python launcher.py`) |
| :--- | :--- | :--- |
| **Recursos de Solo Lectura** | `sys._MEIPASS` (directorio temporal de PyInstaller o carpeta de instalación `_internal`) | Raíz del repositorio (`repo/`) |
| **Frontend Compilado** | `sys._MEIPASS / "frontend" / "dist"` | `repo / "frontend" / "dist"` |
| **Plantillas y Migraciones** | `sys._MEIPASS / "templates"`, `alembic.ini`, `migrations` | `repo / "templates"`, `alembic.ini`, `migrations` |
| **Base de Datos SQLite** | `%LOCALAPPDATA%\MemoriasGastos\data\app.db` | `repo / "data" / "app.db"` |
| **Archivos XML / PDF** | `%LOCALAPPDATA%\MemoriasGastos\storage\` | `repo / "data" / "storage"` |
| **Respaldos Automáticos** | `%LOCALAPPDATA%\MemoriasGastos\respaldos\` (configurable) | `repo / "data" / "respaldos"` |
| **Registros de Ejecución** | `%LOCALAPPDATA%\MemoriasGastos\logs\app.log` | `repo / "logs" / "app.log"` |

**Resolución de Rutas Relativas en Base de Datos**:
En la base de datos se guarda siempre la ruta canónica `storage/{obra_id}/{uuid}.{ext}`. El módulo [`storage.py`](app/services/storage.py) resuelve las rutas de forma independiente de si `storage` es un subdirectorio de `data` (modo desarrollo) o un directorio hermano en `%LOCALAPPDATA%\MemoriasGastos\` (modo congelado). Esto resolvió la causa raíz del error 500/400 al confirmar facturas, donde `pathlib.relative_to` intentaba resolver respecto a `data` en lugar de `storage`.

**Garantía fundamental**: Nada se escribe en la carpeta del programa (`%LOCALAPPDATA%\Programs\MemoriasGastos`). Al desinstalar o actualizar, los datos del usuario **nunca** se eliminan ni se sobrescriben.

---

### 1.2 Mecanismo de Instancia Única (Single-Instance Mutex)

Para evitar que el usuario abra múltiples servidores que choquen en el puerto 8000 o corrompan la base de datos:
1. El archivo [`launcher.py`](launcher.py) crea un mutex de sesión de Windows con el nombre:
   `Local\MemoriasGastos_SingleInstance_Mutex_v2`.
2. Si otra instancia de la aplicación ya se encuentra en ejecución:
   - Lee el archivo `%LOCALAPPDATA%\MemoriasGastos\data\app.url` que contiene la URL exacta (por ejemplo, `http://127.0.0.1:8000`).
   - Abre una nueva pestaña en el navegador predeterminado del sistema apuntando a esa URL.
   - La nueva instancia termina limpiamente de inmediato sin lanzar alertas de error ni procesos huérfanos.
3. Si el puerto 8000 estuviera ocupado por otro servicio ajeno, el launcher busca automáticamente el primer puerto libre (8001–8099) y registra la URL para que el frontend y el navegador se conecten con éxito.

---

### 1.3 Ciclo de Vida y Apagado Automático (Heartbeat & Salir)

1. **Botón "Salir" en la Barra Superior:**
   - La interfaz cuenta con un botón **Salir** que solicita confirmación al usuario.
   - Al confirmar, llama al endpoint `POST /api/sistema/apagar`.
   - El servidor cierra Uvicorn ordenadamente, libera los bloqueos de SQLite y finaliza el proceso de Windows en menos de 2 segundos.
2. **Monitor de Inactividad (Heartbeat):**
   - El frontend envía una señal `POST /api/sistema/heartbeat` cada 30 segundos mientras haya al menos una pestaña abierta.
   - Si el usuario cierra el navegador sin hacer clic en "Salir", el servicio [`lifecycle_service.py`](app/services/lifecycle_service.py) detecta que transcurrieron 5 minutos sin actividad de pestañas y apaga el proceso en segundo plano para no consumir memoria ni batería.

---

### 1.4 Generación de PDF con Edge / Chrome CLI del Sistema

Para eliminar la dependencia pesada de navegadores empaquetados (como Playwright o Chromium descargado que sumarían más de 150 MB):
1. **Detección Exhaustiva y Resiliente en Windows**:
   El servicio [`pdf_service.py`](app/services/pdf_service.py) busca el ejecutable del navegador en tres niveles:
   - **Registro de Windows (`winreg`)**: Consulta las claves `App Paths\msedge.exe` y `App Paths\chrome.exe` en `HKEY_LOCAL_MACHINE` y `HKEY_CURRENT_USER`, tanto en vistas de 64 bits (`KEY_WOW64_64KEY`) como de 32 bits (`KEY_WOW64_32KEY`).
   - **Rutas estándar y variables de entorno**: Inspecciona `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` (ruta estándar en Windows Sandbox), `Program Files`, `LOCALAPPDATA` y variantes de Chrome.
   - **PATH del sistema**: Vía `shutil.which`.
   
   > [!IMPORTANT]
   > **Resolución de la causa raíz en Windows Sandbox:** En entornos con cuentas de servicio o restringidas como `WDAGUtilityAccount` en Windows Sandbox, la función de Python `os.access(path, os.X_OK)` devuelve `False` debido a que la cuenta carece de permisos de lectura sobre las listas de control de acceso (ACLs) de archivos administrados por `TrustedInstaller`. La detección se corrigió verificando estrictamente `path.is_file()`, lo cual permite detectar `msedge.exe` sin falsos negativos.

2. **Aislamiento Total del Proceso Headless (`--user-data-dir` temporal)**:
   Si el usuario ya tiene Microsoft Edge abierto (o la aplicación lo abrió en el arranque para mostrar la interfaz), invocar `msedge.exe` con el perfil por defecto causa que el navegador delegue la URL a la ventana existente y termine de inmediato con código 0 sin generar el PDF.
   Para garantizar una ejecución 100% aislada:
   - Se genera una carpeta temporal única por llamada (`tempfile.mkdtemp(prefix="memorias_pdf_")`) que se pasa como `--user-data-dir`.
   - Se incluyen las banderas `--headless=new`, `--disable-gpu`, `--no-first-run`, `--no-default-browser-check`, `--disable-background-networking`, `--disable-sync`, `--disable-translate`, `--disable-extensions`, `--disable-default-apps`, `--run-all-compositor-stages-before-draw`, `--no-pdf-header-footer` y `--virtual-time-budget=7000`.
   - Al terminar la llamada, el directorio temporal de perfil se elimina automáticamente (`shutil.rmtree(..., ignore_errors=True)`).

3. **Separación Estricta de Errores Técnicos**:
   Se diferencian dos excepciones con diagnóstico técnico completo:
   - `NavegadorNoEncontradoError`: Informa la lista completa de rutas y claves de registro verificadas si no existe Edge ni Chrome.
   - `GeneracionPdfError`: Si el navegador existe pero la generación falló (código de salida != 0, PDF vacío o timeout de 35s), registra y reporta el comando exacto, código de retorno y `stderr`. Nunca se enmascara un fallo de renderizado como "navegador no encontrado".

4. **Respaldo Asistido en la Interfaz de Usuario (UI Fallback)**:
   Si la generación desatendida del servidor llegara a fallar, la interfaz muestra el modal [`FallbackPdfModal.tsx`](frontend/src/components/FallbackPdfModal.tsx) explicando el motivo y ofreciendo con un solo clic abrir `/memorias/{id}/imprimir` en una nueva pestaña junto con las instrucciones para presionar **Ctrl + P** $\rightarrow$ **Guardar como PDF** (tamaño Carta). En la propia pantalla de impresión, un banner interactivo permite invocar la impresión del navegador directamente.

---

### 1.5 Migraciones Automáticas y Respaldo Pre-Migración

Al arrancar:
1. Se verifica la existencia y esquema de `app.db`.
2. Si la base de datos ya existe, se genera un respaldo preventivo de seguridad:
   `%LOCALAPPDATA%\MemoriasGastos\respaldos\pre_migracion_<timestamp>.zip`.
3. Se ejecutan las migraciones de Alembic programáticamente usando las rutas empaquetadas en `sys._MEIPASS`.

---

## 2. Archivos Creados y Modificados en la Etapa G

- [`launcher.py`](launcher.py): Entry point principal con mutex de Windows, selección de puerto libre, arranque de Uvicorn y apertura del navegador web.
- [`memorias.spec`](memorias.spec): Archivo de especificación de PyInstaller que genera `MemoriasGastos.exe` (modo ventana oculta) y `MemoriasGastos-Debug.exe` (consola de diagnóstico), excluyendo módulos pesados no utilizados.
- [`installer.iss`](installer.iss): Script de Inno Setup 6 que compila el instalador en modo usuario (`PrivilegesRequired=lowest`), crea accesos directos y preserva los datos del usuario.
- [`build.ps1`](build.ps1): Pipeline automatizado de 5 pasos (pytest -> build Vite -> PyInstaller -> Prueba de humo con binario real -> Inno Setup).
- [`tests/smoke_test_empaquetado.py`](tests/smoke_test_empaquetado.py): Prueba de humo posterior al empaquetado que arranca el binario empaquetado con `%LOCALAPPDATA%` temporal y ejecuta el ciclo contable completo (obra, subida XML+PDF, confirmación, 409 duplicados, gasto manual, raya, anticipo, memoria, cierre, descarga PDF/Excel y verificación de integridad del respaldo zip).
- [`tests/fixtures/`](tests/fixtures/): Facturas de ejemplo externas al instalador (`factura_muestra.xml` y `factura_muestra.pdf`) usadas por la prueba de humo.
- [`app/config.py`](app/config.py): Gestión unificada de rutas `sys.frozen` y modo desarrollo.
- [`app/main.py`](app/main.py): Hook de migración con respaldo preventivo, middleware SPA y manejador global de excepciones con logging detallado.
- [`app/services/storage.py`](app/services/storage.py): Almacenamiento desacoplado con rutas canónicas `storage/{obra_id}/{uuid}.{ext}` y soporte para `STORAGE_DIR` independiente de `DATA_DIR`.
- [`app/services/lifecycle_service.py`](app/services/lifecycle_service.py): Gestor de apagado y watchdog de heartbeat de 5 minutos.
- [`app/routers/sistema.py`](app/routers/sistema.py): Endpoints `/api/sistema/heartbeat`, `/api/sistema/apagar` y `/api/sistema/abrir-logs`.
- [`app/services/pdf_service.py`](app/services/pdf_service.py): Generación de PDF llamando a `msedge.exe` / `chrome.exe` en modo headless CLI.
- [`app/services/backup_service.py`](app/services/backup_service.py): Compatibilidad con directorios relativos y absolutos para respaldos en empaquetado.
- [`frontend/src/version.ts`](frontend/src/version.ts): Constante centralizada de versión `2.0.0`.
- [`frontend/src/lib/api.ts`](frontend/src/lib/api.ts): Métodos cliente `enviarHeartbeat`, `apagarSistema` y `abrirCarpetaLogs`, con captura de errores amigables y detalles técnicos.
- [`frontend/src/components/layout/AppLayout.tsx`](frontend/src/components/layout/AppLayout.tsx): Temporizador cíclico de heartbeat de 30s.
- [`frontend/src/components/layout/Header.tsx`](frontend/src/components/layout/Header.tsx): Botón "Salir" con modal de confirmación y cierre suave.
- [`frontend/src/pages/CargaFacturasPage.tsx`](frontend/src/pages/CargaFacturasPage.tsx): Mensaje amigable "No se pudo guardar la factura. Los detalles técnicos se guardaron en el registro", con botones "Copiar detalles" y "Abrir carpeta de registros".
- [`tests/test_etapa_g_empaquetado.py`](tests/test_etapa_g_empaquetado.py): Pruebas de detección de navegador, endpoints de sistema, resolución de rutas y apertura de logs.

---

## 3. Comandos para Compilar el Instalador

### Requisitos en la máquina de desarrollo
1. Python 3.12+ con el entorno virtual activado (`.venv`).
2. Node.js 18+ y npm instalados.
3. Inno Setup 6 instalado (detectado automáticamente en `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe` o `Program Files (x86)`).
4. PyInstaller (`pip install pyinstaller`).

### Ejecución del Script Automatizado
Desde la raíz del repositorio, ejecute en PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

El script ejecuta automáticamente los 5 pasos:
1. **Paso 1/5**: Corre las 83 pruebas unitarias y de integración con `pytest` y aborta de inmediato si alguna falla.
2. **Paso 2/5**: Compila la interfaz con `npm run build` en `frontend/dist`.
3. **Paso 3/5**: Empaqueta los ejecutables y dependencias con `pyinstaller memorias.spec`.
4. **Paso 4/5**: Ejecuta la prueba de humo automatizada (`tests/smoke_test_empaquetado.py`) sobre el binario real `MemoriasGastos-Debug.exe` en un entorno `%LOCALAPPDATA%` temporal y puerto dinámico aislado. Si algún endpoint, descarga o verificación de respaldo falla, la compilación se aborta sin generar el instalador.
5. **Paso 5/5**: Compila el instalador final con Inno Setup (`ISCC.exe /DAppVersion=2.0.0 installer.iss`).

---

## 4. Métricas de Tamaño y Ubicación de Salida

| Archivo / Carpeta | Ruta | Tamaño Aprox. |
| :--- | :--- | :--- |
| **Instalador Final (.exe)** | `dist\Instalador-Memorias-2.0.0.exe` | **38.3 MB** |
| **Directorio de la Aplicación Instalada** | `%LOCALAPPDATA%\Programs\MemoriasGastos\` | **120.1 MB** |

*(Nota: Gracias a la exclusión de drivers externos innecesarios y al uso del Edge del sistema operativo, el instalador se redujo de más de 180 MB a menos de 40 MB).*

---

## 5. Guía de Verificación en una Máquina Limpia (Windows Sandbox)

Windows Sandbox ofrece un entorno virtual limpio y aislado de Windows 11 sin Python, Node ni variables de entorno del desarrollador.

### Preparación del Sandbox
1. En Windows, presione `Win + R`, escriba `optionalfeatures.exe` y asegúrese de que **Espacio aislado de Windows** (Windows Sandbox) esté activado.
2. Abra **Espacio aislado de Windows** desde el menú Inicio.
3. En su máquina física, copie el archivo compilado:
   `D:\Users\kathe\Documents\App memorias\repo\dist\Instalador-Memorias-2.0.0.exe`
4. Péguelo en el escritorio del Sandbox (Ctrl+V).

---

### Prueba Paso a Paso

#### Paso 1: Instalación sin permisos de administrador
- Haga doble clic en `Instalador-Memorias-2.0.0.exe`.
- Verifique que el instalador **NO solicita elevación de UAC** (icono de escudo azul y amarillo).
- Verifique que la ruta de instalación predeterminada sea:
  `C:\Users\WDAGUtilityAccount\AppData\Local\Programs\MemoriasGastos`
- Complete el asistente de instalación en español.

#### Paso 2: Accesos directos
- Compruebe que se haya creado el acceso directo **Memorias de Gastos** en el Escritorio.
- Compruebe que figure en el Menú Inicio dentro del grupo **Memorias de Gastos**.

#### Paso 3: Arranque de la aplicación
- Marque la casilla "Ejecutar Memorias de Gastos" al finalizar la instalación (o haga doble clic en el acceso directo del escritorio).
- Compruebe que:
  - No aparece ninguna consola negra ni ventanas con trazas de Python.
  - Se abre automáticamente Microsoft Edge en `http://127.0.0.1:8000`.
  - La interfaz de usuario carga completa con la versión `2.0.0`.
  - En `%LOCALAPPDATA%\MemoriasGastos\data\` se creó automáticamente `app.db` con todas las migraciones aplicadas.

#### Paso 4: Operación completa (Obra, Factura XML+PDF, Memorias)
- **Crear Obra**: En el menú Obras, cree una obra llamada `Obra Sandbox 1` con cliente `Cliente Prueba`.
- **Subir Factura**: Suba un archivo XML y su PDF correspondiente. Verifique que los datos se extraen, se visualizan y se guardan en `%LOCALAPPDATA%\MemoriasGastos\storage\`.
- **Generar Memoria**: Cree la Memoria 01 de esa obra e incluya la factura.
- **Descargar PDF**: Haga clic en el botón de descarga de PDF. Edge en modo headless generará el archivo `MEMORIA 01 - Obra Sandbox 1.pdf`. Ábralo y verifique formato Carta exacto con 12 mm de margen.
- **Descargar Excel**: Haga clic en descargar Excel y compruebe que se descarga el `.xlsx` con fórmulas vivas.

#### Paso 5: Apagado limpio
- Haga clic en el botón **Salir** ubicado en la barra superior derecha.
- Confirme en el modal "Cerrar sistema".
- Verifique que en el Administrador de Tareas (`Ctrl + Shift + Esc`) el proceso `MemoriasGastos.exe` finaliza y desaparece limpiamente.

#### Paso 6: Persistencia al reabrir
- Vuelva a hacer doble clic en el acceso directo del Escritorio **Memorias de Gastos**.
- Verifique que el servidor vuelve a abrir el navegador y la obra `Obra Sandbox 1`, sus facturas y su memoria siguen intactas.

#### Paso 7: Actualización sobre la versión existente
- Vuelva a ejecutar `Instalador-Memorias-2.0.0.exe` simulando una actualización.
- Instale en la misma ruta sin desinstalar previamente.
- Abra la aplicación y verifique que todos los datos y facturas cargados en el paso 4 permanecen intactos.

#### Paso 8: Desinstalación limpia preservando datos
- Cierre la aplicación.
- Vaya a **Configuración de Windows > Aplicaciones > Aplicaciones instaladas** (o Panel de Control).
- Desinstale **Memorias de Gastos**.
- Verifique que los archivos ejecutables en `%LOCALAPPDATA%\Programs\MemoriasGastos` fueron eliminados.
- Verifique que la carpeta de datos **`%LOCALAPPDATA%\MemoriasGastos`** (con la base de datos `app.db`, las facturas en `storage\` y los respaldos en `respaldos\`) **SE CONSERVA INTACTA**, garantizando que el usuario jamás perderá su información contable por un desinstalado accidental o reinstalación.

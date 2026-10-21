# Script de compilación y empaquetado para Windows (Etapa G)
# Orden estricto: pytest -> npm run build -> pyinstaller -> Inno Setup (ISCC.exe)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
if (-not $repoRoot) { $repoRoot = (Get-Location).Path }
Set-Location $repoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "     MEMORIAS DE GASTOS - COMPILACIÓN Y EMPAQUETADO" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ----------------------------------------------------
# 0. Extracción y Estampado de Versión Unificada (<versión>+<AAAAMMDD.HHMM>)
# ----------------------------------------------------
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    Write-Error "No se encontró el entorno virtual en $pythonPath."
    exit 1
}

$stampScript = Join-Path $repoRoot "scripts\stamp_version.py"
if (-not (Test-Path $stampScript)) {
    Write-Error "No se encontró el script de versión en $stampScript."
    exit 1
}

$version = (& $pythonPath $stampScript).Trim()
if (-not $version) {
    Write-Error "No se pudo estampar la versión unificada"
    exit 1
}
Write-Host "[*] Versión unificada estampada: $version" -ForegroundColor Green

# ----------------------------------------------------
# 1. Pruebas Automatizadas (pytest)
# ----------------------------------------------------
Write-Host ""
Write-Host "--- PASO 1/5: Ejecutando pruebas unitarias y de integración ---" -ForegroundColor Yellow
$pytestPath = Join-Path $repoRoot ".venv\Scripts\pytest.exe"
if (-not (Test-Path $pytestPath)) {
    Write-Error "No se encontró pytest en el entorno virtual ($pytestPath)."
    exit 1
}

& $pytestPath -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "Las pruebas automatizadas fallaron con código $LASTEXITCODE. Compilación abortada."
    exit 1
}
Write-Host "[OK] Todas las pruebas pasaron satisfactoriamente." -ForegroundColor Green

# ----------------------------------------------------
# 2. Compilación del Frontend (npm run build)
# ----------------------------------------------------
Write-Host ""
Write-Host "--- PASO 2/5: Compilando interfaz web (frontend/dist) ---" -ForegroundColor Yellow
$frontendDir = Join-Path $repoRoot "frontend"
Push-Location $frontendDir
try {
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "La compilación de Vite falló con código $LASTEXITCODE."
        exit 1
    }
} finally {
    Pop-Location
}

$distIndex = Join-Path $frontendDir "dist\index.html"
if (-not (Test-Path $distIndex)) {
    Write-Error "El archivo $distIndex no fue generado."
    exit 1
}
Write-Host "[OK] Frontend compilado correctamente en $frontendDir\dist." -ForegroundColor Green

# ----------------------------------------------------
# 3. Empaquetado PyInstaller (memorias.spec)
# ----------------------------------------------------
Write-Host ""
Write-Host "--- PASO 3/5: Empaquetando binarios con PyInstaller ---" -ForegroundColor Yellow
$pyinstallerPath = Join-Path $repoRoot ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstallerPath)) {
    Write-Error "No se encontró PyInstaller en el entorno virtual ($pyinstallerPath)."
    exit 1
}

$distMemorias = Join-Path $repoRoot "dist\MemoriasGastos"
if (Test-Path $distMemorias) {
    Remove-Item -Recurse -Force $distMemorias -ErrorAction SilentlyContinue
}

$specFile = Join-Path $repoRoot "memorias.spec"
& $pyinstallerPath $specFile --noconfirm -y
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller falló con código $LASTEXITCODE."
    exit 1
}

$exeProd = Join-Path $repoRoot "dist\MemoriasGastos\MemoriasGastos.exe"
$exeDebug = Join-Path $repoRoot "dist\MemoriasGastos\MemoriasGastos-Debug.exe"
if (-not (Test-Path $exeProd)) {
    Write-Error "El ejecutable principal $exeProd no fue generado."
    exit 1
}
Write-Host "[OK] Binarios generados en dist\MemoriasGastos (MemoriasGastos.exe y MemoriasGastos-Debug.exe)." -ForegroundColor Green

# ----------------------------------------------------
# 4. Prueba de Humo del Binario Empaquetado
# ----------------------------------------------------
Write-Host ""
Write-Host "--- PASO 4/5: Ejecutando prueba de humo sobre binario empaquetado ---" -ForegroundColor Yellow
$smokeTestScript = Join-Path $repoRoot "tests\smoke_test_empaquetado.py"
if (-not (Test-Path $smokeTestScript)) {
    Write-Error "No se encontró el script de prueba de humo en $smokeTestScript."
    exit 1
}

& $pythonPath $smokeTestScript
if ($LASTEXITCODE -ne 0) {
    Write-Error "La prueba de humo sobre el binario empaquetado falló con código $LASTEXITCODE. Compilación del instalador abortada."
    exit 1
}
Write-Host "[OK] Prueba de humo superada exitosamente." -ForegroundColor Green

# ----------------------------------------------------
# 5. Generación del Instalador Inno Setup (.exe)
# ----------------------------------------------------
Write-Host ""
Write-Host "--- PASO 5/5: Compilando instalador para Windows con Inno Setup ---" -ForegroundColor Yellow
$isccCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Get-Command iscc -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
)

$isccPath = $null
foreach ($candidate in $isccCandidates) {
    if ($candidate -and (Test-Path $candidate)) {
        $isccPath = $candidate
        break
    }
}

if (-not $isccPath) {
    Write-Error "No se encontró el compilador de Inno Setup (ISCC.exe). Instálelo ejecutando: winget install JRSoftware.InnoSetup"
    exit 1
}
Write-Host "[*] Usando compilador Inno Setup: $isccPath" -ForegroundColor DarkCyan

$issFile = Join-Path $repoRoot "installer.iss"
& $isccPath "/DAppVersion=$version" $issFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "La compilación del instalador falló con código $LASTEXITCODE."
    exit 1
}

# ----------------------------------------------------
# Resumen de Entrega
# ----------------------------------------------------
$installerFile = Join-Path $repoRoot "dist\Instalador-Memorias-$version.exe"
if (-not (Test-Path $installerFile)) {
    Write-Error "El archivo del instalador $installerFile no se encontró tras la compilación."
    exit 1
}

$installerSizeMB = [math]::Round(((Get-Item $installerFile).Length / 1MB), 2)
$dirSizeMB = [math]::Round(((Get-ChildItem -Path (Join-Path $repoRoot "dist\MemoriasGastos") -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB), 2)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "          ¡COMPILACIÓN Y EMPAQUETADO EXITOSOS!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Versión:            $version"
Write-Host "Instalador final:   $installerFile"
Write-Host "Tamaño instalador:  $installerSizeMB MB"
Write-Host "Tamaño instalado:   $dirSizeMB MB"
Write-Host "Modo de instalación: Por usuario (sin privilegios de administrador)"
Write-Host "Ruta destino:       %LOCALAPPDATA%\Programs\MemoriasGastos"
Write-Host "Datos de usuario:   %LOCALAPPDATA%\MemoriasGastos (conservados siempre)"
Write-Host "============================================================" -ForegroundColor Green

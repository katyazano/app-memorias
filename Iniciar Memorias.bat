@echo off
chcp 65001 >nul
title Memorias de Gastos - Lanzador
cd /d "%~dp0"

echo ============================================================
echo           MEMORIAS DE GASTOS - GESTION LOCAL
echo ============================================================
echo.

REM 1. Verificar si el puerto 8000 ya esta activo
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 goto YA_ACTIVO

REM 2. Verificar existencia de Python en el entorno virtual
if not exist ".venv\Scripts\python.exe" (
    echo [X] ERROR: No se encontro el entorno virtual en '.venv'.
    echo     Asegurese de instalar los requisitos antes de iniciar.
    echo.
    echo Presione cualquier tecla para salir...
    pause >nul
    exit /b 1
)

REM 3. Arrancar servidor en segundo plano
echo [*] Iniciando el servidor local de Memorias de Gastos...
start "Memorias de Gastos - Servidor Backend" /min ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

REM 4. Esperar a que el backend este listo
echo [*] Esperando respuesta del servidor en http://localhost:8000...
set INTENTOS=0

:WAIT_LOOP
ping -n 2 127.0.0.1 >nul
set /a INTENTOS+=1

curl.exe -f -s http://127.0.0.1:8000/health >nul 2>&1
if not errorlevel 1 goto READY

if %INTENTOS% geq 15 (
    echo [!] El servidor tardo en responder, pero intentaremos abrir el navegador...
    goto READY
)

goto WAIT_LOOP

:READY
echo [OK] Servidor listo y funcionando.
echo [*] Abriendo la aplicacion en su navegador web...
start "" "http://localhost:8000"
ping -n 2 127.0.0.1 >nul
exit /b 0

:YA_ACTIVO
echo [i] El sistema ya esta en ejecucion en el puerto 8000.
echo [i] Abriendo la aplicacion en su navegador web...
start "" "http://localhost:8000"
ping -n 2 127.0.0.1 >nul
exit /b 0

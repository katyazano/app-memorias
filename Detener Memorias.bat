@echo off
chcp 65001 >nul
title Memorias de Gastos - Detener
cd /d "%~dp0"

echo ============================================================
echo           MEMORIAS DE GASTOS - DETENER SERVICIO
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host '[OK] El servidor en el puerto 8000 (PID ' $conn.OwningProcess ') fue detenido exitosamente.' -ForegroundColor Green; } else { Write-Host '[i] No se encontro ningun servidor de Memorias de Gastos ejecutandose en el puerto 8000.' -ForegroundColor Yellow; }"

echo.
echo Presione cualquier tecla para cerrar esta ventana...
pause >nul
exit /b 0

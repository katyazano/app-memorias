@echo off
chcp 65001 >nul
title Memorias de Gastos - Crear Acceso Directo
cd /d "%~dp0"

echo ============================================================
echo   CREAR ACCESO DIRECTO EN EL ESCRITORIO
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = [Environment]::GetFolderPath('Desktop'); $target = Join-Path (Get-Location) 'Iniciar Memorias.bat'; $lnkPath = Join-Path $desk 'Memorias de Gastos.lnk'; $sc = $ws.CreateShortcut($lnkPath); $sc.TargetPath = $target; $sc.WorkingDirectory = (Get-Location).Path; $sc.Description = 'Sistema de Memorias de Gastos para Arquitectos'; $sc.IconLocation = 'shell32.dll,43'; $sc.Save(); Write-Host '[OK] Acceso directo creado exitosamente en su Escritorio:' -ForegroundColor Green; Write-Host '     ' $lnkPath -ForegroundColor Cyan;"

echo.
echo Presione cualquier tecla para salir...
pause >nul
exit /b 0

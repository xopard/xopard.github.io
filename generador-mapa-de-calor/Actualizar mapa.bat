@echo off
rem Genera "Mapa de calor.html" a partir de los GPX de Strava
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  py -3 -I preparar.py %*
) else (
  python -I preparar.py %*
)
if errorlevel 1 echo.& echo Ha habido errores: revisa los mensajes de arriba.
echo.
pause

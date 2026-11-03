@echo off
rem Genera "Mapa de calor.html" a partir de los GPX de Strava
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
rem pushd admite carpetas de red (\\servidor\...): les asigna una letra de unidad temporal
pushd "%~dp0"
if errorlevel 1 (
  echo No se puede entrar en la carpeta %~dp0
  pause
  exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  py -3 -I preparar.py %*
) else (
  python -I preparar.py %*
)
if errorlevel 1 echo.& echo Ha habido errores: revisa los mensajes de arriba.
popd
echo.
pause

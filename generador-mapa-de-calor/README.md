# Generador de «Mapa de calor.html»

Copia de la carpeta de trabajo que genera `../Mapa de calor.html` con las rutas de Strava.

- `Actualizar mapa.bat`: ejecuta `preparar.py`.
- `preparar.py`: lee los GPX de `..\..\Rutas Strava gpxs originales` y mete las rutas en la plantilla.
- `plantilla.html`: toda la interfaz de la página. **Los cambios de la app se hacen aquí**.
- `vendor/`: Leaflet 1.9.4, que se incrusta en la página.

No se suben `cache/` ni el HTML generado (ver `.gitignore`).

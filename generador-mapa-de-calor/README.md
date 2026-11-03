# Generador de «Mapa de calor.html»

Copia de la carpeta de trabajo que genera `../Mapa de calor.html` con las rutas de Strava.

- `Actualizar mapa.bat`: ejecuta `preparar.py`.
- `preparar.py`: lee los GPX de `..\..\Rutas Strava gpxs originales` y mete las rutas en la plantilla.
  Genera también dos KMZ para OruxMaps con la fecha del día:
  `Strava_Rutas_Bici_AA-MM-DD.kmz` (cada ruta, una carpeta por año) y
  `Strava_Calor_Bici_AA-MM-DD.kmz` (red de caminos sin repetir, coloreada por número de pasadas).
- `plantilla.html`: toda la interfaz de la página. **Los cambios de la app se hacen aquí**.
- `vendor/`: Leaflet 1.9.4, que se incrusta en la página.

No se suben `cache/`, el HTML generado ni los KMZ (ver `.gitignore`).

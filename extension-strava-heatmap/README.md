# Extensión «Mapa de calor: capa de Strava»

Hace que la capa «Mapa de calor de Strava» de [Mapa de calor](https://xopard.github.io/Mapa%20de%20calor.html)
funcione con tu sesión de Strava. Solo para Chrome o Edge en el PC.

## Instalar (una vez)

1. Descarga esta carpeta (o el `.zip`) y descomprímela en un sitio fijo: Chrome la usa desde ahí.
2. Abre `chrome://extensions` (en Edge, `edge://extensions`).
3. Activa **Modo de desarrollador** (arriba a la derecha).
4. Pulsa **Cargar descomprimida** y elige la carpeta `extension-strava-heatmap`.
5. Entra en <https://www.strava.com/maps/global-heatmap> con tu cuenta de Strava.

Si el icono de la extensión muestra un **!** rojo, no hay sesión de Strava: púlsalo y entra con tu cuenta.

## Usar

En Mapa de calor, abierto **desde la web** (no como fichero en el PC): *Aspecto del mapa* →
casilla **Mapa de calor de Strava**, con «Acceso a Strava» en «Con la extensión».

## Qué hace

Lee las cookies de tu sesión en strava.com y las añade solo a las peticiones de teselas del mapa de
calor (`*.strava.com/identified/globalheat/…`) que hace `xopard.github.io`. No envía nada a ningún
otro sitio. Es lo mismo que hace la extensión «Strava Heatmap» para gpx.studio y OpenStreetMap.

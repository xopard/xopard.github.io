#!/usr/bin/env python3
"""Genera «Mapa de calor.html» con todas las rutas de Strava dentro.

Uso: python -I preparar.py [carpeta_gpx] [--todo]

- Lee los GPX de ..\\..\\Rutas Strava gpxs originales (o de carpeta_gpx). No los modifica.
- Solo procesa los nuevos o cambiados: el resto sale de cache\\rutas.json.
- --todo ignora la caché.
"""
import json
import math
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA_DEF = os.path.join(AQUI, "..", "..", "Rutas Strava gpxs originales")
CACHE = os.path.join(AQUI, "cache", "rutas.json")
PLANTILLA = os.path.join(AQUI, "plantilla.html")
SALIDA = os.path.join(AQUI, "Mapa de calor.html")

# Subir este número si cambia el cálculo: invalida la caché
VERSION = 1
TOLERANCIA_M = 2.5        # simplificación: la comparación de rutas nuevas trabaja con ~25 m
UMBRAL_DESNIVEL_M = 5.0   # el mismo que Giros OruxMaps, para no sumar el ruido de la altitud
VEL_MOVIMIENTO = 0.7      # m/s (2,5 km/h); por debajo cuenta como parado
HUECO_PARADO_S = 60       # un hueco mayor sin puntos cuenta como parado aunque haya avanzado poco
R = 6371008.8


def largo(ruta):
    """Prefijo \\\\?\\ para las rutas con nombres muy largos."""
    ruta = os.path.abspath(ruta)
    return ruta if ruta.startswith("\\\\") else "\\\\?\\" + ruta


def dist(a, b):
    la1, lo1 = math.radians(a[0]), math.radians(a[1])
    la2, lo2 = math.radians(b[0]), math.radians(b[1])
    s = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(s)))


def leer_gpx(ruta):
    """Devuelve (nombre, [[(lat, lon, ele|None, t|None), ...] por trkseg])."""
    nombre, tramos, tramo = None, [], []
    for ev, el in ET.iterparse(ruta, events=("end",)):
        etq = el.tag.rsplit("}", 1)[-1]
        if etq == "trkpt":
            ele = t = None
            for h in el:
                eh = h.tag.rsplit("}", 1)[-1]
                if eh == "ele" and h.text:
                    ele = float(h.text)
                elif eh == "time" and h.text:
                    t = datetime.fromisoformat(h.text.strip().replace("Z", "+00:00")).timestamp()
            tramo.append((float(el.get("lat")), float(el.get("lon")), ele, t))
            el.clear()
        elif etq == "trkseg":
            if tramo:
                tramos.append(tramo)
            tramo = []
            el.clear()
        elif etq == "name" and nombre is None and el.text:
            nombre = el.text.strip()
    if tramo:
        tramos.append(tramo)
    return nombre, tramos


def simplificar(pts, tol):
    """Douglas-Peucker iterativo en proyección local. Devuelve los puntos conservados."""
    n = len(pts)
    if n < 3:
        return list(pts)
    k = math.cos(math.radians(pts[0][0]))
    xs = [math.radians(p[1]) * k * R for p in pts]
    ys = [math.radians(p[0]) * R for p in pts]
    tol2 = tol * tol
    marca = bytearray(n)
    marca[0] = marca[n - 1] = 1
    pila = [(0, n - 1)]
    while pila:
        i, j = pila.pop()
        ax, ay = xs[i], ys[i]
        dx, dy = xs[j] - ax, ys[j] - ay
        l2 = dx * dx + dy * dy
        peor, idx = tol2, -1
        for m in range(i + 1, j):
            px, py = xs[m] - ax, ys[m] - ay
            if l2 > 0:
                u = max(0.0, min(1.0, (px * dx + py * dy) / l2))
                px -= u * dx
                py -= u * dy
            d2 = px * px + py * py
            if d2 > peor:
                peor, idx = d2, m
        if idx >= 0:
            marca[idx] = 1
            pila.append((i, idx))
            pila.append((idx, j))
    return [pts[m] for m in range(n) if marca[m]]


def codificar(pts):
    """Polyline de Google con precisión 1e-5 (~1 m)."""
    salida, la0, lo0 = [], 0, 0
    for p in pts:
        la, lo = round(p[0] * 1e5), round(p[1] * 1e5)
        for v in (la - la0, lo - lo0):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                salida.append(chr((0x20 | (v & 0x1f)) + 63))
                v >>= 5
            salida.append(chr(v + 63))
        la0, lo0 = la, lo
    return "".join(salida)


def analizar(ruta, fichero):
    nombre, tramos = leer_gpx(ruta)
    if not sum(len(t) for t in tramos):
        raise ValueError("sin puntos")
    metros = subida = total = movimiento = 0.0
    t0 = t_fin = ref = None
    for tramo in tramos:
        for i, p in enumerate(tramo):
            if p[3] is not None:
                t0 = p[3] if t0 is None else t0
                t_fin = p[3]
            if p[2] is not None:
                if ref is None:
                    ref = p[2]
                elif p[2] - ref >= UMBRAL_DESNIVEL_M:
                    subida += p[2] - ref
                    ref = p[2]
                elif ref - p[2] >= UMBRAL_DESNIVEL_M:
                    ref = p[2]
            if i == 0:
                continue
            q = tramo[i - 1]
            d = dist(q, p)
            metros += d
            if p[3] is not None and q[3] is not None:
                dt = p[3] - q[3]
                if 0 < dt <= HUECO_PARADO_S and d / dt >= VEL_MOVIMIENTO:
                    movimiento += dt
    if t0 is not None:
        total = t_fin - t0
    geo = [codificar(simplificar(t, TOLERANCIA_M)) for t in tramos]
    fecha = datetime.fromtimestamp(t0).strftime("%Y-%m-%d") if t0 is not None else fichero[:10].replace("_", "-")
    return {
        "f": fichero, "n": nombre or os.path.splitext(fichero)[0], "d": fecha,
        "t0": round(t0) if t0 is not None else None,
        "km": round(metros / 1000, 2), "up": round(subida), "tt": round(total), "tm": round(movimiento),
        "g": geo, "pts": sum(len(t) for t in tramos),
    }


def cargar_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            c = json.load(f)
        return c["rutas"] if c.get("version") == VERSION else {}
    except (OSError, ValueError, KeyError):
        return {}


def guardar_cache(rutas):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": VERSION, "rutas": rutas}, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, CACHE)


def bloque_script(texto):
    """Evita que el texto cierre la etiqueta <script> o <style> que lo contiene."""
    return texto.replace("</script", "<\\/script").replace("</style", "<\\/style")


def generar_html(rutas):
    with open(PLANTILLA, encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(AQUI, "vendor", "leaflet.js"), encoding="utf-8") as f:
        leaflet_js = bloque_script(f.read())
    with open(os.path.join(AQUI, "vendor", "leaflet.css"), encoding="utf-8") as f:
        # Las imágenes de Leaflet no se usan: sin marcadores por defecto ni control de capas
        leaflet_css = f.read()
    datos = [{k: v for k, v in r.items() if k not in ("pts", "size", "mtime")} for r in rutas]
    # «<» escapado: un nombre de ruta no puede cerrar el <script>
    js = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    meta = json.dumps({"generado": datetime.now().strftime("%d-%m-%Y %H:%M")}, ensure_ascii=False)
    for marca, valor in (("/*__LEAFLET_CSS__*/", leaflet_css), ("/*__LEAFLET_JS__*/", leaflet_js),
                         ("/*__RUTAS__*/[]", js), ("/*__META__*/{}", meta)):
        if marca not in html:
            raise RuntimeError("falta " + marca + " en plantilla.html")
        html = html.replace(marca, valor, 1)
    tmp = SALIDA + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    os.replace(tmp, SALIDA)


# ---------- KMZ para OruxMaps ----------
# Dos ficheros con la fecha de hoy en el nombre:
# - Strava_Rutas_Bici_AA-MM-DD.kmz: cada ruta por separado, una carpeta por año.
# - Strava_Calor_Bici_AA-MM-DD.kmz: la red de caminos, cada uno una sola vez,
#   coloreado según cuántas rutas han pasado por él.
COLOR_RUTAS = ("ffb0279c", 2)                         # KML: aabbggrr. Morado #9C27B0
CLASES_CALOR = (                                      # (nombre, mínimo de pasadas, color, grosor)
    ("1 vez", 1, "ffd893ce", 2),                      # morado claro #CE93D8
    ("2 a 5 veces", 2, "ffb0279c", 3),                # morado #9C27B0
    ("Más de 5 veces", 6, "ff7e00e6", 4),             # rosa intenso #E6007E
)
FUSION_M = 15.0        # dos pasadas a menos de esto son el mismo camino
PASO_RED_M = 6.0       # separación de los puntos de la red
MIN_TROZO_M = 30.0     # un desvío más corto que esto no crea camino nuevo (ruido del GPS)
SIMPLIFICAR_RED_M = 3.0


def decodificar(cad):
    pts, i, la, lo = [], 0, 0, 0
    while i < len(cad):
        v = []
        for _ in (0, 1):
            r = s = 0
            while True:
                b = ord(cad[i]) - 63
                i += 1
                r |= (b & 31) << s
                s += 5
                if b < 32:
                    break
            v.append(~(r >> 1) if r & 1 else r >> 1)
        la += v[0]
        lo += v[1]
        pts.append((la / 1e5, lo / 1e5))
    return pts


def esc_xml(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def coords_kml(pts):
    return " ".join(f"{lo:.5f},{la:.5f}" for la, lo in pts)


def escribir_kmz(ruta, nombre, cuerpo):
    import zipfile
    kml = ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f"<name>{esc_xml(nombre)}</name>{cuerpo}</Document></kml>")
    tmp = ruta + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)
    os.replace(tmp, ruta)


def hms(s):
    m = round(s / 60)
    return f"{m // 60} h {m % 60:02d} min"


def kmz_rutas(rutas, ruta):
    nombre = os.path.splitext(os.path.basename(ruta))[0]
    partes = [f'<Style id="ruta"><LineStyle><color>{COLOR_RUTAS[0]}</color><width>{COLOR_RUTAS[1]}</width></LineStyle></Style>']
    por_anio = {}
    for r in rutas:
        por_anio.setdefault(r["d"][:4], []).append(r)
    for anio in sorted(por_anio, reverse=True):
        partes.append(f"<Folder><name>{anio}</name>")
        for r in sorted(por_anio[anio], key=lambda r: (r["t0"] or 0, r["f"])):
            lineas = [decodificar(g) for g in r["g"]]
            lineas = [l for l in lineas if len(l) > 1]
            if not lineas:
                continue
            geo = "".join(f"<LineString><coordinates>{coords_kml(l)}</coordinates></LineString>" for l in lineas)
            if len(lineas) > 1:
                geo = f"<MultiGeometry>{geo}</MultiGeometry>"
            desc = f"{r['d']}<br>Distancia: {r['km']:.1f} km<br>Desnivel: {r['up']:,} m+".replace(",", ".").replace(".", ",", 1)
            if r.get("tm"):
                desc += f"<br>En movimiento: {hms(r['tm'])}<br>Total: {hms(r['tt'])}"
            partes.append(f"<Placemark><name>{esc_xml(r['n'])}</name><description><![CDATA[{desc}]]></description>"
                          f"<styleUrl>#ruta</styleUrl>{geo}</Placemark>")
        partes.append("</Folder>")
    escribir_kmz(ruta, nombre, "".join(partes))


def red_de_caminos(rutas):
    """Funde todas las rutas en una red donde cada camino aparece una vez.

    Devuelve [(lista de (lat, lon), lista de pasadas por punto)]. Se recorren las rutas por fecha:
    lo que queda a menos de FUSION_M de la red ya existente suma una pasada a esos puntos
    (una vez por ruta); lo que no, se añade a la red como camino nuevo.
    """
    k_lat = math.pi / 180 * R
    xy = lambda la, lo: (math.radians(lo) * R * math.cos(math.radians(la)), la * k_lat)
    celda = FUSION_M
    rejilla = {}
    nlat, nlon, nx, ny, cuenta, origen = [], [], [], [], [], []   # nodos de la red
    lineas = []                                                   # listas de índices de nodo
    f2 = FUSION_M * FUSION_M
    cerca = math.ceil(3 * FUSION_M / PASO_RED_M)   # nodos recién puestos por la misma ruta: no cuentan

    def nuevo_nodo(la, lo, x, y, r, i):
        nlat.append(la); nlon.append(lo); nx.append(x); ny.append(y); cuenta.append(1); origen.append((r, i))
        rejilla.setdefault((math.floor(x / celda), math.floor(y / celda)), []).append(len(nx) - 1)
        return len(nx) - 1

    for ir, r in enumerate(sorted(rutas, key=lambda r: (r["t0"] or 0, r["f"]))):
        tocados, base = set(), 0     # base: nº de muestras de los tramos anteriores de esta ruta
        for g in r["g"]:
            pts = decodificar(g)
            # Muestras cada PASO_RED_M
            mu = []
            for a, b in zip(pts, pts[1:]):
                d = dist(a, b)
                n = max(1, math.ceil(d / PASO_RED_M))
                for j in range(n):
                    mu.append((a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n))
            if pts:
                mu.append(pts[-1])
            # Para cada muestra: nodos de la red cercanos (de otras rutas, o de esta pero de hace rato)
            cercanos = []
            for i, (la, lo) in enumerate(mu):
                x, y = xy(la, lo)
                cx, cy = math.floor(x / celda), math.floor(y / celda)
                lista, mejor, mejor_d = [], -1, f2
                for a in (cx - 1, cx, cx + 1):
                    for b in (cy - 1, cy, cy + 1):
                        for n in rejilla.get((a, b), ()):
                            o = origen[n]
                            if o[0] == ir and base + i - o[1] < cerca:
                                continue
                            d2 = (nx[n] - x) ** 2 + (ny[n] - y) ** 2
                            if d2 <= f2:
                                lista.append(n)
                                if d2 < mejor_d:
                                    mejor, mejor_d = n, d2
                cercanos.append((lista, mejor))
                if lista:
                    tocados.update(lista)
                    continue
                # Muestra nueva: se añade ya, para que la vuelta de una ida y vuelta la encuentre
                cercanos[-1] = ([], nuevo_nodo(la, lo, x, y, ir, base + i))
            # Trozos de muestras nuevas → caminos nuevos, unidos a la red por sus extremos
            i = 0
            while i < len(mu):
                if cercanos[i][0]:
                    i += 1
                    continue
                j = i
                while j + 1 < len(mu) and not cercanos[j + 1][0]:
                    j += 1
                ids = [cercanos[m][1] for m in range(i, j + 1)]
                if i > 0:
                    ids.insert(0, cercanos[i - 1][1])
                if j + 1 < len(mu):
                    ids.append(cercanos[j + 1][1])
                largo_m = (j - i + 1) * PASO_RED_M
                if largo_m >= MIN_TROZO_M and len(ids) > 1:
                    lineas.append(ids)
                i = j + 1
            base += len(mu)
        for n in tocados:
            if origen[n][0] != ir:
                cuenta[n] += 1
    return [([(nlat[n], nlon[n]) for n in l], [cuenta[n] for n in l]) for l in lineas]


def kmz_calor(rutas, ruta):
    nombre = os.path.splitext(os.path.basename(ruta))[0]
    clase = lambda c: max(i for i, (_, mn, _, _) in enumerate(CLASES_CALOR) if c >= mn)
    trozos = [[] for _ in CLASES_CALOR]
    for pts, cuentas in red_de_caminos(rutas):
        # Se parte cada camino donde cambia de clase; el punto de corte va en los dos trozos
        ini = 0
        for m in range(1, len(pts) + 1):
            if m == len(pts) or clase(cuentas[m]) != clase(cuentas[ini]):
                tramo = pts[ini:m + 1] if m < len(pts) else pts[ini:]
                if len(tramo) > 1:
                    tramo = [(p[0], p[1], None, None) for p in tramo]
                    trozos[clase(cuentas[ini])].append([p[:2] for p in simplificar(tramo, SIMPLIFICAR_RED_M)])
                ini = m
    partes = []
    for i, (nom, _, color, ancho) in enumerate(CLASES_CALOR):
        partes.append(f'<Style id="c{i}"><LineStyle><color>{color}</color><width>{ancho}</width></LineStyle></Style>')
    # De menos a más pasadas: los caminos más usados quedan encima
    for i, (nom, _, _, _) in enumerate(CLASES_CALOR):
        if not trozos[i]:
            continue
        geo = "".join(f"<LineString><coordinates>{coords_kml(t)}</coordinates></LineString>" for t in trozos[i])
        partes.append(f"<Folder><name>{esc_xml(nom)}</name><Placemark><name>{esc_xml(nom)}</name>"
                      f"<styleUrl>#c{i}</styleUrl><MultiGeometry>{geo}</MultiGeometry></Placemark></Folder>")
    escribir_kmz(ruta, nombre, "".join(partes))


def generar_kmz(rutas):
    hoy = datetime.now().strftime("%y-%m-%d")
    salidas = []
    for prefijo, fn in (("Strava_Rutas_Bici", kmz_rutas), ("Strava_Calor_Bici", kmz_calor)):
        ruta = os.path.join(AQUI, f"{prefijo}_{hoy}.kmz")
        inicio = time.time()
        fn(rutas, ruta)
        salidas.append(f"Generado: {ruta} ({os.path.getsize(ruta) / 1e6:.1f} MB, {time.time() - inicio:.0f} s)")
    return salidas


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    carpeta = args[0] if args else CARPETA_DEF
    previa = {} if "--todo" in sys.argv else cargar_cache()
    entradas = sorted((e for e in os.scandir(largo(carpeta)) if e.name.lower().endswith(".gpx") and e.is_file()),
                      key=lambda e: e.name)
    if not entradas:
        print("No hay GPX en", carpeta)
        return 1
    print(f"{len(entradas)} GPX en {os.path.abspath(carpeta)}")
    rutas, errores, nuevas = {}, [], 0
    inicio = time.time()
    for e in entradas:
        st = e.stat()
        c = previa.get(e.name)
        if c and c["size"] == st.st_size and c["mtime"] == int(st.st_mtime):
            rutas[e.name] = c
            continue
        try:
            d = analizar(e.path, e.name)
        except (ET.ParseError, ValueError, OSError) as ex:
            errores.append(f"{e.name}: {ex}")
            continue
        d.update(size=st.st_size, mtime=int(st.st_mtime))
        rutas[e.name] = d
        nuevas += 1
        print(f"  [{nuevas}] {d['km']:7.1f} km  {d['up']:5d} m  {d['n']}", flush=True)
        if nuevas % 25 == 0:
            guardar_cache(rutas | {k: v for k, v in previa.items() if k not in rutas})
    guardar_cache(rutas)
    orden = sorted(rutas.values(), key=lambda r: (r["t0"] or 0, r["f"]), reverse=True)
    generar_html(orden)
    print("Generando los KMZ para OruxMaps…", flush=True)
    kmz = generar_kmz(orden)
    print(f"\n{nuevas} procesadas y {len(rutas) - nuevas} de la caché en {time.time() - inicio:.0f} s")
    print(f"{len(orden)} rutas, {sum(r['km'] for r in orden):,.0f} km, {sum(r['up'] for r in orden):,} m+")
    print(f"Puntos: {sum(r['pts'] for r in orden):,} originales")
    print(f"Generado: {SALIDA} ({os.path.getsize(SALIDA) / 1e6:.1f} MB)")
    for linea in kmz:
        print(linea)
    for err in errores:
        print("ERROR", err)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())

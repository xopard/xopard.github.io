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
    print(f"\n{nuevas} procesadas y {len(rutas) - nuevas} de la caché en {time.time() - inicio:.0f} s")
    print(f"{len(orden)} rutas, {sum(r['km'] for r in orden):,.0f} km, {sum(r['up'] for r in orden):,} m+")
    print(f"Puntos: {sum(r['pts'] for r in orden):,} originales")
    print(f"Generado: {SALIDA} ({os.path.getsize(SALIDA) / 1e6:.1f} MB)")
    for err in errores:
        print("ERROR", err)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())

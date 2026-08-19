"""zerolith · exemple « artefact hébergé ».

Une seule fonction Python qui rend une PAGE, pas un JSON : elle va chercher ses données
côté serveur (open-meteo, sans clé), calcule la géométrie de deux graphiques, et renvoie
un document HTML autonome — SVG en ligne, CSS en ligne, aucune dépendance externe, aucune
étape de build, aucun bundler.

C'est le même geste qu'un artefact de chatbot, sauf que le résultat a une URL stable, que
les données sont fraîches à chaque chargement, et qu'aucun pod ne tourne entre deux
visites.

    GET /?city=Paris
    GET /?city=Tokyo&days=7
    GET /?city=Paris&format=json     -> les mêmes données, brutes
"""

import html
import math
import os
import time
from datetime import datetime
from urllib.parse import quote

import httpx

TIMEOUT = float(os.environ.get("DEMO_TIMEOUT_SECONDS", "8"))
UA = {"User-Agent": "zerolith-demo/1.0 (+https://zerolith.io)"}

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Palette de marque, mais ramenée dans la bande de luminosité qui reste lisible sur un
# fond quasi noir : des néons purs à 2 px de trait « bavent » et deux séries voisines
# cessent d'être distinguables en vision daltonienne.
CYAN = "#1fa3a7"
AMBER = "#d26a10"
INK = "#c9d6e2"
INK_DIM = "#8497a6"
INK_FAINT = "#5b6c7b"
GRID = "#16212e"
SURFACE = "#070b11"
PANEL = "#0c121b"

_BOOT = time.monotonic()
_POD = os.environ.get("HOSTNAME", "inconnu")
_SERVED = 0

JOURS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]


# ─────────────────────────────────────────────────────────────────────────────
# Données
# ─────────────────────────────────────────────────────────────────────────────


def fetch(city, days):
    with httpx.Client(headers=UA, timeout=TIMEOUT) as client:
        geo = client.get(
            GEOCODE_URL, params={"name": city, "count": 1, "language": "fr"}
        )
        geo.raise_for_status()
        hits = geo.json().get("results") or []
        if not hits:
            return None
        place = hits[0]

        forecast = client.get(
            FORECAST_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,apparent_temperature,wind_speed_10m,relative_humidity_2m",
                "hourly": "temperature_2m",
                "daily": "temperature_2m_max,temperature_2m_min",
                "forecast_days": days,
                "timezone": "auto",
            },
        )
        forecast.raise_for_status()
        data = forecast.json()

    hourly = data["hourly"]
    daily = data["daily"]
    # Une fenêtre de 24 h CENTRÉE SUR MAINTENANT (6 h de passé, 18 h à venir) : open-meteo
    # renvoie les heures à partir de minuit, et à 23 h un graphe « aujourd'hui » n'aurait
    # plus rien à montrer.
    now = data["current"]["time"][:13]
    cursor = next((i for i, t in enumerate(hourly["time"]) if t[:13] >= now), 0)
    start = max(0, cursor - 6)
    return {
        "city": place["name"],
        "country": place.get("country"),
        "timezone": data.get("timezone"),
        "current": data["current"],
        "hourly": [
            {"t": t, "temp": v}
            for t, v in zip(
                hourly["time"][start : start + 24],
                hourly["temperature_2m"][start : start + 24],
            )
            if v is not None
        ],
        "daily": [
            {"date": d, "min": lo, "max": hi}
            for d, lo, hi in zip(
                daily["time"], daily["temperature_2m_min"], daily["temperature_2m_max"]
            )
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Géométrie : tout le calcul des graphiques se fait ici, en Python.
# ─────────────────────────────────────────────────────────────────────────────


def nice_scale(lo, hi, ticks=4):
    """Une échelle qui tombe sur des valeurs rondes, avec un peu d'air en haut/bas."""
    span = max(hi - lo, 1.0)
    raw = span / ticks
    magnitude = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 0.1
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    bottom = step * math.floor(lo / step)
    top = bottom + step * ticks
    while top < hi:
        top += step
    return bottom, top, step


def line_chart(points, width=760, height=220):
    """Courbe horaire : une seule série, donc pas de légende — le titre la nomme."""
    pad_l, pad_r, pad_t, pad_b = 44, 16, 18, 34
    temps = [p["temp"] for p in points]
    lo, hi, step = nice_scale(min(temps), max(temps))
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    def x_of(i):
        return pad_l + (plot_w * i / max(len(points) - 1, 1))

    def y_of(v):
        return pad_t + plot_h - plot_h * (v - lo) / (hi - lo)

    coords = [(x_of(i), y_of(p["temp"])) for i, p in enumerate(points)]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(coords))
    area = (
        f"{line} L{coords[-1][0]:.1f},{pad_t + plot_h:.1f} "
        f"L{coords[0][0]:.1f},{pad_t + plot_h:.1f} Z"
    )

    out = []
    # Grille horizontale seulement : les repères verticaux n'aident pas une courbe.
    v = lo
    while v <= hi + 1e-9:
        y = y_of(v)
        out.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" class="tick">{v:g}°</text>'
        )
        v += step

    out.append(f'<path d="{area}" fill="url(#fade)"/>')
    out.append(
        f'<path d="{line}" fill="none" stroke="{CYAN}" stroke-width="2" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # Étiquettes directes sur les seuls points qui méritent un chiffre : le pic et le creux.
    # Une seule si la série est plate — sinon les deux se superposent au même endroit.
    marked = [("max", temps.index(max(temps)))]
    if max(temps) != min(temps):
        marked.append(("min", temps.index(min(temps))))

    for label, idx in marked:
        x, y = coords[idx]
        # Le creux s'étiquette EN DESSOUS, sauf s'il touche le bas du cadre : là, l'étiquette
        # tomberait dans la rangée des heures. Une échelle arrondie rend le cas rare, pas
        # impossible — et « rare » est exactement ce qui n'est jamais testé.
        dy = -12 if label == "max" or y > pad_t + plot_h - 22 else 20
        # Près d'un bord, une étiquette centrée déborde sur la colonne des graduations.
        if x < pad_l + 24:
            anchor, dx = "start", 8
        elif x > width - pad_r - 24:
            anchor, dx = "end", -8
        else:
            anchor, dx = "middle", 0
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{CYAN}" '
            f'stroke="{SURFACE}" stroke-width="2"/>'
        )
        out.append(
            f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}" class="peak">'
            f"{temps[idx]:g}°</text>"
        )

    # Heures, une graduation sur trois.
    for i, p in enumerate(points):
        if i % 3:
            continue
        hour = p["t"][11:16]
        out.append(
            f'<text x="{x_of(i):.1f}" y="{height - 8}" text-anchor="middle" class="tick">{hour}</text>'
        )

    # Couche de survol : une bande par point, plus large que la marque elle-même.
    band = plot_w / max(len(points) - 1, 1)
    for i, (x, y) in enumerate(coords):
        out.append(
            f'<rect class="hit" x="{x - band / 2:.1f}" y="{pad_t}" width="{band:.1f}" '
            f'height="{plot_h}" fill="transparent" data-x="{x:.1f}" data-y="{y:.1f}" '
            f'data-label="{points[i]["t"][11:16]}" data-value="{points[i]["temp"]:g} °C"/>'
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" '
        f'aria-label="Température heure par heure">'
        f'<defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{CYAN}" stop-opacity="0.22"/>'
        f'<stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/>'
        f"</linearGradient></defs>"
        + "".join(out)
        # Le viseur est émis EN DERNIER : en SVG il n'y a pas de z-index, seul l'ordre
        # du document décide de ce qui passe au-dessus.
        + f'<g class="crosshair" style="display:none" pointer-events="none">'
        f'<line y1="{pad_t}" y2="{pad_t + plot_h}" stroke="{INK_FAINT}" stroke-width="1"/>'
        f'<circle r="5" fill="{CYAN}" stroke="{SURFACE}" stroke-width="2"/></g>'
        + "</svg>"
    )


def range_chart(days, width=760, height=200):
    """Barres d'amplitude : une barre = l'intervalle min→max d'un jour, pas une magnitude.
    C'est pourquoi elle ne part pas de zéro — elle encode un segment, pas une quantité."""
    # pad_b tient DEUX rangées de texte sous le cadre : le minimum de chaque barre, puis le
    # nom du jour.
    pad_l, pad_r, pad_t, pad_b = 44, 16, 26, 44
    lo, hi, step = nice_scale(
        min(d["min"] for d in days), max(d["max"] for d in days)
    )
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    slot = plot_w / len(days)
    bar_w = min(26, slot - 14)  # l'espace entre deux barres reste ≥ 14 px

    def y_of(v):
        return pad_t + plot_h - plot_h * (v - lo) / (hi - lo)

    out = []
    v = lo
    while v <= hi + 1e-9:
        y = y_of(v)
        out.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" class="tick">{v:g}°</text>'
        )
        v += step

    for i, d in enumerate(days):
        cx = pad_l + slot * (i + 0.5)
        y_hi, y_lo = y_of(d["max"]), y_of(d["min"])
        date = datetime.fromisoformat(d["date"])
        out.append(
            f'<rect class="hit bar" x="{cx - bar_w / 2:.1f}" y="{y_hi:.1f}" width="{bar_w:.1f}" '
            f'height="{max(y_lo - y_hi, 4):.1f}" rx="4" fill="{AMBER}" '
            f'data-label="{JOURS[date.weekday()]} {date.day}" '
            f'data-value="{d["min"]:g} → {d["max"]:g} °C"/>'
        )
        out.append(
            f'<text x="{cx:.1f}" y="{y_hi - 8:.1f}" text-anchor="middle" class="peak">{d["max"]:g}°</text>'
        )
        out.append(
            f'<text x="{cx:.1f}" y="{y_lo + 15:.1f}" text-anchor="middle" class="tick">{d["min"]:g}°</text>'
        )
        out.append(
            f'<text x="{cx:.1f}" y="{height - 8}" text-anchor="middle" class="tick">'
            f"{JOURS[date.weekday()]}</text>"
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" '
        f'aria-label="Amplitude quotidienne, minimum au maximum">' + "".join(out) + "</svg>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────

CSS = f"""
*{{box-sizing:border-box}}
body{{margin:0;background:{SURFACE};color:{INK};
  font:14px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
.wrap{{max-width:860px;margin:0 auto;padding:32px 20px 64px}}
h1{{font-size:26px;letter-spacing:.04em;margin:0 0 4px;font-weight:700}}
h2{{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:{INK_DIM};
  margin:36px 0 10px;font-weight:700}}
.sub{{color:{INK_DIM};margin:0 0 28px;font-size:13px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.tile{{background:{PANEL};border:1px solid {GRID};border-left:2px solid {CYAN};
  border-radius:2px;padding:14px 16px}}
.tile .v{{font-size:28px;font-weight:700;color:{INK};line-height:1.2}}
.tile .k{{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:{INK_DIM}}}
.panel{{background:{PANEL};border:1px solid {GRID};border-radius:2px;padding:8px 4px;
  position:relative}}
.chart{{width:100%;height:auto;display:block;overflow:visible}}
.tick{{fill:{INK_FAINT};font-size:11px}}
.peak{{fill:{INK};font-size:12px;font-weight:700}}
.hit:hover{{cursor:crosshair}}
.bar{{transition:opacity .12s}}
.panel:hover .bar{{opacity:.55}}
.bar:hover{{opacity:1}}
.tip{{position:absolute;pointer-events:none;opacity:0;transition:opacity .1s;
  background:{SURFACE};border:1px solid {CYAN};border-radius:2px;padding:6px 9px;
  font-size:12px;white-space:nowrap;transform:translate(-50%,-140%);z-index:5}}
.tip b{{color:{CYAN};font-weight:700}}
details{{margin-top:12px}}
summary{{color:{INK_DIM};font-size:12px;cursor:pointer}}
table{{border-collapse:collapse;margin-top:10px;font-size:12px;width:100%}}
th,td{{text-align:right;padding:4px 10px;border-bottom:1px solid {GRID};
  font-variant-numeric:tabular-nums}}
th:first-child,td:first-child{{text-align:left}}
th{{color:{INK_DIM};font-weight:400;font-size:10px;letter-spacing:.14em;text-transform:uppercase}}
footer{{margin-top:44px;padding-top:18px;border-top:1px solid {GRID};
  color:{INK_FAINT};font-size:12px}}
a{{color:{CYAN};text-decoration:none}} a:hover{{color:{AMBER}}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
"""

JS = """
document.querySelectorAll('.panel').forEach(function (panel) {
  var tip = document.createElement('div');
  tip.className = 'tip';
  panel.appendChild(tip);
  var cross = panel.querySelector('.crosshair');
  var svg = panel.querySelector('svg');
  panel.querySelectorAll('.hit').forEach(function (hit) {
    hit.addEventListener('pointerenter', function () {
      var box = hit.getBoundingClientRect(), p = panel.getBoundingClientRect();
      tip.innerHTML = hit.dataset.label + ' &nbsp;<b>' + hit.dataset.value + '</b>';
      tip.style.left = (box.left + box.width / 2 - p.left) + 'px';
      tip.style.top = (hit.dataset.y
        ? svg.getBoundingClientRect().top - p.top
          + (+hit.dataset.y) * svg.getBoundingClientRect().height / svg.viewBox.baseVal.height
        : box.top - p.top) + 'px';
      tip.style.opacity = 1;
      if (cross && hit.dataset.x) {
        cross.style.display = '';
        cross.querySelector('line').setAttribute('x1', hit.dataset.x);
        cross.querySelector('line').setAttribute('x2', hit.dataset.x);
        cross.querySelector('circle').setAttribute('cx', hit.dataset.x);
        cross.querySelector('circle').setAttribute('cy', hit.dataset.y);
      }
    });
  });
  panel.addEventListener('pointerleave', function () {
    tip.style.opacity = 0;
    if (cross) cross.style.display = 'none';
  });
});
"""


def page(d, meta):
    """Assemble le document. `html.escape` sur TOUT ce qui vient de la requête : le nom de
    ville arrive du client, et il finit dans le HTML."""
    cur = d["current"]
    city = html.escape(f"{d['city']}, {d['country']}")
    tiles = [
        ("Température", f"{cur['temperature_2m']:g}°"),
        ("Ressenti", f"{cur['apparent_temperature']:g}°"),
        ("Vent", f"{cur['wind_speed_10m']:g} km/h"),
        ("Humidité", f"{cur['relative_humidity_2m']:g} %"),
    ]
    rows = "".join(
        f"<tr><td>{html.escape(x['date'])}</td><td>{x['min']:g} °C</td>"
        f"<td>{x['max']:g} °C</td></tr>"
        for x in d["daily"]
    )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{city} — tableau de bord</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<h1>{city}</h1>
<p class="sub">Fuseau {html.escape(d["timezone"] or "?")} · relevé
{html.escape(cur["time"])} · page assemblée en {meta["render_ms"]} ms</p>

<div class="tiles">
{"".join(f'<div class="tile"><div class="v">{v}</div><div class="k">{k}</div></div>'
         for k, v in tiles)}
</div>

<h2>Température, heure par heure</h2>
<div class="panel">{line_chart(d["hourly"][:24])}</div>

<h2>Amplitude quotidienne (min → max)</h2>
<div class="panel">{range_chart(d["daily"])}
<details><summary>Voir les données</summary>
<table><thead><tr><th>Jour</th><th>Min</th><th>Max</th></tr></thead>
<tbody>{rows}</tbody></table></details></div>

<footer>
Rendu par une fonction zerolith · pod <code>{html.escape(meta["pod"])}</code> ·
{"démarrage à froid" if meta["cold_start"] else f'pod en vie depuis {meta["pod_age_s"]} s'} ·
requête n° {meta["served"]} de ce pod<br>
Données <a href="https://open-meteo.com">open-meteo</a>, récupérées côté serveur en
{meta["fetch_ms"]} ms · <a href="?city={quote(d["city"])}&amp;format=json">les mêmes
données en JSON</a>
</footer>
</div><script>{JS}</script></body></html>"""


HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


def handler(request):
    global _SERVED
    started = time.perf_counter()
    cold = _SERVED == 0
    _SERVED += 1

    city = (request.query.get("city") or "Paris").strip()[:80]
    try:
        days = min(max(int(request.query.get("days", 7)), 2), 10)
    except ValueError:
        days = 7

    fetch_started = time.perf_counter()
    data = fetch(city, days)
    fetch_ms = round((time.perf_counter() - fetch_started) * 1000)

    if data is None:
        body = (
            f"<!doctype html><meta charset=utf-8><style>{CSS}</style>"
            f'<div class=wrap><h1>Ville introuvable</h1><p class=sub>Aucun résultat pour '
            f"« {html.escape(city)} ». Essayez <a href=?city=Paris>Paris</a>.</p></div>"
        )
        return 404, body, HTML_HEADERS

    meta = {
        "render_ms": 0,
        "fetch_ms": fetch_ms,
        "pod": _POD,
        "cold_start": cold,
        "pod_age_s": round(time.monotonic() - _BOOT, 1),
        "served": _SERVED,
    }

    if request.query.get("format") == "json":
        meta["render_ms"] = round((time.perf_counter() - started) * 1000)
        return 200, {**data, "meta": meta}

    meta["render_ms"] = round((time.perf_counter() - started) * 1000)
    return 200, page(data, meta), HTML_HEADERS

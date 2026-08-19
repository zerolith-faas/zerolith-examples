"""zerolith · exemple « agrégateur d'API ».

Un cas d'usage courant : une requête cliente déclenche un géocodage, puis un appel
simultané à trois APIs publiques (météo, qualité de l'air, Wikipédia), le tout fusionné
en une seule réponse JSON. La latence rendue est celle de l'API la plus lente, pas la
somme des trois.

Aucune clé d'API, aucun état conservé : la fonction est purement calculatoire. C'est le
profil idéal pour le scale-to-zero — elle ne coûte rien tant que personne ne l'appelle,
et la réponse expose son propre temps de démarrage pour que vous puissiez le constater.

    GET /?city=Paris
    GET /?city=Tokyo&lang=en
"""

import asyncio
import os
import time
from urllib.parse import quote

import httpx

TIMEOUT = float(os.environ.get("DEMO_TIMEOUT_SECONDS", "6"))
UA = {"User-Agent": "zerolith-demo/1.0 (+https://zerolith.io)"}

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Échelle European AQI (bornes hautes -> libellé).
AQI_BANDS = [
    (20, "bon"),
    (40, "correct"),
    (60, "moyen"),
    (80, "mauvais"),
    (100, "très mauvais"),
    (float("inf"), "extrêmement mauvais"),
]

# Cette fonction est appelée depuis un navigateur : sans cet en-tête, le navigateur
# refuse de livrer la réponse à la page. « * » est ici sans risque — la fonction est
# publique et ne lit aucun cookie, elle n'expose donc rien de plus qu'un appel anonyme.
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "no-store",
}

# Renseigné à l'import du module, donc au démarrage du pod : les compteurs ci-dessous
# mesurent la vraie durée de vie de l'instance, pas celle de la requête.
_BOOT = time.monotonic()
_POD = os.environ.get("HOSTNAME", "inconnu")
_SERVED = 0


def _aqi_label(value):
    if value is None:
        return None
    return next(label for ceiling, label in AQI_BANDS if value < ceiling)


async def _fetch(client, name, url, params):
    """Retourne (nom, résultat) sans jamais lever : une source indisponible dégrade la
    réponse au lieu de la casser.

    Les erreurs de connexion transitoires sont réessayées quelques fois, très brièvement.
    Le géocodage est une dépendance dure de la réponse : sans ces essais, un aléa réseau
    d'une fraction de seconde transformerait une requête parfaitement valide en 404.
    """
    started = time.perf_counter()
    last = None
    for attempt in range(3):
        try:
            response = await client.get(url, params=params, headers=UA, timeout=TIMEOUT)
            response.raise_for_status()
            return name, {
                "ok": True,
                "ms": round((time.perf_counter() - started) * 1000),
                "data": response.json(),
            }
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            last = exc
            await asyncio.sleep(0.25 * (attempt + 1))
        except Exception as exc:
            last = exc
            break
    return name, {
        "ok": False,
        "ms": round((time.perf_counter() - started) * 1000),
        "error": f"{type(last).__name__}: {last}",
    }


async def _geocode(client, city):
    name, result = await _fetch(
        client, "geocoding", GEOCODE_URL, {"name": city, "count": 1, "language": "fr"}
    )
    if not result["ok"]:
        return None, result
    hits = result["data"].get("results") or []
    if not hits:
        return None, {**result, "ok": False, "error": f"ville introuvable : {city!r}"}
    return hits[0], result


async def _aggregate(city, lang):
    timings = {}
    async with httpx.AsyncClient() as client:
        place, timings["geocoding"] = await _geocode(client, city)
        if place is None:
            return None, timings

        coords = {"latitude": place["latitude"], "longitude": place["longitude"]}
        fanout_started = time.perf_counter()

        # Le cœur de l'exemple : trois APIs indépendantes interrogées en parallèle, donc
        # la latence totale est celle de la plus lente et non la somme des trois.
        results = await asyncio.gather(
            _fetch(
                client,
                "weather",
                FORECAST_URL,
                {**coords, "current": "temperature_2m,wind_speed_10m,weather_code"},
            ),
            _fetch(client, "air_quality", AIR_URL, {**coords, "current": "european_aqi"}),
            _fetch(
                client,
                "wikipedia",
                f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(place['name'])}",
                None,
            ),
        )
        fanout_ms = round((time.perf_counter() - fanout_started) * 1000)

    sources = dict(results)
    timings.update(sources)

    weather = sources["weather"].get("data", {}).get("current", {})
    air = sources["air_quality"].get("data", {}).get("current", {})
    aqi = air.get("european_aqi")

    body = {
        "city": place["name"],
        "country": place.get("country"),
        "coordinates": {"lat": place["latitude"], "lon": place["longitude"]},
        "timezone": place.get("timezone"),
        "weather": {
            "temperature_c": weather.get("temperature_2m"),
            "wind_kmh": weather.get("wind_speed_10m"),
            "observed_at": weather.get("time"),
        },
        "air_quality": {"european_aqi": aqi, "label": _aqi_label(aqi)},
        "about": sources["wikipedia"].get("data", {}).get("extract"),
        "fanout_ms": fanout_ms,
    }
    return body, timings


def handler(request):
    global _SERVED

    started = time.perf_counter()
    cold_start = _SERVED == 0
    _SERVED += 1

    city = (request.query.get("city") or "Paris").strip()
    lang = (request.query.get("lang") or "fr").strip().lower()
    if lang not in ("fr", "en", "de", "es", "it"):
        lang = "fr"

    body, timings = asyncio.run(_aggregate(city, lang))
    if body is None:
        error = timings["geocoding"].get("error", "géocodage impossible")
        return 404, {"error": error, "city": city}, CORS

    body["meta"] = {
        "total_ms": round((time.perf_counter() - started) * 1000),
        "sources": {name: {"ok": r["ok"], "ms": r["ms"]} for name, r in timings.items()},
        # Le nom du pod change à chaque remontée depuis zéro : de quoi vérifier vous-même
        # le scale-to-zero en rappelant la fonction après quelques minutes d'inactivité.
        "pod": _POD,
        "cold_start": cold_start,
        "pod_age_seconds": round(time.monotonic() - _BOOT, 1),
        "requests_served_by_this_pod": _SERVED,
    }
    return 200, body, CORS

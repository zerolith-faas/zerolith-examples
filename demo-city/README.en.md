*[Français](README.md)*

# demo-city

An API aggregator in one Python function: a geocode, then three **concurrent** calls (weather,
air quality, Wikipedia) merged into a single JSON response.

**Live:** <https://demo-city-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/?city=Paris&lang=en>

## What it demonstrates

The latency the client sees is that of the slowest API, **not the sum of the three**: the calls
leave together through `asyncio.gather`. That gain is what justifies aggregating server-side
rather than in the browser, where three separate requests would also have cost the client three
round trips.

No API key, no state kept: the function is purely computational. That is the ideal scale-to-zero
profile — it costs nothing while nobody calls it. The response reports its own startup time, so
you can observe the cold start instead of taking our word for it.

## Calling it

```bash
curl "https://<function-url>/?city=Tokyo"
curl "https://<function-url>/?city=Paris&lang=en"
```

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `city` | `Paris` | the city to geocode |
| `lang` | `fr` | the response language |

## Deploying

Runtime `python`, handler `main.handler`. `httpx` already ships with the runtime — nothing to
install.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEMO_TIMEOUT_SECONDS` | `6` | maximum time allowed to each upstream API |

The APIs it calls (open-meteo, Wikipedia) are public and keyless. If you deploy this example
as-is, its outbound calls leave through your isolated space — worth remembering if you swap those
APIs for a service that counts requests.

*[Français](README.md)*

# demo-dashboard

A weather dashboard that returns a **complete HTML page**: the function fetches its data
server-side, computes the geometry of its two charts in Python, and returns a self-contained
document — inline SVG, inline CSS, no external dependency.

**Live:** <https://demo-dashboard-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/?city=Paris>

## What it demonstrates

The SVG is **already drawn when the document arrives**. No bundler, no build step, no loading
screen, no second request to go fetch the data: one URL, one response, the page is finished.

It is the same gesture as a chatbot artifact, except the result has a stable URL, the data is
fresh on every load, and no pod runs between two visits. This is the function the article
["Artifact, canvas, frame"](https://zerolith.io/en/blog/serverless-html-dashboard) is built on.

The same URL with `?format=json` returns the same data raw: the rendering and the data come out
of the same handler, without duplicating them.

## Calling it

```bash
curl "https://<function-url>/?city=Tokyo&days=7"
curl "https://<function-url>/?city=Paris&format=json"
```

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `city` | `Paris` | the city shown (truncated to 80 characters) |
| `days` | `7` | forecast days, clamped between 2 and 10 |
| `format` | — | `json` for the raw data instead of the page |

## Deploying

Runtime `python`, handler `main.handler`. `httpx` already ships with the runtime.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEMO_TIMEOUT_SECONDS` | `8` | maximum time allowed to the weather API |

The data comes from open-meteo, public and keyless.

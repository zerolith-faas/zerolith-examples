*[Français](README.md)*

# zerolith-examples

Ready-to-deploy example functions for [zerolith](https://zerolith.io), the scale-to-zero
Functions-as-a-Service platform.

Each directory holds a single file — the handler — that you can paste as-is into the deploy
form. The four gallery examples are the **code really running in production** behind the public
URLs listed below: what you read here is what answers when you call.

> The handlers' own docstrings and comments are in French, as is the platform's primary
> documentation. The code itself needs no translation.

## The examples

| Directory | Runtime | What it does | Live |
|-----------|---------|--------------|------|
| [`hello/`](hello/) | python · nodejs24 | The smallest handler that works, in both languages. The starting point. | — |
| [`demo-dashboard/`](demo-dashboard/) | python | A weather dashboard returning a **complete HTML page**, its SVG drawn server-side. No bundler, no build step, no loading screen. | [call it](https://demo-dashboard-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/?city=Paris) |
| [`demo-city/`](demo-city/) | python | An API aggregator: a geocode, then three **concurrent** calls merged into one JSON response. Latency is the slowest API, not their sum. | [call it](https://demo-city-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/?city=Paris&lang=en) |
| [`stock-api/`](stock-api/) | python | An inventory API backed by a **private database**. State survives sleep. | [call it](https://stock-api-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/stats) |
| [`timer/`](timer/) | nodejs24 | A countdown-timer page. The handler returns the HTML; the interactivity runs in the browser. | [open it](https://timer-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/) |

These functions sit at **zero instances** until someone calls them. The first call after a quiet
spell pays a brief cold start; `demo-city` and `demo-dashboard` report their own startup time in
their response, so you can see it rather than take our word for it.

## Deploying an example

1. Create an account on [zerolith.io](https://zerolith.io) and verify your email address.
2. In the dashboard, create a function, pick the runtime, and paste the contents of `main.py` /
   `main.js`.
3. Leave the "Handler" field at its default, `main.handler`.
4. Try it from its page with the "Test the function" button.

The free signup credit easily covers these first steps: an idle function costs nothing.

Everything is also driven through the API or by an agent over the MCP server — see the
[documentation](https://zerolith.io/en/docs).

## The handler contract

A function is **a single file** exposing a handler. It receives a request object and returns the
response.

```python
# main.py — handler: main.handler
def handler(request):
    # request.method   -> "GET", "POST", ...
    # request.path     -> str
    # request.headers  -> dict[str, str]
    # request.query    -> dict[str, str]
    # request.body     -> bytes
    # request.json()   -> parsed JSON body
    name = request.query.get("name", "world")
    return {"message": f"hello, {name}"}
```

Accepted return shapes:

| Return | HTTP response |
|--------|---------------|
| `"text"` | 200 `text/plain` |
| `{"a": 1}` or `[1, 2]` | 200 `application/json` |
| `(404, "not found")` | status + body |
| `(201, body, {"X-My": "hdr"})` | status + body + headers |

In Node.js, same rules with `exports.handler` and an array instead of the tuple.

The runtimes already bundle the common libraries: `requests`, `httpx`, `pydantic`, `PyYAML` on
Python; `axios`, `lodash`, `zod`, `dayjs` on Node.

## Runtimes

The offered ids are `python`, `nodejs20`, `nodejs22`, `nodejs24`, and depending on the deployment
`python313` / `python314`. `python` stays on 3.12 and is never repointed under your feet: newer
lines are distinct ids that you opt into.

The list actually available is whatever `/api/catalog` returns — that is the authority.

## Calling a function

```bash
# private function — API key in the Authorization header
curl -H "Authorization: Bearer $ZEROLITH_KEY" "https://<function-url>?name=neo"

# public function — no authentication
curl "https://<function-url>?name=neo"

# presigned URL — the token is in the URL, until the date you set
curl "https://<function-url>?faas_token=faast_..."
```

Authentication is checked **at the edge**, before your function even wakes: an unauthorized call
costs you nothing.

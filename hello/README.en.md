*[Français](README.md)*

# hello

The smallest handler that works, in both languages. It is also the sample prefilled in the
deploy form.

- [`python/main.py`](python/main.py) — runtime `python`
- [`nodejs/main.js`](nodejs/main.js) — runtime `nodejs24` (or `nodejs20` / `nodejs22`)

Handler: `main.handler` (the default — nothing to change).

## Calling it

```bash
curl "https://<function-url>?name=neo"
# {"message": "hello, neo", "method": "GET"}
```

The `name` parameter is optional and defaults to `world`. Every HTTP method and every path
reaches the handler: `request.method` and `request.path` give them to you.

## Next

Return something other than JSON — the return value decides the response:

```python
return "text"                             # 200 text/plain
return {"a": 1}                           # 200 application/json
return 404, "not found"                   # status + body
return 201, body, {"X-My": "hdr"}         # status + body + headers
```

Every other example in this repo starts from here: [`demo-city`](../demo-city/) adds concurrent
network calls, [`demo-dashboard`](../demo-dashboard/) returns a whole HTML page,
[`stock-api`](../stock-api/) wires a database to it.

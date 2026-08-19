*[Français](README.md)*

# stock-api

A shop inventory API backed by a **private database**: catalogue, item sheet with its history,
stock movements in and out, aggregates.

**Live:** <https://stock-api-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/stats>
(the public instance is **read-only** — writes are disabled so the data stays readable by
everyone)

## What it demonstrates

State survives sleep. The database sleeps alongside the function: at rest neither costs compute
time, only the reserved storage tier is billed. The first call after a quiet spell wakes both and
pays a cold start — and the data is exactly where it was left.

Nothing to configure in the code: once a database is attached to the function, the platform
injects `DATABASE_URL` and `DATABASE_AUTH_TOKEN` into the pod. The token is displayed nowhere,
neither in the UI nor through the API — it is mounted from a write-only secret.

**The design decision that matters:** stock is not a column you increment, but the **sum of a
movement ledger**. Two pods woken in parallel reading 10, each adding 5 and writing 15 instead of
20 is not a textbook case on a platform that starts instances when traffic rises: it is the
default behaviour. A ledger does not have that problem, since every write is an insert. The
history comes free as a bonus. The trade-off is aggregating on read — negligible at this scale,
and indexed.

## Routes

```
GET  /                     this message and the aggregates
GET  /products             catalogue + current stock  (?category=  ?low_stock=1)
GET  /products/<sku>       item sheet + last 20 movements
POST /products             {sku, name, category, price_cents, reorder_level, quantity}
POST /movements            {sku, delta, reason}   negative delta = outgoing
GET  /stats                aggregates and stock value
```

```bash
curl "https://<function-url>/stats"
curl "https://<function-url>/products?low_stock=1"
```

## Deploying

Runtime `python`, handler `main.handler`. The libSQL client already ships with the runtime.

1. Provision a database from the app, then **attach it** to the function. The two environment
   variables then appear in the pod without you writing them.
2. Lay down the schema with [`migrator/main.py`](migrator/main.py): the database server cannot
   call your functions, so migrations are explicit. Deploy the migrator as a private function,
   designate it as the database's **migrator**, then trigger it from the UI, the API or an MCP
   agent.
3. Remove `STOCK_READ_ONLY` (or set it to `0`) to get the full write API.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | injected | address of the attached database |
| `DATABASE_AUTH_TOKEN` | injected | token, mounted from a write-only secret |
| `STOCK_READ_ONLY` | `1` | refuses writes; set to `0` for the full API |

### The schema and the migrator function

[`migrator/main.py`](migrator/main.py) lays down the schema this API expects:

```
products(id, sku, name, category, price_cents, reorder_level, created_at)
movements(id, product_id, delta, reason, created_at)
```

Deploy it as a **separate private function** (it is DDL — it has no business on an open URL),
attach the same database to it, designate it as the migrator, then trigger it. It is replayable:
`CREATE TABLE IF NOT EXISTS` throughout, and the demo catalogue is only seeded if the `products`
table is empty. Re-run against a database already in use, it duplicates nothing and does not
touch real stock.

The `IF NOT EXISTS` is not laziness: the migration is triggered by hand, so it must be replayable
without consequence — if only because you no longer remember whether it ran.

The full reasoning about the movement ledger is developed in the article
["A stateful API"](https://zerolith.io/en/blog/stateful-api-database) — the article gives a
deliberately simplified version of the schema (without `category` or `reorder_level`); the one in
this repo is the complete version, aligned with the code.

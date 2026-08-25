*[Français](README.md)*

# quiz — hiding a cold start behind a game

A ten-question quiz about serverless. While you answer it, the database wakes up backstage — and
by the time your score needs saving, it has been up for a while.

**Live:** <https://jeu-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/>
(and <https://jeu-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/?prewarm=0> to play the
same game **without** the trick — that's the comparison, playable)

> The handlers' own docstrings and comments are in French, as is the platform's primary
> documentation. The page itself is in French too. The code needs no translation.

## What it shows

A function starts quickly. A database does not: it also has to restore its state from object
storage. On this platform, measured the day this example was written, a cold Python function
answers in ~2 s while waking a database takes ~14. That gap is what turns a demo into a frozen
screen.

That cold start is not removed here, nor shortened by a millisecond. It is **moved off the path
where someone is waiting** — and it takes no cache, no queue and no instance kept warm. It takes
**splitting the work across two functions**:

| Function | Database attached | Role |
|----------|-------------------|------|
| `jeu` (this directory, [`main.py`](main.py)) | **none** | renders the page and nothing else. It has no `DATABASE_URL` and would not know what to do with one. |
| `quiz-api` ([`api/main.py`](api/main.py)) | yes | the half that talks to the database: wake, score write, aggregates. |

On the page's first paint, it calls `quiz-api/wake` **without awaiting the response**. That call
wakes the database pod and pays for its restore while the player reads the rules and answers the
questions. At the end of the game, ~45 s later, the write takes a few milliseconds.

The split is what makes the trick possible. Were the page and the database in one function, the
visitor would wait for the wake before seeing anything — which is exactly what `?prewarm=0`
stages again.

## The demo collects its own evidence

Every game records three columns that have nothing to do with the quiz: whether the page had
prewarmed the database (`prewarm`), how long the wake took (`wake_ms`), and how long the final
write took **as seen from the browser** (`submit_ms`). `GET /stats` turns those into a comparison
of the two regimes across all players.

Two details paid for at design time rather than after:

**`submit_ms` arrives on a second request.** A browser cannot know how long a request took before
it finishes, and that duration is precisely what we want to publish. The page measures it, then
posts the value to `POST /latency` — tiny, and against a database that is warm by then.

**That write happens once per game** (`WHERE submit_ms IS NULL`). Without the clause, anyone could
rewrite any game's latency and move the median the page displays. The route answers
`{"recorded": false}` when it refused — saying "recorded" about a refused write would be a
response that lies.

## `quiz-api` routes

```
GET  /wake      a SELECT 1 and nothing else. The point is not to get an answer but to
                make the pod exist. Returns how long that took.
POST /score     {score, answers[10], duration_ms, prewarm, wake_ms} -> {game_id, rank}
POST /latency   {game_id, submit_ms} -> {recorded}   one write per game
GET  /stats     the aggregates, including write latency with and without prewarming
```

The score is computed by the browser. That is deliberate: grading server-side would mean
duplicating the question bank across both functions, and the subject here is latency, not
cheating. So the API validates the **shape** of what arrives — lengths, bounds, types, the score
agreeing with the answers — so a malformed submission cannot pollute the aggregates. A body that
is not JSON is refused with a 400, before the database is even opened.

## Deploying

Three functions, one database. Runtime `python`, handler `main.handler` throughout.

1. **`quiz-migrate`** — [`migrator/main.py`](migrator/main.py), as a **private** function. It is
   DDL; it has no business on an open URL.
2. Create the database, attach it to the migrator, designate it as the database's **migrator**,
   then trigger it. It is replayable: `CREATE TABLE IF NOT EXISTS` throughout.
3. **`quiz-api`** — [`api/main.py`](api/main.py), **public**, same database attached.
4. **`jeu`** — [`main.py`](main.py), **public**, **no database**. That is the whole point: do not
   attach one.

The page derives its API's URL from its own `Host`: `jeu-fn-<id>` and `quiz-api-fn-<id>` differ
only in their first segment. Redeploy the pair under another account and it finds itself.
`QUIZ_API_URL` takes over if you name your functions differently.

| Variable | Default | Role |
|----------|---------|------|
| `DATABASE_URL` | injected | the attached database's address (`quiz-api` and the migrator only) |
| `DATABASE_AUTH_TOKEN` | injected | token, mounted from a write-only secret |
| `QUIZ_API_URL` | derived from `Host` | on `jeu`, when the two functions do not share a suffix |

### The CORS preflight never reaches your handler

The two functions have different origins, so the API returns CORS headers. That is not enough: a
`POST` in `application/json` is not a "simple" request, so the browser first sends an `OPTIONS`
preflight — and the runtime declares its routes **without `OPTIONS`**. Flask answers it itself, with
an empty `200` and not one `Access-Control-*`. The browser blocks the `POST` that follows, the page
shows a write error, and the API is perfectly fine.

The tell: `GET /wake` works (no preflight on a simple GET) and only the write fails. The workaround
is in [`main.py`](main.py) — post as `text/plain;charset=UTF-8`, which is a simple request. Nothing
changes server-side; `request.json()` parses the bytes it received without looking at the
`Content-Type`.

[`api/main.py`](api/main.py) keeps its `OPTIONS` branch, annotated as unreachable today.

### A trap that cost a 500 in production

`request.headers` is a **plain dictionary** that preserves the original casing: the key is `Host`,
not `host`. A `request.headers.get("host")` returns `None` without raising, the page answers 500,
and a test bench that builds its headers in lowercase stays green. [`main.py`](main.py)
normalises the casing before looking. If you read a header in a handler, do the same.

## The schema

```
games(id, score, duration_ms, prewarm, wake_ms, submit_ms, created_at)
answers(game_id, q, correct)
```

`answers` exists for one thing: to say "the question everybody gets wrong". That aggregate only
means something because every player writes to the same database — the kind of thing a stateless
function cannot produce.

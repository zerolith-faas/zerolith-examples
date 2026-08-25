"""zerolith · schéma du quiz « Serverless ou pas ? ».

Fonction migratrice de la base `quiz` : elle pose le schéma et rien d'autre. Elle
est désignée comme migrateur de la base (voir la section « Bases de données » de la
documentation) et n'est jamais appelée par sa route publique — la plateforme
l'invoque par le chemin interne signé, à la demande.

Idempotente : chaque instruction est un CREATE ... IF NOT EXISTS, donc la rejouer
ne coûte rien et ne détruit rien.

Ce que l'on garde d'une partie, et pourquoi
    games   une ligne par partie terminée. Les trois colonnes qui portent la
            démonstration sont `prewarm`, `wake_ms` et `submit_ms` : elles
            enregistrent, pour chaque joueur, si la page avait préchauffé la base
            et combien de temps l'écriture a réellement pris de son point de vue.
            C'est le jeu de données de l'article, collecté par l'article lui-même.
    answers une ligne par question répondue, pour pouvoir dire « la question que
            tout le monde rate » — un agrégat qui n'a de sens qu'avec une base
            partagée entre tous les visiteurs.
"""

import os

import libsql_client

DDL = [
    """
    CREATE TABLE IF NOT EXISTS games (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        score       INTEGER NOT NULL,
        duration_ms INTEGER NOT NULL,
        prewarm     INTEGER NOT NULL,
        wake_ms     INTEGER,
        submit_ms   INTEGER,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS answers (
        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
        q       INTEGER NOT NULL,
        correct INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_games_created ON games (created_at)",
    "CREATE INDEX IF NOT EXISTS idx_games_prewarm ON games (prewarm)",
    "CREATE INDEX IF NOT EXISTS idx_answers_q ON answers (q)",
]


def handler(request):
    db = libsql_client.create_client_sync(
        url=os.environ["DATABASE_URL"],
        auth_token=os.environ["DATABASE_AUTH_TOKEN"],
    )
    try:
        for statement in DDL:
            db.execute(statement)
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).rows
        return {"migrated": True, "tables": [t[0] for t in tables]}
    finally:
        db.close()

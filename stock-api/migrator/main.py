"""zerolith · fonction migratrice de l'exemple « API de stock ».

Le serveur de base ne peut pas appeler vos fonctions : les migrations sont donc explicites.
Désignez CETTE fonction comme migrateur de la base, puis déclenchez-la à la demande depuis
l'interface, l'API ou un agent MCP. Elle pose le schéma que `stock-api` attend, puis remplit
un petit catalogue de démonstration si la base est encore vide.

Elle est appelée en POST sur `/`, sans corps, par l'invocateur interne de la plateforme —
elle ne lit donc aucun paramètre de requête et ne doit dépendre d'aucun.

Deux propriétés qui comptent plus que le SQL lui-même :

  • Elle est REJOUABLE. Une migration déclenchée à la main doit pouvoir être relancée sans
    conséquence, ne serait-ce que parce qu'on ne sait plus si elle est passée. D'où le
    `IF NOT EXISTS` partout, et un amorçage conditionné à une table vide.

  • Elle ne détruit rien. Aucun DROP, aucun DELETE : une fonction déclenchable d'un clic
    depuis l'interface n'a pas à pouvoir vider un inventaire.

Déployez-la en PRIVÉ (jamais publique) : c'est du DDL, ça n'a rien à faire sur une URL
ouverte. Attachez-lui la même base que `stock-api`.
"""

import os

import libsql_client

# Le schéma que stock-api/main.py lit et écrit, à la colonne près.
#
# `products.created_at` n'est jamais relu par l'API : il est là parce qu'une ligne sans date
# de création est un regret qu'on n'a qu'une fois, et qu'ajouter la colonne après coup sur des
# lignes existantes coûte plus cher que de la poser tout de suite.
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS products (
         id            INTEGER PRIMARY KEY,
         sku           TEXT    NOT NULL UNIQUE,
         name          TEXT    NOT NULL,
         category      TEXT    NOT NULL DEFAULT 'divers',
         price_cents   INTEGER NOT NULL DEFAULT 0,
         reorder_level INTEGER NOT NULL DEFAULT 0,
         created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
       )""",
    # Le stock n'est PAS une colonne de products : c'est la somme de ce registre. Chaque
    # entrée ou sortie est une INSERTION, jamais une mise à jour — deux pods réveillés en
    # parallèle ne peuvent donc pas s'écraser mutuellement.
    """CREATE TABLE IF NOT EXISTS movements (
         id         INTEGER PRIMARY KEY,
         product_id INTEGER NOT NULL REFERENCES products(id),
         delta      INTEGER NOT NULL,
         reason     TEXT    NOT NULL,
         created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
       )""",
    # L'index qui porte tout le reste : chaque lecture de stock agrège les mouvements d'un
    # produit, et /stats les agrège pour tout le catalogue.
    "CREATE INDEX IF NOT EXISTS movements_product ON movements(product_id)",
]

# Catalogue d'amorçage : (sku, nom, catégorie, prix en centimes, seuil de réappro, quantité).
# Deux références sont volontairement sous leur seuil, pour que `/products?low_stock=1` et
# l'agrégat `references_a_reapprovisionner` renvoient autre chose que du vide.
SEED = [
    ("CAF-001", "Café en grains 1 kg", "épicerie", 1890, 10, 42),
    ("CAF-002", "Café moulu 250 g", "épicerie", 640, 20, 8),
    ("THE-010", "Thé vert sencha 100 g", "épicerie", 1250, 8, 15),
    ("MUG-100", "Mug isotherme 400 ml", "accessoires", 2400, 5, 3),
    ("FIL-200", "Filtres papier n°4 (100)", "accessoires", 380, 12, 60),
    ("MOU-300", "Moulin à café manuel", "matériel", 4900, 3, 7),
]


def _client():
    return libsql_client.create_client_sync(
        url=os.environ["DATABASE_URL"],
        auth_token=os.environ["DATABASE_AUTH_TOKEN"],
    )


def _seed(db):
    """Remplit le catalogue, mais seulement si la base est encore vierge.

    C'est cette condition qui rend la fonction rejouable : relancée sur une base déjà
    utilisée, elle ne duplique rien et ne touche pas au stock réel.
    """
    if db.execute("SELECT COUNT(*) FROM products").rows[0][0]:
        return 0

    for sku, name, category, price_cents, reorder, qty in SEED:
        db.execute(
            "INSERT INTO products (sku, name, category, price_cents, reorder_level) "
            "VALUES (?, ?, ?, ?, ?)",
            [sku, name, category, price_cents, reorder],
        )
        if qty:
            pid = db.execute("SELECT id FROM products WHERE sku = ?", [sku]).rows[0][0]
            db.execute(
                "INSERT INTO movements (product_id, delta, reason) "
                "VALUES (?, ?, 'stock initial')",
                [pid, qty],
            )
    return len(SEED)


def handler(request):
    db = _client()
    try:
        for statement in SCHEMA:
            db.execute(statement)
        seeded = _seed(db)
        products = db.execute("SELECT COUNT(*) FROM products").rows[0][0]
        movements = db.execute("SELECT COUNT(*) FROM movements").rows[0][0]
    finally:
        db.close()

    return {
        "ok": True,
        "statements": len(SCHEMA),
        "seeded": seeded,
        "products": int(products),
        "movements": int(movements),
    }

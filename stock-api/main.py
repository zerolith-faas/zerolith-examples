"""zerolith · exemple « API de stock », branchée sur une base de données privée.

Un inventaire de magasin servi par une fonction : consultation du catalogue, fiche
article avec son historique, entrées et sorties, et quelques agrégats. Les données
vivent dans une base privée attachée à la fonction — SQLite en réseau, répliquée en
continu vers un stockage objet.

Vous n'avez rien à configurer : quand une base est attachée, la plateforme injecte
DATABASE_URL et DATABASE_AUTH_TOKEN dans le pod. Le jeton n'est jamais affiché nulle
part, ni dans l'interface ni dans l'API — il est monté depuis un secret en écriture
seule, et les identifiants du stockage objet ne quittent jamais le serveur de base.

La base se met en veille comme la fonction : au repos, ni l'une ni l'autre ne coûte
de temps de calcul, seul le palier de stockage réservé reste facturé. Le premier appel
après une période creuse réveille les deux et paie un démarrage à froid.

Le stock n'est PAS une colonne que l'on incrémente, mais la somme d'un registre de
mouvements. Un registre donne l'historique gratuitement et évite que deux écritures
simultanées s'écrasent — la contrepartie étant une agrégation à la lecture, négligeable
à cette échelle et indexée.

Le schéma est posé par une fonction compagnon désignée comme migrateur de la base
(voir la section « Bases de données » de la documentation) :

    products(id, sku, name, category, price_cents, reorder_level, created_at)
    movements(id, product_id, delta, reason, created_at)

Routes
    GET  /                     ce message et les agrégats
    GET  /products             catalogue + stock courant  (?category=  ?low_stock=1)
    GET  /products/<sku>       fiche article + 20 derniers mouvements
    POST /products             {sku, name, category, price_cents, reorder_level, quantity}
    POST /movements            {sku, delta, reason}   delta négatif = sortie
    GET  /stats                agrégats et valeur du stock
"""

import os

import libsql_client

# Cette instance est une vitrine publique : les écritures y sont désactivées pour que
# les données restent lisibles par tous. Retirez cette variable d'environnement (ou
# passez-la à "0") pour obtenir l'API complète sur votre propre déploiement.
READ_ONLY = os.environ.get("STOCK_READ_ONLY", "1").lower() in ("1", "true", "yes")

# La fonction est appelée depuis un navigateur : sans cet en-tête, le navigateur refuse
# de livrer la réponse à la page. Sans risque ici — la fonction est publique et ne lit
# aucun cookie, elle n'expose donc rien de plus qu'un appel anonyme.
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "no-store",
}

# Le stock courant se calcule à la lecture : une jointure sur le registre de mouvements.
STOCK_SELECT = """
    SELECT p.id, p.sku, p.name, p.category, p.price_cents, p.reorder_level,
           CAST(COALESCE(SUM(m.delta), 0) AS INTEGER) AS qty
      FROM products p
      LEFT JOIN movements m ON m.product_id = p.id
"""


def _client():
    """Ouvre une connexion à la base privée attachée à cette fonction.

    Le client libSQL parle HTTP : c'est ce qui permet à la base de dormir et de se
    réveiller à la demande, exactement comme la fonction.
    """
    return libsql_client.create_client_sync(
        url=os.environ["DATABASE_URL"],
        auth_token=os.environ["DATABASE_AUTH_TOKEN"],
    )


def _product_row(row):
    qty, reorder = int(row[6]), int(row[5])
    return {
        "sku": row[1],
        "name": row[2],
        "category": row[3],
        "price_eur": round(int(row[4]) / 100, 2),
        "quantity": qty,
        "reorder_level": reorder,
        "low_stock": qty <= reorder,
    }


def _list_products(db, query):
    where, params = [], []
    if query.get("category"):
        where.append("p.category = ?")
        params.append(query["category"])
    sql = STOCK_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY p.id ORDER BY p.category, p.sku"

    items = [_product_row(r) for r in db.execute(sql, params).rows]
    if query.get("low_stock") in ("1", "true", "yes"):
        items = [i for i in items if i["low_stock"]]
    return {"count": len(items), "products": items}


def _get_product(db, sku):
    rows = db.execute(STOCK_SELECT + " WHERE p.sku = ? GROUP BY p.id", [sku]).rows
    if not rows:
        return 404, {"error": "sku inconnu", "sku": sku}
    product = _product_row(rows[0])
    movements = db.execute(
        "SELECT delta, reason, created_at FROM movements WHERE product_id = ? "
        "ORDER BY id DESC LIMIT 20",
        [rows[0][0]],
    ).rows
    product["movements"] = [
        {"delta": int(m[0]), "reason": m[1], "at": m[2]} for m in movements
    ]
    return 200, product


def _create_product(db, body):
    sku = (body.get("sku") or "").strip()
    name = (body.get("name") or "").strip()
    if not sku or not name:
        return 400, {"error": "sku et name sont obligatoires"}

    if db.execute("SELECT COUNT(*) FROM products WHERE sku = ?", [sku]).rows[0][0]:
        return 409, {"error": "sku deja utilise", "sku": sku}

    db.execute(
        "INSERT INTO products (sku, name, category, price_cents, reorder_level) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            sku,
            name,
            body.get("category") or "divers",
            int(body.get("price_cents") or 0),
            int(body.get("reorder_level") or 0),
        ],
    )
    pid = db.execute("SELECT id FROM products WHERE sku = ?", [sku]).rows[0][0]

    qty = int(body.get("quantity") or 0)
    if qty:
        db.execute(
            "INSERT INTO movements (product_id, delta, reason) VALUES (?, ?, 'reception')",
            [pid, qty],
        )
    return 201, {"created": sku, "quantity": qty}


def _move(db, body):
    """Enregistre une entrée (delta positif) ou une sortie (delta négatif)."""
    sku = (body.get("sku") or "").strip()
    try:
        delta = int(body.get("delta"))
    except (TypeError, ValueError):
        return 400, {"error": "delta doit etre un entier non nul"}
    if not sku or delta == 0:
        return 400, {"error": "sku et delta (non nul) sont obligatoires"}

    rows = db.execute("SELECT id FROM products WHERE sku = ?", [sku]).rows
    if not rows:
        return 404, {"error": "sku inconnu", "sku": sku}
    pid = rows[0][0]

    def stock():
        return int(
            db.execute(
                "SELECT COALESCE(SUM(delta), 0) FROM movements WHERE product_id = ?", [pid]
            ).rows[0][0]
        )

    before = stock()
    if before + delta < 0:
        return 409, {
            "error": "stock insuffisant",
            "sku": sku,
            "quantity": before,
            "requested": delta,
        }

    # Le contrôle est rejoué dans le SQL lui-même : entre la lecture ci-dessus et cette
    # écriture, une autre requête a pu vider le stock. La condition WHERE rend l'insertion
    # conditionnelle côté base, ce qui règle la concurrence sans verrou applicatif.
    db.execute(
        "INSERT INTO movements (product_id, delta, reason) "
        "SELECT ?, ?, ? WHERE (SELECT COALESCE(SUM(delta), 0) FROM movements "
        "WHERE product_id = ?) + ? >= 0",
        [pid, delta, (body.get("reason") or "manual")[:40], pid, delta],
    )

    after = stock()
    if after == before:
        return 409, {"error": "stock insuffisant (concurrence)", "sku": sku, "quantity": after}
    return 200, {"sku": sku, "delta": delta, "quantity": after}


def _stats(db):
    row = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(qty), 0), COALESCE(SUM(qty * price_cents), 0), "
        "COALESCE(SUM(CASE WHEN qty <= reorder_level THEN 1 ELSE 0 END), 0) "
        "FROM (" + STOCK_SELECT + " GROUP BY p.id)"
    ).rows[0]
    by_cat = db.execute(
        "SELECT category, COUNT(*), COALESCE(SUM(qty), 0) FROM ("
        + STOCK_SELECT
        + " GROUP BY p.id) GROUP BY category ORDER BY category"
    ).rows
    movements = db.execute("SELECT COUNT(*) FROM movements").rows[0][0]
    return {
        "references": int(row[0]),
        "articles_en_stock": int(row[1]),
        "valeur_stock_eur": round(int(row[2]) / 100, 2),
        "references_a_reapprovisionner": int(row[3]),
        "mouvements_enregistres": int(movements),
        "par_categorie": [
            {"category": c[0], "references": int(c[1]), "quantity": int(c[2])} for c in by_cat
        ],
    }


def handler(request):
    parts = [p for p in request.path.split("/") if p]
    method = request.method.upper()

    if READ_ONLY and method not in ("GET", "HEAD"):
        return 403, {"error": "instance de démonstration en lecture seule"}, CORS

    db = _client()
    try:
        if not parts:
            return 200, {
                "service": "stock-api",
                "database": "base privée attachée (libSQL, répliquée)",
                "read_only": READ_ONLY,
                "routes": [
                    "GET  /products?category=&low_stock=1",
                    "GET  /products/<sku>",
                    "POST /products  {sku,name,category,price_cents,reorder_level,quantity}",
                    "POST /movements {sku,delta,reason}",
                    "GET  /stats",
                ],
                "stats": _stats(db),
            }, CORS

        if parts[0] == "products":
            if len(parts) == 1:
                if method == "GET":
                    return 200, _list_products(db, request.query), CORS
                if method == "POST":
                    status, body = _create_product(db, request.json() or {})
                    return status, body, CORS
                return 405, {"error": "methode non autorisee"}, CORS
            if method == "GET":
                status, body = _get_product(db, parts[1])
                return status, body, CORS
            return 405, {"error": "methode non autorisee"}, CORS

        if parts[0] == "movements" and len(parts) == 1:
            if method == "POST":
                status, body = _move(db, request.json() or {})
                return status, body, CORS
            return 405, {"error": "methode non autorisee"}, CORS

        if parts[0] == "stats" and method == "GET":
            return 200, _stats(db), CORS

        return 404, {"error": "route inconnue", "path": request.path}, CORS
    finally:
        db.close()

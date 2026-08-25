"""zerolith · l'API du quiz « Serverless ou pas ? » — la moitié qui parle à la base.

Cette fonction est la SEULE des deux à avoir une base attachée. Sa jumelle `jeu`
sert la page et ne connaît aucune base : c'est ce découpage qui permet de masquer
le réveil de la base derrière le temps de jeu.

Trois routes, et l'ordre dans lequel la page les appelle est tout le sujet :

    GET  /wake    appelée dès la première image de la page, sans attendre. Fait un
                  SELECT 1 et rien d'autre. Sur une base endormie cet appel prend
                  une dizaine de secondes — démarrage à froid du pod plus restauration
                  depuis le stockage objet — mais personne ne l'attend : le joueur
                  est en train de lire les règles.
    POST /score   appelée à la fin de la partie, ~45 s plus tard. La base est chaude
                  depuis longtemps, l'écriture prend quelques millisecondes.
    POST /latency une deuxième requête, minuscule, qui vient dire à la base combien
                  de temps la PRÉCÉDENTE avait pris. Ce détour est nécessaire : un
                  navigateur ne peut pas mesurer la durée d'une requête avant de
                  l'avoir terminée, et c'est précisément cette durée que la
                  démonstration veut publier. Écriture unique par partie.
    GET  /stats   les agrégats de tous les joueurs, y compris la comparaison des
                  latences de soumission avec et sans préchauffage.

Le score est calculé par le navigateur, pas ici. C'est un choix assumé et non une
négligence : corriger côté serveur imposerait de dupliquer la banque de questions
dans les deux fonctions, alors que le sujet de cette démonstration est la latence,
pas la triche. On valide donc la FORME de ce qui arrive (bornes, longueurs, types)
et on refuse tout le reste, pour qu'un envoi malformé ne pollue pas les agrégats.
"""

import os
import time

import libsql_client

# Le nombre de questions de la banque servie par la fonction `jeu`. Les deux doivent
# rester d'accord : c'est la seule chose que ces deux fonctions partagent.
QUESTIONS = 10

# La page est servie par une autre fonction, donc une autre origine. Sans cet en-tête
# le navigateur refuse de livrer la réponse. Sans risque : la fonction est publique,
# ne lit aucun cookie et n'expose rien de plus qu'un appel anonyme.
#
# ATTENTION, ces en-têtes ne suffisent QUE pour les requêtes « simples » au sens CORS.
# Un POST en `application/json` déclenche d'abord un OPTIONS de contrôle préalable, et
# le runtime déclare ses routes SANS OPTIONS : Flask y répond lui-même, avec un 200
# vide et aucun en-tête Access-Control-*. Le navigateur bloque alors le POST qui suit.
# C'est pour ça que la page poste en `text/plain` — voir le commentaire dans `jeu`.
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Cache-Control": "no-store",
}


def _client():
    return libsql_client.create_client_sync(
        url=os.environ["DATABASE_URL"],
        auth_token=os.environ["DATABASE_AUTH_TOKEN"],
    )


def _wake():
    """Réveille la base et rend le temps que ça a pris, vu du serveur.

    Aucune donnée n'est lue : le but n'est pas d'obtenir une réponse mais de faire
    exister le pod. Si la requête a mis plus d'une seconde, c'est qu'elle a payé un
    démarrage — une base déjà debout répond en quelques millisecondes.
    """
    started = time.monotonic()
    db = _client()
    try:
        db.execute("SELECT 1")
    finally:
        db.close()
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {"ready": True, "query_ms": elapsed_ms, "was_cold": elapsed_ms > 1000}


def _body(request):
    """Le corps JSON de la requete, ou None si ce n'en est pas.

    `request.json()` leve sur un corps tronque, et un handler qui leve rend 500.
    Mesure sur la fonction deployee avant ce correctif : `POST /score` avec la
    charge `{"score":` repondait « internal handler error » en 500 — une erreur de
    SERVEUR annoncee pour une faute de CLIENT, sur une route publique. Le refus
    doit etre un 400, et il doit avoir lieu avant d'ouvrir la base.

    On analyse les OCTETS recus sans consulter le Content-Type, ce qui est aussi ce
    qui permet a la page de poster en `text/plain` pour eviter le controle prealable.
    """
    try:
        return request.json() or {}
    except Exception:
        return None


def _int(value, low, high, default=None):
    """Un entier dans ses bornes, ou `default`. Tout le reste est refusé."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if low <= n <= high else default


def _save(db, body):
    answers = body.get("answers")
    if not isinstance(answers, list) or len(answers) != QUESTIONS:
        return 400, {"error": f"answers doit etre une liste de {QUESTIONS} booleens"}
    correct = [1 if a else 0 for a in answers]

    score = _int(body.get("score"), 0, QUESTIONS)
    duration_ms = _int(body.get("duration_ms"), 0, 3_600_000)
    if score is None or duration_ms is None:
        return 400, {"error": "score et duration_ms sont obligatoires et bornes"}
    if score != sum(correct):
        return 400, {"error": "le score ne correspond pas aux reponses"}

    # Bornées elles aussi : ce sont des mesures faites par le navigateur, donc des
    # valeurs qu'un client choisit. Une seule ligne aberrante décalerait la médiane
    # que l'article cite.
    prewarm = 1 if body.get("prewarm") else 0
    wake_ms = _int(body.get("wake_ms"), 0, 120_000)

    # submit_ms reste NULL ici : c'est la durée de CETTE requête, que le client ne
    # connaîtra qu'une fois la réponse reçue. Il la renverra par /latency.
    row = db.execute(
        "INSERT INTO games (score, duration_ms, prewarm, wake_ms) "
        "VALUES (?, ?, ?, ?) RETURNING id",
        [score, duration_ms, prewarm, wake_ms],
    ).rows
    game_id = int(row[0][0])

    # Une seule instruction pour les dix réponses : dix aller-retours pour dix entiers
    # seraient dix fois la latence réseau pour rien.
    values = ", ".join(["(?, ?, ?)"] * QUESTIONS)
    params = []
    for index, ok in enumerate(correct):
        params += [game_id, index, ok]
    db.execute(f"INSERT INTO answers (game_id, q, correct) VALUES {values}", params)

    return 200, {"game_id": game_id, "score": score, "rank": _rank(db, score)}


def _latency(db, body):
    """Enregistre, une seule fois, la latence que le navigateur a mesurée sur /score.

    Le `submit_ms IS NULL` n'est pas une précaution de style : sans lui, n'importe
    qui pourrait réécrire la latence de n'importe quelle partie et déplacer la
    médiane que cette page affiche. Une partie ne peut donc être chronométrée qu'une
    fois, par celui qui vient de la jouer.
    """
    game_id = _int(body.get("game_id"), 1, 2**62)
    submit_ms = _int(body.get("submit_ms"), 0, 120_000)
    if game_id is None or submit_ms is None:
        return 400, {"error": "game_id et submit_ms sont obligatoires et bornes"}

    result = db.execute(
        "UPDATE games SET submit_ms = ? WHERE id = ? AND submit_ms IS NULL",
        [submit_ms, game_id],
    )
    # Dire « recorded » quand la clause `IS NULL` a justement refuse l'ecriture
    # serait un mensonge poli : la reponse rend ce qui s'est reellement passe.
    affected = getattr(result, "rows_affected", None)
    return 200, {"recorded": True if affected is None else affected > 0}


def _rank(db, score):
    """Le rang du joueur, en pourcentage de parties qu'il bat."""
    row = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(CASE WHEN score < ? THEN 1 ELSE 0 END), 0) "
        "FROM games",
        [score],
    ).rows[0]
    total, below = int(row[0]), int(row[1])
    return {
        "games": total,
        "better_than_percent": round(100 * below / total) if total else None,
    }


def _stats(db):
    row = db.execute(
        "SELECT COUNT(*), COALESCE(AVG(score), 0), COALESCE(AVG(duration_ms), 0) FROM games"
    ).rows[0]

    # La question la plus ratée : l'agrégat qui n'existe que parce que tous les
    # joueurs écrivent dans la même base.
    hardest = db.execute(
        "SELECT q, COUNT(*), COALESCE(SUM(correct), 0) FROM answers "
        "GROUP BY q ORDER BY (CAST(SUM(correct) AS REAL) / COUNT(*)) ASC LIMIT 1"
    ).rows

    # Le coeur de la demonstration : la latence de l'ecriture finale, vue du
    # navigateur, selon que la page avait prechauffe la base ou non.
    latency = db.execute(
        "SELECT prewarm, COUNT(*), COALESCE(AVG(submit_ms), 0), "
        "       COALESCE(MIN(submit_ms), 0), COALESCE(MAX(submit_ms), 0) "
        "FROM games WHERE submit_ms IS NOT NULL GROUP BY prewarm"
    ).rows

    by_prewarm = {}
    for r in latency:
        by_prewarm["avec_prechauffage" if int(r[0]) else "sans_prechauffage"] = {
            "parties": int(r[1]),
            "soumission_ms_moyenne": round(float(r[2])),
            "soumission_ms_min": int(r[3]),
            "soumission_ms_max": int(r[4]),
        }

    stats = {
        "parties": int(row[0]),
        "score_moyen": round(float(row[1]), 2),
        "duree_moyenne_s": round(float(row[2]) / 1000, 1),
        "latence_de_soumission": by_prewarm,
    }
    if hardest:
        total, ok = int(hardest[0][1]), int(hardest[0][2])
        stats["question_la_plus_ratee"] = {
            "q": int(hardest[0][0]),
            "reussite_percent": round(100 * ok / total) if total else None,
        }
    return stats


def handler(request):
    method = request.method.upper()
    # ATTENTION : cette branche ne s'execute pas aujourd'hui. Le runtime declare ses
    # routes sans OPTIONS, donc Flask repond lui-meme au controle prealable CORS,
    # avec un 200 vide et SANS le moindre en-tete Access-Control-*. C'est pourquoi
    # la page poste en `text/plain` : une requete « simple » n'a pas de controle
    # prealable. On garde la branche pour le jour ou le runtime passera OPTIONS au
    # handler — elle sera juste, et elle ne nuit pas en attendant.
    if method == "OPTIONS":
        return 204, b"", CORS

    parts = [p for p in request.path.split("/") if p]
    route = parts[0] if parts else ""

    # Le réveil n'ouvre volontairement PAS la connexion via le même chemin que les
    # autres routes : il doit rester la requête la plus pauvre possible.
    if route == "wake" and method == "GET":
        return 200, _wake(), CORS

    if route == "" and method == "GET":
        return 200, {
            "service": "quiz-api",
            "role": "la moitie qui parle a la base — la page est servie par `jeu`",
            "routes": ["GET /wake", "POST /score", "POST /latency", "GET /stats"],
        }, CORS

    if route not in ("score", "stats", "latency"):
        return 404, {"error": "route inconnue", "path": request.path}, CORS

    db = _client()
    try:
        if route == "stats" and method == "GET":
            return 200, _stats(db), CORS
        if method == "POST" and route in ("score", "latency"):
            body = _body(request)
            if body is None:
                return 400, {"error": "corps JSON invalide"}, CORS
            handle = _save if route == "score" else _latency
            status, payload = handle(db, body)
            return status, payload, CORS
        return 405, {"error": "methode non autorisee"}, CORS
    finally:
        db.close()

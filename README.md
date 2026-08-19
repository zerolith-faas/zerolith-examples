*[English](README.en.md)*

# zerolith-examples

Fonctions d'exemple prêtes à déployer sur [zerolith](https://zerolith.io), la plateforme
Functions-as-a-Service en scale-to-zero.

Chaque dossier contient un fichier unique — le handler — que vous pouvez copier tel quel dans
le formulaire de déploiement. Les quatre exemples de la galerie sont le **code réellement en
production** derrière les URLs publiques listées ci-dessous : ce que vous lisez ici est ce qui
répond quand vous appelez.

## Les exemples

| Dossier | Runtime | Ce que ça fait | En direct |
|---------|---------|----------------|-----------|
| [`hello/`](hello/) | python · nodejs24 | Le plus petit handler possible, dans les deux langages. Le point de départ. | — |
| [`demo-dashboard/`](demo-dashboard/) | python | Un tableau de bord météo qui rend une **page HTML complète**, SVG dessiné côté serveur. Ni bundler, ni étape de build, ni écran de chargement. | [appeler](https://demo-dashboard-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/?city=Paris) |
| [`demo-city/`](demo-city/) | python | Un agrégateur d'API : un géocodage puis trois appels **concurrents** fusionnés en une réponse JSON. La latence est celle de l'API la plus lente, pas leur somme. | [appeler](https://demo-city-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/?city=Paris) |
| [`stock-api/`](stock-api/) | python | Une API d'inventaire adossée à une **base de données privée**. L'état survit à la mise en veille. | [appeler](https://stock-api-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/stats) |
| [`timer/`](timer/) | nodejs24 | Une page de compte à rebours. Le handler renvoie le HTML ; l'interactivité tourne dans le navigateur. | [ouvrir](https://timer-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/) |

Ces fonctions sont à **zéro instance** tant que personne ne les appelle. Le premier appel après
une période creuse paie un démarrage à froid de quelques instants ; `demo-city` et
`demo-dashboard` exposent d'ailleurs leur propre temps de démarrage dans leur réponse, pour que
vous puissiez le constater plutôt que nous croire.

## Déployer un exemple

1. Créez un compte sur [zerolith.io](https://zerolith.io) et vérifiez votre adresse e-mail.
2. Dans le tableau de bord, créez une fonction, choisissez le runtime, et collez le contenu du
   fichier `main.py` / `main.js`.
3. Laissez le champ « Handler » sur sa valeur par défaut, `main.handler`.
4. Testez-la depuis sa page avec le bouton « Tester la fonction ».

Le crédit offert à l'inscription couvre largement ces premiers pas : une fonction au repos ne
coûte rien.

Tout se pilote aussi par l'API ou par un agent via le serveur MCP — voir la
[documentation](https://zerolith.io/docs).

## Le contrat handler

Une fonction est **un fichier unique** exposant un handler. Il reçoit un objet requête et
retourne la réponse.

```python
# main.py — handler : main.handler
def handler(request):
    # request.method   -> "GET", "POST", ...
    # request.path     -> str
    # request.headers  -> dict[str, str]
    # request.query    -> dict[str, str]
    # request.body     -> bytes
    # request.json()   -> corps JSON parsé
    name = request.query.get("name", "world")
    return {"message": f"hello, {name}"}
```

Les formes de retour acceptées :

| Retour | Réponse HTTP |
|--------|--------------|
| `"texte"` | 200 `text/plain` |
| `{"a": 1}` ou `[1, 2]` | 200 `application/json` |
| `(404, "not found")` | statut + corps |
| `(201, corps, {"X-My": "hdr"})` | statut + corps + en-têtes |

En Node.js, mêmes règles avec `exports.handler` et un tableau au lieu du tuple.

Les runtimes embarquent déjà les bibliothèques courantes : `requests`, `httpx`, `pydantic`,
`PyYAML` côté Python ; `axios`, `lodash`, `zod`, `dayjs` côté Node.

## Runtimes

Les identifiants offerts sont `python`, `nodejs20`, `nodejs22`, `nodejs24`, et selon le
déploiement `python313` / `python314`. `python` reste sur 3.12 et n'est jamais repointé sous vos
pieds : les lignes plus récentes sont des identifiants distincts, que vous choisissez.

La liste réellement disponible est celle que renvoie `/api/catalog` — c'est elle qui fait foi.

## Appeler une fonction

```bash
# fonction privée — clé API dans l'en-tête Authorization
curl -H "Authorization: Bearer $ZEROLITH_KEY" "https://<url-de-la-fonction>?name=neo"

# fonction publique — aucune authentification
curl "https://<url-de-la-fonction>?name=neo"

# URL présignée — le jeton est dans l'URL, jusqu'à la date que vous fixez
curl "https://<url-de-la-fonction>?faas_token=faast_..."
```

L'authentification est vérifiée **en périphérie**, avant que votre fonction ne se réveille : un
appel non autorisé ne vous coûte rien.

*[English](README.en.md)*

# hello

Le plus petit handler qui fonctionne, dans les deux langages. C'est aussi l'exemple prérempli
dans le formulaire de déploiement.

- [`python/main.py`](python/main.py) — runtime `python`
- [`nodejs/main.js`](nodejs/main.js) — runtime `nodejs24` (ou `nodejs20` / `nodejs22`)

Handler : `main.handler` (la valeur par défaut, rien à changer).

## Appeler

```bash
curl "https://<url-de-la-fonction>?name=neo"
# {"message": "hello, neo", "method": "GET"}
```

Le paramètre `name` est optionnel et vaut `world` par défaut. Toutes les méthodes HTTP et tous
les chemins arrivent au handler : `request.method` et `request.path` vous les donnent.

## Et ensuite

Renvoyer autre chose qu'un JSON — le retour décide de la réponse :

```python
return "texte"                            # 200 text/plain
return {"a": 1}                           # 200 application/json
return 404, "not found"                   # statut + corps
return 201, corps, {"X-My": "hdr"}        # statut + corps + en-têtes
```

Les autres exemples de ce dépôt partent tous de là : [`demo-city`](../demo-city/) ajoute des
appels réseau concurrents, [`demo-dashboard`](../demo-dashboard/) renvoie une page HTML entière,
[`stock-api`](../stock-api/) y branche une base de données.

*[English](README.en.md)*

# demo-dashboard

Un tableau de bord météo qui renvoie une **page HTML complète** : la fonction va chercher ses
données côté serveur, calcule la géométrie de ses deux graphiques en Python, et renvoie un
document autonome — SVG en ligne, CSS en ligne, aucune dépendance externe.

**En direct :** <https://demo-dashboard-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/?city=Paris>

## Ce que ça montre

Le SVG est **déjà dessiné quand le document arrive**. Pas de bundler, pas d'étape de build, pas
d'écran de chargement, pas de deuxième requête pour aller chercher les données : une URL, une
réponse, la page est finie.

C'est le même geste qu'un artefact de chatbot, sauf que le résultat a une URL stable, que les
données sont fraîches à chaque chargement, et qu'aucun pod ne tourne entre deux visites. C'est la
fonction autour de laquelle est écrit l'article
[« Artefact, canvas, frame »](https://zerolith.io/blog/tableau-de-bord-html).

La même URL avec `?format=json` renvoie les mêmes données brutes : le rendu et les données
sortent du même handler, sans les dupliquer.

## Appeler

```bash
curl "https://<url-de-la-fonction>/?city=Tokyo&days=7"
curl "https://<url-de-la-fonction>/?city=Paris&format=json"
```

| Paramètre | Défaut | Rôle |
|-----------|--------|------|
| `city` | `Paris` | la ville affichée (tronquée à 80 caractères) |
| `days` | `7` | nombre de jours de prévision, borné entre 2 et 10 |
| `format` | — | `json` pour les données brutes au lieu de la page |

## Déployer

Runtime `python`, handler `main.handler`. `httpx` est déjà dans le runtime.

| Variable | Défaut | Rôle |
|----------|--------|------|
| `DEMO_TIMEOUT_SECONDS` | `8` | délai maximum accordé à l'API météo |

Les données viennent d'open-meteo, publique et sans clé.

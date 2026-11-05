*[English](README.en.md)*

# og-image

L'image d'aperçu d'un lien (Open Graph, 1200×630), dessinée à la demande par une fonction
Python. C'est elle que Slack, LinkedIn, X ou Discord affichent quand on colle une URL.

**En direct :** <https://og-image-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.fr/?title=Builds+de+d%C3%A9pendances&subtitle=zerolith.fr>

| Paramètre | Valeur |
|-----------|--------|
| `title` | le titre, 90 caractères au plus, coupé sur un mot avec « … » |
| `subtitle` | une ligne sous le titre, 70 caractères au plus |
| `theme` | `dark` (par défaut) ou `light` |

À poser dans la page qui partage le lien :

```html
<meta property="og:image"
      content="https://<url-de-la-fonction>/?title=Mon+article&subtitle=blog.example.com">
```

## Ce que ça montre

Cette fonction a besoin de deux paquets que l'image Python de base ne contient pas :

```text
# requirements.txt
pillow==13.0.0
font-source-sans-pro==0.0.1
```

- **Pillow** dessine l'image. C'est une bibliothèque **compilée** : son wheel dépend de la version
  exacte de l'interpréteur. Un `pip install` fait sur votre machine puis copié dans le code ne se
  chargerait pas ; la plateforme construit donc la couche elle-même, pour le runtime choisi.
- **font-source-sans-pro** apporte une police libre (OFL 1.1). La police intégrée à Pillow n'a
  pas de lettres accentuées : « dépendances » s'y affiche « d▯pendances ». Le code d'une fonction
  ne transporte que du texte, donc un fichier `.ttf` passe, lui aussi, par un paquet.

Les polices sont chargées une fois au démarrage du pod, pas à chaque requête.

## Déployer

Le build des dépendances est une étape **avant** le déploiement. Par MCP (ou l'API REST
`/api/dependencies/builds`) :

1. `build_dependencies` avec `language: "python"` et le `requirements.txt` ;
2. `get_dependency_build` jusqu'à `ready` (environ 15 s pour ce lockfile) ;
3. `deploy_function` avec `main.py` **et** le même `requirements.txt`, handler `main.handler`.

Un déploiement dont le lockfile n'a pas encore de build prêt est refusé (409) avec la marche à
suivre. Mesuré en prod le 2026-11-05 : couche de 9,8 Mo compressés (26 Mo une fois extraite),
téléchargée en 0,5 s au démarrage du pod ; rendu d'une image en 160 ms environ. Démarrage à froid (taille `small`) : 4,2 s en moyenne sur
trois essais, contre 2,3 s pour `hello` au même moment, soit environ 1,8 s pour la couche ; à chaud,
0,15 s.

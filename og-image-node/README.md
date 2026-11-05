*[English](README.en.md)*

# og-image-node

La même image d'aperçu de lien (Open Graph, 1200×630) que [`og-image`](../og-image/), dessinée
cette fois par une fonction **Node.js**.

**En direct :** <https://og-image-node-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.fr/?title=D%C3%A9pendances+Node&subtitle=zerolith.fr>

Mêmes paramètres : `title` (90 caractères au plus), `subtitle` (70), `theme` = `dark` ou `light`.

## Ce que ça montre

Trois paquets absents de l'image Node de base, déclarés dans `package.json` et figés par
`package-lock.json` :

| Paquet | Rôle |
|--------|------|
| `satori` | met en page un arbre de type JSX (flexbox, texte) et produit un SVG, en JavaScript pur |
| `@resvg/resvg-js` | rastérise le SVG en PNG. Un binaire **natif** (Rust) : `npm ci` installe la variante de la plateforme, `linux-x64-gnu` ici, et ignore les onze autres |
| `@fontsource/source-sans-3` | la police, en WOFF : satori ne lit pas le WOFF2 |

Le handler n'a pas besoin de compilateur JSX : un nœud satori s'écrit
`{ type: 'div', props: { style, children } }`.

**Une dépendance corrigée sans attendre l'amont.** Après le premier build, l'indicateur de
vulnérabilités (OSV) a signalé `fflate@0.7.3` (GHSA-px8p-9vwx-vf98), que satori épingle en version
exacte. La faille concerne `unzipSync` sur une archive ZIP forgée, que cette fonction n'appelle
jamais ; elle a quand même été corrigée par un `overrides` npm :

```json
"overrides": { "fflate": "0.7.5" }
```

Le PNG produit est identique à l'octet près, et le build suivant ne signale plus rien.

## Déployer

1. Générez le lockfile sans exécuter de script : `npm install --package-lock-only --ignore-scripts` ;
2. `build_dependencies` avec `language: "nodejs22"`, `package.json` **et** `package-lock.json` ;
3. `get_dependency_build` jusqu'à `ready` (environ 30 s pour ce lockfile) ;
4. `deploy_function` avec `main.js`, `package.json` et `package-lock.json`, handler `main.handler`.

Mesuré en prod le 2026-11-05 : couche de 18,4 Mo compressés (46 Mo, 707 fichiers une fois extraite).
Démarrage à froid (taille `small`, six essais) : médiane 4,3 s, contre 1,4 s pour `timer` (Node, sans
couche) au même moment ; le téléchargement de la couche en prend 1,6 s en médiane. À chaud, 0,12 à 0,18 s.

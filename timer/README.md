*[English](README.en.md)*

# timer

Une page web de compte à rebours, en une fonction Node.js. On saisit une durée, elle décompte
jusqu'à 00:00.

**En direct :** <https://timer-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/>

## Ce que ça montre

Le handler ne fait qu'une chose : renvoyer une page HTML complète, avec son CSS et son script
en ligne. Toute l'interactivité — la saisie, le décompte, les préréglages — tourne **dans le
navigateur**, pas sur la plateforme. La fonction ne s'exécute donc qu'une fois par chargement de
page, et dort le reste du temps.

C'est le profil le moins cher qui existe sur une plateforme facturée au temps d'exécution : un
seul appel très court, puis plus rien.

```js
exports.handler = (request) => {
  return [200, PAGE, { 'content-type': 'text/html; charset=utf-8' }];
};
```

Le tableau `[statut, corps, en-têtes]` est la forme de retour qui permet de fixer le
`content-type` — sans lui, une chaîne serait servie en `text/plain` et le navigateur afficherait
le HTML au lieu de le rendre.

## Déployer

Runtime `nodejs24` (`nodejs20` et `nodejs22` conviennent aussi), handler `main.handler`, aucune
variable d'environnement, aucun paramètre de requête. La fonction répond la même page sur
n'importe quel chemin.

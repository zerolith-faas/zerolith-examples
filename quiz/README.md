*[English](README.en.md)*

# quiz — masquer un démarrage à froid derrière un jeu

Un quiz de dix questions sur le serverless. Pendant que vous y répondez, la base de données se
réveille en coulisse — et quand vient le moment d'enregistrer votre score, elle est debout depuis
longtemps.

**En direct :** <https://jeu-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.fr/>
(et <https://jeu-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.fr/?prewarm=0> pour jouer la
même partie **sans** le tour de passe-passe — c'est la comparaison, jouable)

## Ce que ça montre

Une fonction démarre vite. Une base de données, non : elle doit en plus restaurer son état depuis
le stockage objet. Sur cette plateforme, mesuré le jour où cet exemple a été écrit, une fonction
Python froide répond en ~2 s quand le réveil d'une base en prend ~14. C'est le genre d'écart qui
transforme une démonstration en écran figé.

Ce démarrage n'est pas supprimé ici, ni raccourci d'une milliseconde. Il est **déplacé hors du
chemin où quelqu'un attend** — et ça ne demande ni cache, ni file d'attente, ni instance
maintenue chaude. Ça demande de **découper en deux fonctions** :

| Fonction | Base attachée | Rôle |
|----------|---------------|------|
| `jeu` (ce dossier, [`main.py`](main.py)) | **aucune** | rend la page, et rien d'autre. N'a pas de `DATABASE_URL` et ne saurait qu'en faire. |
| `quiz-api` ([`api/main.py`](api/main.py)) | oui | la moitié qui parle à la base : réveil, écriture du score, agrégats. |

À la première image du rendu, la page appelle `quiz-api/wake` **sans attendre la réponse**. Cet
appel réveille le pod de la base et paie sa restauration pendant que le joueur lit les règles et
répond aux questions. À la fin de la partie, ~45 s plus tard, l'écriture prend quelques
millisecondes.

La séparation est ce qui rend le tour possible. Si la page et la base vivaient dans la même
fonction, le visiteur attendrait le réveil avant de voir quoi que ce soit — c'est exactement ce
que `?prewarm=0` remet en scène.

## La démonstration collecte ses propres preuves

Chaque partie enregistre trois colonnes qui n'ont rien à voir avec le quiz : si la page avait
préchauffé la base (`prewarm`), combien de temps le réveil a pris (`wake_ms`), et combien de
temps l'écriture finale a pris **vue du navigateur** (`submit_ms`). `GET /stats` en sort la
comparaison des deux régimes sur l'ensemble des joueurs.

Deux détails qui se paient à la conception plutôt qu'après :

**`submit_ms` arrive par une deuxième requête.** Un navigateur ne peut pas connaître la durée
d'une requête avant qu'elle finisse, et c'est précisément cette durée qu'on veut publier. La page
mesure, puis dépose la valeur par `POST /latency` — minuscule, et sur une base désormais chaude.

**Cette écriture est unique par partie** (`WHERE submit_ms IS NULL`). Sans cette clause,
n'importe qui pourrait réécrire la latence de n'importe quelle partie et déplacer la médiane que
la page affiche. La route répond `{"recorded": false}` quand elle a refusé — dire « enregistré »
sur une écriture refusée serait une réponse qui ment.

## Routes de `quiz-api`

```
GET  /wake      un SELECT 1, et rien d'autre. Le but n'est pas d'obtenir une réponse
                mais de faire exister le pod. Rend le temps que ça a pris.
POST /score     {score, answers[10], duration_ms, prewarm, wake_ms} -> {game_id, rank}
POST /latency   {game_id, submit_ms} -> {recorded}   écriture unique par partie
GET  /stats     les agrégats, dont la latence d'écriture avec et sans préchauffage
```

Le score est calculé par le navigateur. C'est assumé : corriger côté serveur imposerait de
dupliquer la banque de questions dans les deux fonctions, alors que le sujet est la latence, pas
la triche. L'API valide donc la **forme** de ce qui arrive — longueurs, bornes, types, cohérence
du score avec les réponses — pour qu'un envoi malformé ne pollue pas les agrégats. Un corps qui
n'est pas du JSON est refusé en 400, avant même d'ouvrir la base.

## Déployer

Trois fonctions, une base. Runtime `python`, handler `main.handler` partout.

1. **`quiz-migrate`** — [`migrator/main.py`](migrator/main.py), déployée avec le type
   **`migrate`** (`"kind": "migrate"` à la création). C'est du DDL : ça n'a rien à faire sur une
   URL ouverte, et ce type n'en a aucune. Ni service, ni route, ni nom d'hôte, et aucun pod entre
   deux exécutions — elle est donc privée *par construction* et non par un drapeau, `public: true`
   y étant refusé plutôt qu'ignoré. Le code ne change pas : `request` vaut `method: "RUN"`.
2. Créez la base, attachez-la au migrateur, désignez-le comme **migrateur** de la base, puis
   déclenchez-le. Il est rejouable : `CREATE TABLE IF NOT EXISTS` partout.
3. **`quiz-api`** — [`api/main.py`](api/main.py), **publique**, la même base attachée.
4. **`jeu`** — [`main.py`](main.py), **publique**, **sans base**. C'est le cœur du dispositif :
   ne lui en attachez pas.

La page déduit l'URL de son API de son propre `Host` : `jeu-fn-<id>` et `quiz-api-fn-<id>` ne
diffèrent que par leur premier segment. Redéployez la paire sous un autre compte et elle se
retrouve toute seule. `QUIZ_API_URL` reprend la main si vous nommez vos fonctions autrement.

| Variable | Défaut | Rôle |
|----------|--------|------|
| `DATABASE_URL` | injectée | adresse de la base attachée (`quiz-api` et le migrateur seulement) |
| `DATABASE_AUTH_TOKEN` | injectée | jeton, monté depuis un secret en écriture seule |
| `QUIZ_API_URL` | déduite du `Host` | sur `jeu`, si les deux fonctions ne partagent pas leur suffixe |

### Le contrôle préalable CORS

Les deux fonctions ont des origines différentes, donc l'API renvoie les en-têtes CORS. Ça ne suffit
pas : un `POST` en `application/json` n'est pas une requête « simple », le navigateur envoie donc
d'abord un `OPTIONS` de contrôle préalable. C'est la branche `OPTIONS` de
[`api/main.py`](api/main.py) qui y répond : le runtime passe la méthode au handler, donc la
politique CORS de la fonction est décidée là et nulle part ailleurs.

[`main.py`](main.py) poste en `text/plain;charset=UTF-8`, qui est une requête simple. C'est un
choix, pas une obligation : une requête simple n'a pas de contrôle préalable, donc c'est un
aller-retour de moins avant l'écriture. Côté serveur rien ne change, `request.json()` analyse les
octets reçus sans regarder le `Content-Type`.

### Un piège qui a coûté un 500 en production

`request.headers` est un **dictionnaire ordinaire** qui conserve la casse d'origine : la clé est
`Host`, pas `host`. Un `request.headers.get("host")` renvoie `None` sans lever, la page rend un
500, et un banc de test qui fabrique ses en-têtes en minuscules reste vert. [`main.py`](main.py)
normalise la casse avant de chercher. Si vous lisez un en-tête dans un handler, faites-en autant.

## Le schéma

```
games(id, score, duration_ms, prewarm, wake_ms, submit_ms, created_at)
answers(game_id, q, correct)
```

`answers` existe pour une seule chose : dire « la question que tout le monde rate ». C'est un
agrégat qui n'a de sens que parce que tous les joueurs écrivent dans la même base — le genre de
chose qu'une fonction sans état ne peut pas produire.

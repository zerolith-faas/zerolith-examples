*[English](README.en.md)*

# stock-api

Une API d'inventaire de magasin, adossée à une **base de données privée** : catalogue, fiche
article avec son historique, entrées et sorties de stock, agrégats.

**En direct :** <https://stock-api-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/stats>
(instance publique en **lecture seule** — les écritures y sont désactivées pour que les données
restent lisibles par tous)

## Ce que ça montre

L'état survit à la mise en veille. La base dort avec la fonction : au repos, ni l'une ni l'autre
ne coûte de temps de calcul, seul le palier de stockage réservé reste facturé. Le premier appel
après une période creuse réveille les deux et paie un démarrage à froid — puis les données sont
exactement là où on les avait laissées.

Rien à configurer côté code : quand une base est attachée à la fonction, la plateforme injecte
`DATABASE_URL` et `DATABASE_AUTH_TOKEN` dans le pod. Le jeton n'est affiché nulle part, ni dans
l'interface ni dans l'API — il est monté depuis un secret en écriture seule.

**La décision de conception qui compte :** le stock n'est pas une colonne que l'on incrémente,
mais la **somme d'un registre de mouvements**. Deux pods réveillés en parallèle qui lisent 10,
ajoutent 5 chacun et écrivent 15 au lieu de 20, ce n'est pas un cas d'école sur une plateforme
qui démarre des instances quand le trafic monte : c'est le comportement par défaut. Un registre
n'a pas ce problème puisque chaque écriture est une insertion. En prime, l'historique est gratuit.
La contrepartie est une agrégation à la lecture — négligeable à cette échelle, et indexée.

## Routes

```
GET  /                     ce message et les agrégats
GET  /products             catalogue + stock courant  (?category=  ?low_stock=1)
GET  /products/<sku>       fiche article + 20 derniers mouvements
POST /products             {sku, name, category, price_cents, reorder_level, quantity}
POST /movements            {sku, delta, reason}   delta négatif = sortie
GET  /stats                agrégats et valeur du stock
```

```bash
curl "https://<url-de-la-fonction>/stats"
curl "https://<url-de-la-fonction>/products?low_stock=1"
```

## Déployer

Runtime `python`, handler `main.handler`. Le client libSQL est déjà dans le runtime.

1. Provisionnez une base depuis l'application, puis **attachez-la** à la fonction. Les deux
   variables d'environnement apparaissent alors dans le pod, sans que vous les écriviez.
2. Posez le schéma avec [`migrator/main.py`](migrator/main.py) : le serveur de base ne peut pas
   appeler vos fonctions, donc les migrations sont explicites. Déployez le migrateur en fonction
   privée, désignez-le comme **migrateur** de la base, puis déclenchez-le depuis l'interface,
   l'API ou un agent MCP.
3. Retirez `STOCK_READ_ONLY` (ou passez-la à `0`) pour obtenir l'API complète en écriture.

| Variable | Défaut | Rôle |
|----------|--------|------|
| `DATABASE_URL` | injectée | adresse de la base attachée |
| `DATABASE_AUTH_TOKEN` | injectée | jeton, monté depuis un secret en écriture seule |
| `STOCK_READ_ONLY` | `1` | refuse les écritures ; mettre à `0` pour l'API complète |

### Le schéma et la fonction migratrice

[`migrator/main.py`](migrator/main.py) pose le schéma que cette API attend :

```
products(id, sku, name, category, price_cents, reorder_level, created_at)
movements(id, product_id, delta, reason, created_at)
```

Déployez-la en **fonction privée séparée** (c'est du DDL, ça n'a rien à faire sur une URL
ouverte), attachez-lui la même base, désignez-la comme migratrice, puis déclenchez-la. Elle est
rejouable : `CREATE TABLE IF NOT EXISTS` partout, et l'amorçage du catalogue de démonstration
n'a lieu que si la table `products` est vide. Relancée sur une base déjà utilisée, elle ne
duplique rien et ne touche pas au stock réel.

Le `IF NOT EXISTS` n'est pas de la paresse : la migration est déclenchée à la main, donc elle
doit pouvoir être rejouée sans conséquence, ne serait-ce que parce qu'on ne sait plus si elle
est passée.

Le raisonnement complet sur le registre de mouvements est développé dans l'article
[« Une API avec état »](https://zerolith.io/blog/api-base-de-donnees) — l'article en donne une
version volontairement simplifiée du schéma (sans `category` ni `reorder_level`) ; celle de ce
dépôt est la version complète, alignée sur le code.

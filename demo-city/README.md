*[English](README.en.md)*

# demo-city

Un agrégateur d'API en une fonction Python : un géocodage, puis trois appels **concurrents**
(météo, qualité de l'air, Wikipédia) fusionnés en une seule réponse JSON.

**En direct :** <https://demo-city-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.io/?city=Paris>

## Ce que ça montre

La latence rendue au client est celle de l'API la plus lente, **pas la somme des trois** : les
appels partent ensemble via `asyncio.gather`. C'est le gain qui justifie de faire l'agrégation
côté serveur plutôt que dans le navigateur, où trois requêtes séparées auraient aussi coûté
trois allers-retours au client.

Aucune clé d'API, aucun état conservé : la fonction est purement calculatoire. C'est le profil
idéal pour le scale-to-zero — elle ne coûte rien tant que personne ne l'appelle. La réponse
expose d'ailleurs son propre temps de démarrage, pour que vous puissiez constater le démarrage à
froid au lieu de nous croire sur parole.

## Appeler

```bash
curl "https://<url-de-la-fonction>/?city=Tokyo"
curl "https://<url-de-la-fonction>/?city=Paris&lang=en"
```

| Paramètre | Défaut | Rôle |
|-----------|--------|------|
| `city` | `Paris` | la ville à géocoder |
| `lang` | `fr` | la langue de la réponse |

## Déployer

Runtime `python`, handler `main.handler`. `httpx` est déjà dans le runtime, rien à installer.

| Variable | Défaut | Rôle |
|----------|--------|------|
| `DEMO_TIMEOUT_SECONDS` | `6` | délai maximum accordé à chaque API amont |

Les APIs appelées (open-meteo, Wikipédia) sont publiques et sans clé. Si vous déployez cet
exemple tel quel, vos appels sortants passent par le réseau de votre espace isolé — pensez-y si
vous remplacez ces APIs par un service qui compte les requêtes.

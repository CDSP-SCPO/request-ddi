## Configuration des Secrets Kubernetes

Pour déployer l'application **basedequestions** sur Kubernetes, assurez-vous de mettre à jour les clés suivantes dans les secrets appropriés. 

### Secrets à mettre à jour

| Clé                        | Secret                 | Description                          |
|---------------------------|-------------------------|--------------------------------------|
| `DJANGO_SECRET_KEY`       | `basedequestions-secret`| Clé secrète pour Django              |
| `DJANGO_ALLOWED_HOSTS`    | `basedequestions-secret`| Liste des hôtes autorisés par Django |
| `CSRF_TRUSTED_ORIGINS`    | `basedequestions-secret`| Origines de confiance pour CSRF      |
| `POSTGRES_DB`             | `postgres`              | Nom de la base de données PostgreSQL |
| `POSTGRES_USER`           | `postgres`              | Utilisateur de la base de données    |
| `POSTGRES_PASSWORD`       | `postgres`              | Mot de passe de la base de données   |
| `ELASTICSEARCH_HOST`      | `elasticsearch-secret`  | Hôte Elasticsearch                   |



# 📘 Déploiement Kubernetes – Environnement Préproduction

## 🌐 Namespace
Le namespace utilisé pour cet environnement est `request`.

---

## 🧱 Composants déployés

### 1. **Application Django – `basedequestions`**

#### `basedequestions/deployment.yaml`
Ce fichier définit le déploiement de l'application Django. Voici les détails :
- **Nom du déploiement** : `basedequestions`
- **Réplicas** : `1`
- **Image Docker** : `gitlab.sciences-po.fr:4567/cdspit/request/base-de-questions:latest`
- **Entrypoint** : `./entrypoint.sh`
- **Init container** : crée `/app/media`, change les permissions, ajoute un fichier test
- **Secrets utilisés** :
  - `basedequestions-secret` (Django)
  - `postgres` (DB)
  - `elasticsearch-secret` (ES)
- **Variables d’environnement** : injectées via `env` et `secretKeyRef`
- **Volumes** :
  - `media-volume` monté sur `/app/media` via PVC `media-pvc`

#### `basedequestions/service.yaml`
Ce fichier définit le service associé à l'application Django. Voici les détails :
- **Nom** : `basedequestions`
- **Type** : `ClusterIP` (headless)
- **Port exposé** : `8000`
- **Selector** : `app: basedequestions`

---

### 2. **Base de données PostgreSQL**

#### `db/deployment.yaml`
Ce fichier définit le déploiement de la base de données PostgreSQL. Voici les détails :
- **Nom du déploiement** : `postgres-deployment`
- **Namespace** : `request`
- **Image Docker** : `postgres:14-alpine`
- **Secrets utilisés** : `postgres` (contient `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`)
- **Volume persistant** : `db-pvc` monté sur `/var/lib/postgresql/data`
- **Labels** : `app=postgres`, `component=db`, `environment=pprd`

#### `db/service.yaml`
Ce fichier définit le service associé à la base de données PostgreSQL. Voici les détails :
- **Nom** : `db`
- **Namespace** : `request`
- **Type** : `ClusterIP` (headless)
- **Port exposé** : `5432`
- **Selector** : `app: postgres`, `component: db`

---

### 3. **Elasticsearch**

#### `elasticsearch/deployment.yaml`
Ce fichier définit le déploiement d'Elasticsearch. Voici les détails :
- **Nom du déploiement** : `elasticsearch`
- **Image Docker** : `elasticsearch:7.17.10`
- **Mode** : `single-node`
- **Ressources** :
  - `requests`: 1Gi RAM / 500m CPU
  - `limits`: 2Gi RAM / 1 CPU
- **Volumes** :
  - `elasticsearch-pvc`
  - ConfigMap `elasticsearch-config`
- **Probes** : readiness & liveness sur `/`
- **Labels** : `component=elasticsearch`

#### `elasticsearch/service.yaml`
Ce fichier définit le service associé à Elasticsearch. Voici les détails :
- **Nom** : `elasticsearch`
- **Type** : `ClusterIP` (headless)
- **Port exposé** : `9200`
- **Selector** : `component: elasticsearch`

#### `elasticsearch-pvc.yaml`
Ce fichier définit le volume persistant pour Elasticsearch. Voici les détails :
- **Nom** : `elasticsearch-pvc`
- **Namespace** : `request`
- **AccessModes** : `ReadWriteOnce`
- **Storage** : `10Gi`
- **StorageClassName** : `nfs-provisioner`

---

### 4. **NGINX pour les fichiers médias**

#### `nginx-media/deployment.yaml`
Ce fichier définit le déploiement de NGINX pour servir les fichiers médias. Voici les détails :
- **Nom du déploiement** : `nginx-media`
- **Namespace** : `request`
- **Image Docker** : `nginx:latest`
- **Volume partagé** : `media-pvc`
- **ConfigMap** : `nginx-config` (sert `/media/`)
- **Port exposé** : `80`
- **Labels** : `app=nginx-media`

#### `nginx-media/nginx-configmap.yaml`
Ce fichier définit la configuration de NGINX via un ConfigMap. Voici les détails :
- **Nom** : `nginx-config`
- **Namespace** : `request`
- **Contenu** : configuration NGINX pour servir les fichiers médias

#### `nginx-media/service.yaml`
Ce fichier définit le service associé à NGINX pour les fichiers médias. Voici les détails :
- **Nom** : `nginx-media`
- **Type** : `ClusterIP`
- **Port exposé** : `80`
- **Selector** : `app: nginx-media`

---

### 5. **Ingress**

#### `overlays/pprd/ingress.yaml`
Ce fichier définit l'Ingress pour l'accès externe. Voici les détails :
- **Nom** : `basedequestions-ingress`
- **Namespace** : `request`
- **Host** : `request-pprd.sciencespo.fr`
- **Timeouts** :
  - `proxy-connect-timeout`: 3600s
  - `proxy-read-timeout`: 3600s
  - `proxy-send-timeout`: 3600s
- **Autres annotations** :
  - `proxy-body-size`: 100m
  - `proxy-request-buffering`: off
  - `enable-cors`: true
- **Routes** :
  - `/media/` → `nginx-media:80`
  - `/` → `basedequestions:8000`

---

### 6. **Kustomization**

#### `pprd/kustomization.yaml`
Ce fichier regroupe toutes les ressources dans un overlay pour la préproduction. Voici les détails :
- **Base** : `../../base`
- **Ressources ajoutées** :
  - `pvc.yml`, `media-pvc.yml`, `ingress.yml`
- **Images** :
  - `basedequestions` avec tag `pprd`
- **Labels communs** :
  - `environment: pprd`

---

## 🔍 Points à surveiller

- **Timeouts NGINX** : non spécifiés ici → à vérifier dans l’Ingress
- **Ressources Django** : non définies → à ajouter si besoin de scaling
- **Elasticsearch** : mode single-node → OK pour préprod, à adapter en prod

---

## 🛠️ Actions manuelles nécessaires

### 1. **Création des secrets**
- `basedequestions-secret` : contient les variables d'environnement pour Django
- `postgres` : contient les informations de connexion à la base de données
- `elasticsearch-secret` : contient les informations de connexion à Elasticsearch

### 2. **Création des volumes persistants**
- `db-pvc` : volume persistant pour PostgreSQL (1Gi)
- `elasticsearch-pvc` : volume persistant pour Elasticsearch (10Gi)
- `media-pvc` : volume persistant pour les fichiers médias

### 3. **Création du ConfigMap `elasticsearch-config`**

Pour créer manuellement le ConfigMap `elasticsearch-config` dans le namespace `request`, suivez les étapes suivantes :

1. Créez un fichier nommé `elasticsearch-configmap.yaml` avec le contenu suivant :

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: elasticsearch-config
  namespace: request
data:
  elasticsearch.yml: |
    cluster.name: "elasticsearch"
    network.host: 0.0.0.0
    discovery.type: single-node
    bootstrap.memory_lock: true


---

## Diagramme d'architecture

Le diagramme d'architecture est disponible à l'URL suivante : " https://www.canva.com/design/DAG5D0e_dcM/bc-f7EnHqbgVJkeqtzS7sw/edit?utm_content=DAG5D0e_dcM&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton"

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


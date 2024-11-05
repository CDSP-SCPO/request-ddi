#!/usr/bin/env sh

# Créer le dossier media s'il n'existe pas
mkdir -p /app/media

# Lancer les migrations Django
python manage.py makemigrations
python manage.py migrate

echo "Waiting for Elasticsearch to be ready..."
while ! nc -z elasticsearch 9200; do
  sleep 1
done

echo "Elasticsearch is up - executing command"

python manage.py search_index --rebuild -f

echo "after populate"

python manage.py shell -c "from app.documents import BindingSurveyDocument; BindingSurveyDocument().update_index()"

echo "after shell"

# Collecter les fichiers statiques
python manage.py collectstatic --noinput

# Démarrer le serveur Django
gunicorn basedequestions.wsgi:application --bind 0.0.0.0:8000

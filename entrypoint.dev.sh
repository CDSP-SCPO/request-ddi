#!/usr/bin/env sh

# Lancer les migrations Django
python manage.py makemigrations
python manage.py migrate

echo "Waiting for Elasticsearch to be ready..."
while ! nc -z elasticsearch 9200; do
  sleep 1
done

echo "Elasticsearch is up - executing command"

# Rebuild the search index
python manage.py search_index --rebuild -f

echo "after populate"

# Mettre à jour l'index avec des documents
python manage.py shell -c "from app.documents import BindingSurveyDocument; BindingSurveyDocument().update_index()"

echo "after shell"

# Démarrer le serveur Django
python manage.py runserver 0.0.0.0:8000

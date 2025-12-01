#!/usr/bin/env sh

# Lancer les migrations Django
echo "Applying Django DB migrations..."
python manage.py migrate
if [ $? -eq 0 ]; then
    echo "DB migrations applied successfully."
else
    echo "Error applying DB migrations."
    exit 1
fi

# Attendre qu'Elasticsearch soit prêt
echo "Waiting until Elasticsearch is available..."
until curl -s -f -o /dev/null --user "${ELASTICSEARCH_ADMIN_USER}:${ELASTICSEARCH_ADMIN_PASSWORD}" "${ELASTICSEARCH_URL}/_cluster/health?wait_for_status=green&timeout=5s"; do
    sleep 1
done
echo "Elasticsearch is ready and reporting status green."

# Création des index dans l'Elasticsearch
if curl -s --user "${ELASTICSEARCH_ADMIN_USER}:${ELASTICSEARCH_ADMIN_PASSWORD}" "${ELASTICSEARCH_URL}/_cat/indices?format=json" | jq -e '. == []'; then
    echo "No indices found in Elasticsearch. Creating indices..."
    python manage.py search_index --rebuild -f
fi

# Mise à jour de l'index Elasticsearch
echo "Updating Elasticsearch index..."
python manage.py shell -c "from app.documents import BindingSurveyDocument; BindingSurveyDocument().update_index()"
if [ $? -eq 0 ]; then
    echo "Elasticsearch index updated successfully."
else
    echo "Error updating Elasticsearch index."
    exit 1
fi

# Démarrage du serveur
if [ "${DJANGO_DEBUG}" = "True" ]; then
    echo "Starting development server..."
    python manage.py runserver 0.0.0.0:8000
else
    # Collecte des fichiers statiques
    echo "Collect static files..."
    python manage.py collectstatic --noinput
    if [ $? -eq 0 ]; then
        echo "Static files collected successfully."
    else
        echo "Error collecting static files."
        exit 1
    fi

    echo "Starting Gunicorn server..."
    exec gunicorn basedequestions.wsgi:application \
        --bind 0.0.0.0:8000 \
        --timeout 3600 \
        --workers 3 \
        --threads 4 \
        --log-level info \
        --access-logfile -
fi
if [ $? -eq 0 ]; then
    echo "Server started successfully."
else
    echo "Error while starting server."
    exit 1
fi

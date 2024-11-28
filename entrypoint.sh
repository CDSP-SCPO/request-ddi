#!/usr/bin/env sh

# Lancer les migrations Django
echo "Application des migrations Django..."
python manage.py migrate
if [ $? -eq 0 ]; then
    echo "Migrations appliquées avec succès."
else
    echo "Erreur lors de l'application des migrations."
    exit 1
fi

# Attendre qu'Elasticsearch soit prêt
echo "Attente de la disponibilité d'Elasticsearch..."
while ! nc -z elasticsearch 9200; do
    sleep 1
done
echo "Elasticsearch est prêt."

# Reconstitution de l'index de recherche
echo "Reconstruction de l'index de recherche Elasticsearch..."
python manage.py search_index --rebuild -f
if [ $? -eq 0 ]; then
    echo "Index de recherche reconstruit avec succès."
else
    echo "Erreur lors de la reconstruction de l'index de recherche."
    exit 1
fi

# Mise à jour de l'index Elasticsearch
echo "Mise à jour de l'index Elasticsearch..."
python manage.py shell -c "from app.documents import BindingSurveyDocument; BindingSurveyDocument().update_index()"
if [ $? -eq 0 ]; then
    echo "Mise à jour de l'index réussie."
else
    echo "Erreur lors de la mise à jour de l'index."
    exit 1
fi

# Collecte des fichiers statiques
echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput
if [ $? -eq 0 ]; then
    echo "Fichiers statiques collectés avec succès."
else
    echo "Erreur lors de la collecte des fichiers statiques."
    exit 1
fi

# Lancer Gunicorn avec des paramètres optimisés
echo "Démarrage du serveur Gunicorn..."
gunicorn basedequestions.wsgi:application \
    --bind 0.0.0.0:8000 \
    --timeout 300 \  # Timeout augmenté pour supporter les requêtes longues
    --workers 3 \  # Nombre de processus (ajustez selon vos ressources)
    --threads 4 \  # Threads par processus pour meilleure gestion IO
    --log-level info \  # Logs plus lisibles en production
    --access-logfile -  # Journaux des accès en sortie standard
if [ $? -eq 0 ]; then
    echo "Serveur Gunicorn démarré avec succès."
else
    echo "Erreur lors du démarrage du serveur Gunicorn."
    exit 1
fi

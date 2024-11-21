#!/usr/bin/env sh
python manage.py showmigrations
python manage.py flush --noinput
python manage.py migrate app zero

# Lancer les migrations Django
echo "Lancement des migrations Django..."
python manage.py makemigrations
if [ $? -eq 0 ]; then
    echo "Migrations créées avec succès."
else
    echo "Erreur lors de la création des migrations."
    exit 1
fi

python manage.py migrate
if [ $? -eq 0 ]; then
    echo "Migrations appliquées avec succès."
else
    echo "Erreur lors de l'application des migrations."
    exit 1
fi

echo "Waiting for Elasticsearch to be ready..."
while ! nc -z elasticsearch 9200; do
  sleep 1
done

echo "Elasticsearch is up - executing command"

python manage.py search_index --rebuild -f
if [ $? -eq 0 ]; then
    echo "L'index de recherche a été reconstruit avec succès."
else
    echo "Erreur lors de la reconstruction de l'index de recherche."
    exit 1
fi

echo "after populate"

python manage.py shell -c "from app.documents import BindingSurveyDocument; BindingSurveyDocument().update_index()"
if [ $? -eq 0 ]; then
    echo "L'index a été mis à jour avec succès."
else
    echo "Erreur lors de la mise à jour de l'index."
    exit 1
fi

echo "after shell"

# Collecter les fichiers statiques
echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput
if [ $? -eq 0 ]; then
    echo "Fichiers statiques collectés avec succès."
else
    echo "Erreur lors de la collecte des fichiers statiques."
    exit 1
fi

# Démarrer le serveur Django
echo "Démarrage du serveur Django..."
gunicorn basedequestions.wsgi:application --bind 0.0.0.0:8000
if [ $? -eq 0 ]; then
    echo "Serveur Django démarré avec succès."
else
    echo "Erreur lors du démarrage du serveur Django."
    exit 1
fi

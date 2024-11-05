FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Crée un utilisateur non privilégié
RUN adduser -u 5678 --disabled-password --gecos "" appuser

# Installe netcat pour les vérifications de connexion
RUN apt-get update && apt-get install -y netcat-openbsd && apt-get clean

# Définit le répertoire de travail
WORKDIR /app

# Crée les répertoires pour les fichiers statiques et ajuste les permissions
RUN mkdir -p /app/static && chown -R appuser:appuser /app/static
RUN mkdir -p /app/collected_static && chown -R appuser:appuser /app/collected_static



# Copie le fichier requirements.txt et installe les dépendances
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade -r requirements.txt

# Copie le reste du code de l'application
COPY --chown=appuser:appuser . .

# Rendre le script d'entrée exécutable
RUN chmod +x /app/entrypoint.sh

# Définit l'utilisateur non privilégié
USER appuser

# Définit le point d'entrée de l'application
ENTRYPOINT ["./entrypoint.sh"]

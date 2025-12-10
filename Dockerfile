FROM python:3.13-alpine

ARG development=False

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Crée un utilisateur non privilégié
RUN adduser -u 1000 --disabled-password --gecos "" appuser

# Installe curl pour les vérifications de connexion
RUN apk add --no-cache git
RUN if [ "${development}" = "True" ]; then apk add --no-cache bash gettext; fi;

# Définit le répertoire de travail
WORKDIR /app

# Copie le reste du code de l'application
COPY --chown=appuser:appuser . .

# Installe l'application
RUN if [ "${development}" = "False" ]; then \
        pip install --no-cache-dir .; rm -rf /app/; apk del git; \
    else \
        pip install --no-cache-dir -e '.[dev]'; apk del git; \
    fi

# Copie config de l'app
COPY --chown=appuser:appuser config config

# Crée les répertoires pour les fichiers statiques et ajuste les permissions
RUN mkdir -p /app/collect_static && chown -R appuser:appuser /app/collect_static

# Définit l'utilisateur non privilégié
USER appuser

# Définit le point d'entrée de l'application
ENTRYPOINT ["request_ddi_manage", "bootstrap", "--ensuresuperuser", "--startserver"]

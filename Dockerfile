FROM python:3.13-alpine

ARG development=False

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Crée un utilisateur non privilégié
RUN adduser -u 1000 --disabled-password --gecos "" appuser

# Installe curl pour les vérifications de connexion
RUN apk add --no-cache git nodejs npm
RUN if [ "${development}" = "True" ]; then apk add --no-cache bash gettext; fi;

# Définit le répertoire de travail
WORKDIR /app

# Copie le reste du code de l'application
COPY --chown=appuser:appuser . .

# Installe l'application
# Due to the .dockerignore not all files are copied into the container during the build
# process. Hence, `git status` will report missing files which leads to VCS reporting
# versions as v1.2.0.dev0.<commit hash> even when we are on tagged versions. To avoid this
# situation, we need to restore all files before calling pip install for production
# images
# We need to add `git config --global --add safe.directory /app` command as well as
# the user building the image is `root` whereas repo files are owned by `appuser`. To bypass
# the permission checks, we need this config
RUN if [ "${development}" = "False" ]; then \
        git config --global --add safe.directory /app; git restore .; \
        pip install --no-cache-dir .; rm -rf /app/; apk del git nodejs npm; \
    else \
        pip install --no-cache-dir -e '.[dev]'; \
    fi

# Copie config de l'app
COPY --chown=appuser:appuser config config

# Crée les répertoires pour les fichiers statiques et ajuste les permissions
RUN mkdir -p /app/collect_static && chown -R appuser:appuser /app/collect_static

# Définit l'utilisateur non privilégié
USER appuser

# Définit le point d'entrée de l'application
ENTRYPOINT ["request_ddi_manage", "bootstrap", "--ensuresuperuser", "--startserver"]

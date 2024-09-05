FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN adduser -u 5678 --disabled-password --gecos "" appuser

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade -r requirements.txt
COPY --chown=appuser:appuser . .

USER appuser
ENTRYPOINT ["entrypoint.sh"]

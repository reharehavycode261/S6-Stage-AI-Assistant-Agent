# ===============================================
# Dockerfile AI-Agent Application
# ===============================================
# Image FastAPI + Celery + LangGraph
# Compatible avec: PostgreSQL + RabbitMQ
# ===============================================

FROM python:3.12-slim

# Metadata
LABEL maintainer="AI-Agent Team"
LABEL description="AI-Agent application with FastAPI, Celery, and LangGraph"
LABEL version="2.0"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Répertoire de travail
WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copier les requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copier le code de l'application
COPY . .

# Créer les répertoires nécessaires
RUN mkdir -p /app/logs && \
    mkdir -p /tmp/workspaces && \
    chmod -R 755 /app

# Exposer les ports
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Commande par défaut (API FastAPI)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


# ===============================================
# Dockerfile PostgreSQL avec pg_partman
# ===============================================
# Image de base : PostgreSQL 15 Alpine
# Extensions : pg_partman pour le partitionnement automatique
# ===============================================

FROM postgres:15-alpine

# Metadata
LABEL maintainer="AI-Agent Team"
LABEL description="PostgreSQL 15 with pg_partman extension for automatic partition management"
LABEL version="1.0"

# Variables d'environnement pour la compilation
ENV PARTMAN_VERSION=5.0.1

# Installation des dépendances nécessaires pour compiler pg_partman
# + cron pour la maintenance automatique
RUN apk add --no-cache --virtual .build-deps \
    build-base \
    git \
    postgresql-dev \
    && apk add --no-cache \
    postgresql-contrib \
    dcron \
    bash

# Télécharger et compiler pg_partman
# NO_BGW=1 désactive le background worker qui nécessite clang-19
RUN cd /tmp \
    && git clone --branch v${PARTMAN_VERSION} --depth 1 https://github.com/pgpartman/pg_partman.git \
    && cd pg_partman \
    && make NO_BGW=1 \
    && make NO_BGW=1 install \
    && cd / \
    && rm -rf /tmp/pg_partman


# Nettoyer les dépendances de build pour réduire la taille de l'image
RUN apk del .build-deps

# Créer le répertoire pour les scripts d'initialisation personnalisés
RUN mkdir -p /docker-entrypoint-initdb.d

# Copier les scripts de maintenance
COPY maintenance-partman.sh /usr/local/bin/maintenance-partman.sh
COPY cron-partman-maintenance /etc/crontabs/postgres

# Rendre les scripts exécutables
RUN chmod +x /usr/local/bin/maintenance-partman.sh

# Créer le répertoire pour les logs de maintenance
RUN mkdir -p /var/log/postgresql && \
    chown -R postgres:postgres /var/log/postgresql

# Exposer le port PostgreSQL
EXPOSE 5432

# Le point d'entrée par défaut de postgres:15-alpine sera utilisé
# Il exécutera automatiquement les scripts dans /docker-entrypoint-initdb.d


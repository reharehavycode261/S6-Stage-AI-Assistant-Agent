-- ===============================================
-- SCRIPT 01: Installation et activation de pg_partman
-- ===============================================
-- Description: Active l'extension pg_partman et crée le schéma nécessaire
-- Exécution: Automatique au démarrage du container PostgreSQL
-- ===============================================

\echo '=========================================='
\echo '🔧 Installation de pg_partman'
\echo '=========================================='

-- Créer l'extension pg_partman dans le schéma partman
CREATE SCHEMA IF NOT EXISTS partman;

-- Activer l'extension pg_partman
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;

-- Vérifier l'installation
\echo '✅ Extension pg_partman installée avec succès'

-- Afficher la version de pg_partman
SELECT extversion AS "Version pg_partman" 
FROM pg_extension 
WHERE extname = 'pg_partman';

\echo '=========================================='
\echo '✅ pg_partman est prêt à être utilisé'
\echo '=========================================='


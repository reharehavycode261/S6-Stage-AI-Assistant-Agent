-- Migration: Ajout du champ user_email dans human_validations
-- Date: 2025-10-31
-- Mise à jour: 2025-11-03
-- Description: Permet de stocker l'email de l'utilisateur pour les notifications Slack

-- Ajouter la colonne user_email
ALTER TABLE human_validations 
ADD COLUMN IF NOT EXISTS user_email VARCHAR(100);

-- Créer un index pour les recherches par email
CREATE INDEX IF NOT EXISTS idx_human_validations_user_email 
ON human_validations(user_email);

-- Commentaire pour documentation
COMMENT ON COLUMN human_validations.user_email IS 'Email de l''utilisateur pour lookup Slack par email';

-- Note: L'email est utilisé pour trouver l'ID Slack de l'utilisateur
-- 1. Extraire le creator ID depuis l'update Monday.com
-- 2. Faire un appel à l'API Monday.com pour récupérer l'email de l'utilisateur
-- 3. Utiliser l'email pour lookup l'ID Slack via l'API Slack
-- 4. Stocker l'email lors de la création de la validation


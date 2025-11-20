#!/bin/bash
# Wrapper pour la maintenance pg_partman via cron

# Récupérer le répertoire du script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="${SCRIPT_DIR}/logs"
MAINTENANCE_SCRIPT="${SCRIPT_DIR}/maintain_webhook_partitions.sh"

# Créer le fichier de log avec timestamp
TIMESTAMP=$(date "+%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/partman_maintenance_${TIMESTAMP}.log"

# Exécuter la maintenance
echo "==================================================================" >> "$LOG_FILE"
echo "Maintenance pg_partman - $(date)" >> "$LOG_FILE"
echo "==================================================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

"$MAINTENANCE_SCRIPT" >> "$LOG_FILE" 2>&1

# Vérifier le statut
if [ $? -eq 0 ]; then
    echo "" >> "$LOG_FILE"
    echo "✅ Maintenance réussie - $(date)" >> "$LOG_FILE"
    exit 0
else
    echo "" >> "$LOG_FILE"
    echo "❌ Erreur lors de la maintenance - $(date)" >> "$LOG_FILE"
    exit 1
fi

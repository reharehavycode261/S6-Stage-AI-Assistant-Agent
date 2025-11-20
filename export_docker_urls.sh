#!/bin/bash
# Script pour exporter les variables d'environnement Docker

echo "====================================="
echo "🚀 Export URLs Docker Services"
echo "====================================="
echo

# Export RabbitMQ URL
export BROKER_URL="amqp://ai_agent_user:secure_password_123@localhost:5672/ai_agent"
echo "✅ BROKER_URL exported: $BROKER_URL"

# Export PostgreSQL URL
export DATABASE_URL="postgresql://admin:password@localhost:5432/ai_agent_admin"
echo "✅ DATABASE_URL exported: $DATABASE_URL"

# Export Redis URL
export REDIS_URL="redis://localhost:6379/0"
echo "✅ REDIS_URL exported: $REDIS_URL"

echo
echo "====================================="
echo "📋 Variables exportées:"
echo "====================================="
echo "BROKER_URL=$BROKER_URL"
echo "DATABASE_URL=$DATABASE_URL"
echo "REDIS_URL=$REDIS_URL"
echo
echo "💡 Pour utiliser ces variables dans votre shell actuel:"
echo "   source ./export_docker_urls.sh"
echo
echo "💡 Ou ajoutez-les à votre .env:"
echo "   echo 'REDIS_URL=$REDIS_URL' >> .env"
echo






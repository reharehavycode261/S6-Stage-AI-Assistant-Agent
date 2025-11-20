from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime
import json

from services.monitoring_service import monitoring_dashboard
from utils.logger import get_logger

logger = get_logger(__name__)

monitoring_router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@monitoring_router.get("/dashboard", response_class=HTMLResponse)
async def get_monitoring_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI-Agent Dashboard - Monitoring RabbitMQ</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://unpkg.com/chart.js"></script>
        <style>
            .metric-card { @apply bg-white rounded-lg shadow p-6 border; }
            .metric-value { @apply text-3xl font-bold; }
            .metric-label { @apply text-gray-600 text-sm; }
            .status-active { @apply bg-green-100 text-green-800; }
            .status-failed { @apply bg-red-100 text-red-800; }
            .status-completed { @apply bg-blue-100 text-blue-800; }
            .nav-link { @apply px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors; }
        </style>
    </head>
    <body class="bg-gray-50">
        <div class="container mx-auto px-4 py-8">
            <!-- Header avec navigation -->
            <div class="mb-8 flex justify-between items-center">
                <div>
                    <h1 class="text-3xl font-bold text-gray-900">🤖 AI-Agent Dashboard</h1>
                    <p class="text-gray-600">Monitoring des workflows avec architecture RabbitMQ</p>
                </div>
                <div class="flex gap-4">
                    <a href="http://localhost:15672" target="_blank" class="nav-link">
                        🐰 RabbitMQ Management
                    </a>
                    <a href="http://localhost:5555" target="_blank" class="nav-link">
                        🌺 Flower (Celery)
                    </a>
                </div>
            </div>
            
            <!-- Statut Architecture -->
            <div class="bg-white rounded-lg shadow mb-8 p-6">
                <h2 class="text-xl font-semibold mb-4">🏗️ Architecture RabbitMQ</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="text-center p-4 bg-green-50 rounded">
                        <div class="text-2xl">🐰</div>
                        <div class="font-semibold">RabbitMQ Broker</div>
                        <div class="text-sm text-gray-600">Message queuing</div>
                    </div>
                    <div class="text-center p-4 bg-blue-50 rounded">
                        <div class="text-2xl">⚙️</div>
                        <div class="font-semibold">Celery Workers</div>
                        <div class="text-sm text-gray-600">Background processing</div>
                    </div>
                    <div class="text-center p-4 bg-purple-50 rounded">
                        <div class="text-2xl">🗄️</div>
                        <div class="font-semibold">PostgreSQL</div>
                        <div class="text-sm text-gray-600">Results backend</div>
                    </div>
                </div>
            </div>
            
            <!-- Métriques Business AI-Agent -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div class="metric-card">
                    <div class="metric-value text-blue-600" id="active-workflows">0</div>
                    <div class="metric-label">Workflows Actifs</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value text-green-600" id="completed-today">0</div>
                    <div class="metric-label">Complétés Aujourd'hui</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value text-purple-600" id="ai-costs">$0.00</div>
                    <div class="metric-label">Coûts IA (24h)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value text-orange-600" id="success-rate">100%</div>
                    <div class="metric-label">Taux de Succès</div>
                </div>
            </div>
            
            <!-- Workflows en cours -->
            <div class="bg-white rounded-lg shadow mb-8">
                <div class="px-6 py-4 border-b">
                    <h2 class="text-xl font-semibold">🔄 Workflows en Cours</h2>
                </div>
                <div class="p-6">
                    <div id="active-workflows-list" class="space-y-4">
                        <p class="text-gray-500">Aucun workflow actif</p>
                    </div>
                </div>
            </div>
            
            <!-- Queues RabbitMQ Summary -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4">📊 Queues RabbitMQ</h3>
                    <div class="space-y-3">
                        <div class="flex justify-between">
                            <span>🚀 webhooks</span>
                            <span id="queue-webhooks" class="font-mono">0</span>
                        </div>
                        <div class="flex justify-between">
                            <span>⚙️ workflows</span>
                            <span id="queue-workflows" class="font-mono">0</span>
                        </div>
                        <div class="flex justify-between">
                            <span>🤖 ai_generation</span>
                            <span id="queue-ai" class="font-mono">0</span>
                        </div>
                        <div class="flex justify-between">
                            <span>🧪 tests</span>
                            <span id="queue-tests" class="font-mono">0</span>
                        </div>
                        <div class="flex justify-between">
                            <span>💀 dlq (dead letters)</span>
                            <span id="queue-dlq" class="font-mono text-red-600">0</span>
                        </div>
                    </div>
                    <div class="mt-4 text-sm text-gray-500">
                        <a href="http://localhost:15672" target="_blank" class="text-blue-600 hover:underline">
                            → Voir détails dans RabbitMQ Management
                        </a>
                    </div>
                </div>
                
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4">💰 Coûts IA par Provider</h3>
                    <canvas id="costs-chart" width="400" height="300"></canvas>
                </div>
            </div>
            
            <!-- Logs temps réel -->
            <div class="bg-white rounded-lg shadow">
                <div class="px-6 py-4 border-b flex justify-between items-center">
                    <h2 class="text-xl font-semibold">📋 Logs AI-Agent</h2>
                    <div class="text-sm text-gray-500">
                        <span class="inline-block w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                        Temps réel via WebSocket
                    </div>
                </div>
                <div class="p-6">
                    <div id="logs-container" class="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm h-64 overflow-y-auto">
                        <div>🚀 AI-Agent Dashboard initialisé avec architecture RabbitMQ...</div>
                        <div>🐰 RabbitMQ Management UI disponible sur :15672</div>
                        <div>🌺 Flower (Celery) disponible sur :5555</div>
                    </div>
                </div>
            </div>
            
            <!-- Alertes flottantes -->
            <div id="alerts-container" class="fixed top-4 right-4 space-y-2 z-50"></div>
        </div>
        
        <script>
            // WebSocket pour les mises à jour temps réel
            const ws = new WebSocket(`ws://${window.location.host}/monitoring/ws`);
            
            ws.onopen = function(event) {
                addLog('✅ WebSocket connecté - Dashboard RabbitMQ');
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onclose = function(event) {
                addLog('❌ WebSocket déconnecté - Reconnexion dans 5s...');
                setTimeout(() => location.reload(), 5000);
            };
            
            // Traitement des messages
            function handleWebSocketMessage(data) {
                switch(data.type) {
                    case 'initial_data':
                        updateDashboard(data.data);
                        break;
                    case 'workflow_update':
                        updateWorkflow(data.workflow_id, data.data);
                        break;
                    case 'queue_stats':
                        updateQueueStats(data.data);
                        break;
                    case 'alert':
                        showAlert(data);
                        break;
                }
            }
            
            function updateDashboard(data) {
                const stats = data.real_time_stats || {};
                
                document.getElementById('active-workflows').textContent = stats.active_workflows || 0;
                document.getElementById('completed-today').textContent = stats.completed_today || 0;
                document.getElementById('ai-costs').textContent = '$' + (stats.ai_costs_today || 0).toFixed(2);
                document.getElementById('success-rate').textContent = (stats.success_rate || 100).toFixed(1) + '%';
                
                updateActiveWorkflows(data.active_workflows || {});
                addLog('📊 Dashboard mis à jour');
            }
            
            function updateActiveWorkflows(workflows) {
                const container = document.getElementById('active-workflows-list');
                
                if (Object.keys(workflows).length === 0) {
                    container.innerHTML = '<p class="text-gray-500">Aucun workflow actif</p>';
                    return;
                }
                
                container.innerHTML = Object.entries(workflows).map(([id, workflow]) => `
                    <div class="border rounded-lg p-4">
                        <div class="flex justify-between items-start mb-2">
                            <h4 class="font-semibold text-sm">${id}</h4>
                            <span class="status-active px-2 py-1 rounded text-xs">${workflow.current_step || 'En cours'}</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2 mb-2">
                            <div class="bg-blue-600 h-2 rounded-full" style="width: ${workflow.progress || 0}%"></div>
                        </div>
                        <div class="text-sm text-gray-600">
                            Progrès: ${workflow.progress || 0}% • 
                            Queue: ${workflow.queue || 'N/A'} •
                            Durée: ${workflow.duration || 0}s
                        </div>
                    </div>
                `).join('');
            }
            
            function updateQueueStats(queues) {
                const queueIds = ['webhooks', 'workflows', 'ai', 'tests', 'dlq'];
                queueIds.forEach(queueId => {
                    const element = document.getElementById(`queue-${queueId}`);
                    if (element && queues[queueId] !== undefined) {
                        element.textContent = queues[queueId];
                        element.className = queues[queueId] > 0 ? 'font-mono text-orange-600' : 'font-mono';
                    }
                });
            }
            
            function showAlert(alert) {
                const alertDiv = document.createElement('div');
                alertDiv.className = 'bg-red-500 text-white p-4 rounded-lg shadow-lg max-w-sm';
                alertDiv.innerHTML = `
                    <div class="flex justify-between items-start">
                        <div>
                            <h4 class="font-bold">🚨 ${alert.rule}</h4>
                            <p class="text-sm">${alert.message}</p>
                        </div>
                        <button onclick="this.parentElement.parentElement.remove()" class="text-white">×</button>
                    </div>
                `;
                
                document.getElementById('alerts-container').appendChild(alertDiv);
                setTimeout(() => alertDiv.remove(), 10000);
                addLog(`🚨 ALERTE: ${alert.rule}`);
            }
            
            function addLog(message) {
                const container = document.getElementById('logs-container');
                const timestamp = new Date().toLocaleTimeString();
                const logDiv = document.createElement('div');
                logDiv.textContent = `[${timestamp}] ${message}`;
                
                container.appendChild(logDiv);
                container.scrollTop = container.scrollHeight;
                
                // Garder seulement les 50 derniers logs
                while (container.children.length > 50) {
                    container.removeChild(container.firstChild);
                }
            }
            
            // Initialisation des graphiques
            let costsChart;
            
            function initCharts() {
                const costsCtx = document.getElementById('costs-chart').getContext('2d');
                costsChart = new Chart(costsCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Claude', 'OpenAI'],
                        datasets: [{
                            data: [0, 0],
                            backgroundColor: [
                                'rgba(236, 72, 153, 0.8)',
                                'rgba(34, 197, 94, 0.8)'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false
                    }
                });
            }
            
            document.addEventListener('DOMContentLoaded', initCharts);
            
            // Mise à jour périodique des stats
            setInterval(() => {
                addLog('🔄 Mise à jour périodique...');
            }, 30000);
        </script>
    </body>
    </html>
    """


@monitoring_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    monitoring_dashboard.connected_clients.append(websocket)
    
    try:
        initial_data = await monitoring_dashboard.get_real_time_stats()
        await websocket.send_text(json.dumps({
            "type": "initial_data",
            "data": initial_data
        }))
        
        logger.info("🔌 Client WebSocket connecté au monitoring RabbitMQ")

        while True:
            try:
                message = await websocket.receive_text()

                if message == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"Erreur WebSocket monitoring: {e}")
    finally:
        if websocket in monitoring_dashboard.connected_clients:
            monitoring_dashboard.connected_clients.remove(websocket)
        logger.info("🔌 Client WebSocket déconnecté du monitoring")


@monitoring_router.get("/stats")
async def get_monitoring_stats():
    """Retourne les statistiques actuelles du monitoring."""
    try:
        stats = await monitoring_dashboard.get_real_time_stats()
        return {
            "success": True,
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur récupération stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@monitoring_router.get("/health")
async def monitoring_health():
    return {
        "status": "healthy",
        "monitoring": "active",
        "rabbitmq_integration": True,
        "websocket_clients": len(monitoring_dashboard.connected_clients),
        "timestamp": datetime.now().isoformat()
    } 
#!/usr/bin/env python3
"""
Script pour vérifier que les données entrent bien en temps réel dans la base de données.
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


async def check_realtime_data():
    """Vérifie les données récentes dans toutes les tables."""
    settings = get_settings()
    
    try:
        # Connexion à la base
        conn = await asyncpg.connect(settings.database_url)
        logger.info("✅ Connexion à la base établie")
        
        # Période à vérifier (dernières 24h)
        since = datetime.now() - timedelta(hours=24)
        
        print("\n" + "="*60)
        print("📊 RAPPORT DE DONNÉES EN TEMPS RÉEL")
        print("="*60)
        
        # 1. Webhooks reçus
        webhooks = await conn.fetch("""
            SELECT source, event_type, processed, received_at
            FROM webhook_events 
            WHERE received_at >= $1 
            ORDER BY received_at DESC LIMIT 10
        """, since)
        
        print(f"\n🌐 WEBHOOKS RÉCENTS ({len(webhooks)} derniers):")
        for webhook in webhooks:
            status = "✅ Traité" if webhook['processed'] else "⏳ En attente"
            print(f"  • {webhook['received_at'].strftime('%H:%M:%S')} - {webhook['source']} - {webhook['event_type']} - {status}")
        
        # 2. Tâches créées
        tasks = await conn.fetch("""
            SELECT tasks_id, title, internal_status, created_at, monday_item_id
            FROM tasks 
            WHERE created_at >= $1 
            ORDER BY created_at DESC LIMIT 10
        """, since)
        
        print(f"\n📋 TÂCHES CRÉÉES ({len(tasks)} récentes):")
        for task in tasks:
            print(f"  • #{task['tasks_id']} - {task['title'][:50]}... - {task['internal_status']} - Monday ID: {task['monday_item_id']}")
        
        # 3. Runs de workflow
        runs = await conn.fetch("""
            SELECT tr.tasks_runs_id, tr.status, tr.current_node, tr.progress_percentage, 
                   tr.started_at, t.title
            FROM task_runs tr
            JOIN tasks t ON tr.task_id = t.tasks_id
            WHERE tr.started_at >= $1 
            ORDER BY tr.started_at DESC LIMIT 10
        """, since)
        
        print(f"\n🚀 EXÉCUTIONS DE WORKFLOW ({len(runs)} récentes):")
        for run in runs:
            progress = f"{run['progress_percentage']}%" if run['progress_percentage'] else "0%"
            print(f"  • Run #{run['tasks_runs_id']} - {run['title'][:40]}... - {run['status']} - {run['current_node']} ({progress})")
        
        # 4. Étapes des runs
        steps = await conn.fetch("""
            SELECT rs.node_name, rs.status, rs.duration_seconds, rs.started_at, t.title
            FROM run_steps rs
            JOIN task_runs tr ON rs.task_run_id = tr.tasks_runs_id
            JOIN tasks t ON tr.task_id = t.tasks_id
            WHERE rs.started_at >= $1 
            ORDER BY rs.started_at DESC LIMIT 15
        """, since)
        
        print(f"\n📍 ÉTAPES EXÉCUTÉES ({len(steps)} récentes):")
        for step in steps:
            duration = f"{step['duration_seconds']}s" if step['duration_seconds'] else "En cours"
            print(f"  • {step['node_name']} - {step['status']} - {duration} - {step['title'][:30]}...")
        
        # 5. Interactions IA
        ai_interactions = await conn.fetch("""
            SELECT ai.ai_provider, ai.model_name, ai.latency_ms, ai.created_at, t.title
            FROM ai_interactions ai
            JOIN run_steps rs ON ai.run_step_id = rs.run_steps_id
            JOIN task_runs tr ON rs.task_run_id = tr.tasks_runs_id
            JOIN tasks t ON tr.task_id = t.tasks_id
            WHERE ai.created_at >= $1 
            ORDER BY ai.created_at DESC LIMIT 10
        """, since)
        
        print(f"\n🤖 INTERACTIONS IA ({len(ai_interactions)} récentes):")
        for ai in ai_interactions:
            latency = f"{ai['latency_ms']}ms" if ai['latency_ms'] else "N/A"
            print(f"  • {ai['ai_provider']} - {ai['model_name']} - {latency} - {ai['title'][:30]}...")
        
        # 6. Générations de code
        code_gens = await conn.fetch("""
            SELECT provider, generation_type, response_time_ms, generated_at, t.title
            FROM ai_code_generations acg
            JOIN task_runs tr ON acg.task_run_id = tr.tasks_runs_id
            JOIN tasks t ON tr.task_id = t.tasks_id
            WHERE acg.generated_at >= $1 
            ORDER BY acg.generated_at DESC LIMIT 10
        """, since)
        
        print(f"\n💻 GÉNÉRATIONS DE CODE ({len(code_gens)} récentes):")
        for gen in code_gens:
            time_ms = f"{gen['response_time_ms']}ms" if gen['response_time_ms'] else "N/A"
            print(f"  • {gen['provider']} - {gen['generation_type']} - {time_ms} - {gen['title'][:30]}...")
        
        # 7. Résultats de tests
        test_results = await conn.fetch("""
            SELECT passed, tests_total, tests_passed, tests_failed, executed_at, t.title
            FROM test_results tr_test
            JOIN task_runs tr ON tr_test.task_run_id = tr.tasks_runs_id
            JOIN tasks t ON tr.task_id = t.tasks_id
            WHERE tr_test.executed_at >= $1 
            ORDER BY tr_test.executed_at DESC LIMIT 10
        """, since)
        
        print(f"\n🧪 RÉSULTATS DE TESTS ({len(test_results)} récents):")
        for test in test_results:
            status = "✅ Réussi" if test['passed'] else "❌ Échoué"
            print(f"  • {status} - {test['tests_passed']}/{test['tests_total']} tests - {test['title'][:30]}...")
        
        # 8. Pull Requests
        prs = await conn.fetch("""
            SELECT github_pr_number, pr_title, pr_status, created_at, t.title
            FROM pull_requests pr
            JOIN tasks t ON pr.task_id = t.tasks_id
            WHERE pr.created_at >= $1 
            ORDER BY pr.created_at DESC LIMIT 10
        """, since)
        
        print(f"\n🔀 PULL REQUESTS ({len(prs)} récentes):")
        for pr in prs:
            print(f"  • PR #{pr['github_pr_number']} - {pr['pr_status']} - {pr['pr_title'][:40]}...")
        
        # 9. Logs applicatifs récents
        app_logs = await conn.fetch("""
            SELECT level, source_component, action, message, ts
            FROM application_logs 
            WHERE ts >= $1 
            ORDER BY ts DESC LIMIT 15
        """, since)
        
        print(f"\n📝 LOGS APPLICATIFS ({len(app_logs)} récents):")
        for log in app_logs:
            emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}.get(log['level'], "📝")
            print(f"  • {emoji} {log['ts'].strftime('%H:%M:%S')} - {log['source_component']} - {log['action']} - {log['message'][:60]}...")
        
        # 10. Métriques de performance
        metrics = await conn.fetch("""
            SELECT total_duration_seconds, total_ai_calls, total_ai_cost, recorded_at, t.title
            FROM performance_metrics pm
            JOIN tasks t ON pm.task_id = t.tasks_id
            WHERE pm.recorded_at >= $1 
            ORDER BY pm.recorded_at DESC LIMIT 5
        """, since)
        
        print(f"\n📊 MÉTRIQUES DE PERFORMANCE ({len(metrics)} récentes):")
        for metric in metrics:
            duration = f"{metric['total_duration_seconds']}s" if metric['total_duration_seconds'] else "N/A"
            cost = f"${metric['total_ai_cost']:.4f}" if metric['total_ai_cost'] else "$0.00"
            print(f"  • Durée: {duration} - Appels IA: {metric['total_ai_calls']} - Coût: {cost} - {metric['title'][:30]}...")
        
        # Statistiques générales
        print("\n" + "="*60)
        print("📈 STATISTIQUES GÉNÉRALES (24h)")
        print("="*60)
        
        stats = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM webhook_events WHERE received_at >= $1) as webhooks_count,
                (SELECT COUNT(*) FROM tasks WHERE created_at >= $1) as tasks_count,
                (SELECT COUNT(*) FROM task_runs WHERE started_at >= $1) as runs_count,
                (SELECT COUNT(*) FROM run_steps WHERE started_at >= $1) as steps_count,
                (SELECT COUNT(*) FROM ai_interactions WHERE created_at >= $1) as ai_calls_count,
                (SELECT COUNT(*) FROM test_results WHERE executed_at >= $1) as tests_count,
                (SELECT COUNT(*) FROM pull_requests WHERE created_at >= $1) as prs_count
        """, since)
        
        print(f"🌐 Webhooks reçus: {stats['webhooks_count']}")
        print(f"📋 Tâches créées: {stats['tasks_count']}")
        print(f"🚀 Runs lancés: {stats['runs_count']}")
        print(f"📍 Étapes exécutées: {stats['steps_count']}")
        print(f"🤖 Appels IA: {stats['ai_calls_count']}")
        print(f"🧪 Tests executés: {stats['tests_count']}")
        print(f"🔀 PRs créées: {stats['prs_count']}")
        
        # Vérifier la "fraîcheur" des données
        latest_activity = await conn.fetchval("""
            SELECT MAX(received_at) FROM webhook_events
        """)
        
        if latest_activity:
            age = datetime.now() - latest_activity.replace(tzinfo=None)
            if age.total_seconds() < 3600:  # Moins d'1h
                print(f"\n✅ Système actif - Dernière activité: il y a {int(age.total_seconds()//60)} minutes")
            else:
                print(f"\n⚠️ Système inactif - Dernière activité: {latest_activity.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("\n❌ Aucune activité détectée")
        
        print("\n" + "="*60)
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification: {e}")
        print(f"\n❌ Erreur: {e}")


if __name__ == "__main__":
    asyncio.run(check_realtime_data()) 
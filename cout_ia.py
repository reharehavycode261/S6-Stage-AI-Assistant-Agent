#!/usr/bin/env python3
"""Script pour afficher les coûts IA - Version qui fonctionne avec le schéma réel."""

import asyncio
import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from admin.backend.database import get_db_connection
    from utils.logger import get_logger
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    print("💡 Assurez-vous d'être dans le bon répertoire et que les dépendances sont installées")
    sys.exit(1)

logger = get_logger(__name__)


def print_header(title: str):
    """Affiche un header stylé."""
    print("\n" + "="*60)
    print(f"💰 {title.upper()}")
    print("="*60)


def print_section(title: str):
    """Affiche un titre de section."""
    print(f"\n📊 {title}")
    print("-" * 40)


def format_cost(cost: float) -> str:
    """Formate un coût en USD."""
    if cost < 0.001:
        return f"${cost:.6f}"
    elif cost < 0.01:
        return f"${cost:.4f}"
    else:
        return f"${cost:.2f}"


def format_tokens(tokens: int) -> str:
    """Formate le nombre de tokens."""
    if tokens >= 1_000_000:
        return f"{tokens/1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens/1_000:.1f}K"
    else:
        return str(tokens)


async def show_table_info():
    """Affiche les informations de base sur la table."""
    print_section("INFORMATION TABLE AI_USAGE_LOGS")
    
    try:
        conn = await get_db_connection()
        
        # Compter les enregistrements
        count_result = await conn.fetchrow('SELECT COUNT(*) as count FROM ai_usage_logs')
        total_records = count_result['count']
        
        if total_records == 0:
            print("💤 Aucun enregistrement trouvé")
            print("💡 Lancez quelques workflows pour voir les données apparaître")
            await conn.close()
            return
        
        # Statistiques générales
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_calls,
                SUM(estimated_cost) as total_cost,
                SUM(total_tokens) as total_tokens,
                MIN(timestamp) as first_call,
                MAX(timestamp) as last_call,
                COUNT(DISTINCT provider) as provider_count,
                COUNT(DISTINCT workflow_id) as workflow_count
            FROM ai_usage_logs
        """)
        
        print(f"📊 Total enregistrements: {stats['total_calls']:,}")
        print(f"💰 Coût total: {format_cost(stats['total_cost'] or 0)}")
        print(f"🔤 Tokens total: {format_tokens(stats['total_tokens'] or 0)}")
        print(f"🗓️ Premier appel: {stats['first_call']}")
        print(f"🗓️ Dernier appel: {stats['last_call']}")
        print(f"🤖 Providers: {stats['provider_count']}")
        print(f"⚡ Workflows: {stats['workflow_count']}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


async def show_daily_stats():
    """Affiche les coûts d'aujourd'hui."""
    print_section("COÛTS D'AUJOURD'HUI")
    
    try:
        conn = await get_db_connection()
        
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as calls,
                SUM(estimated_cost) as cost,
                SUM(total_tokens) as tokens
            FROM ai_usage_logs 
            WHERE DATE(timestamp) = CURRENT_DATE
        """)
        
        if not stats['calls']:
            print("💤 Aucune activité aujourd'hui")
        else:
            print(f"💰 Coût total: {format_cost(stats['cost'] or 0)}")
            print(f"📞 Appels API: {stats['calls']:,}")
            print(f"🔤 Tokens: {format_tokens(stats['tokens'] or 0)}")
            
            # Par provider
            providers = await conn.fetch("""
                SELECT 
                    provider,
                    COUNT(*) as calls,
                    SUM(estimated_cost) as cost
                FROM ai_usage_logs 
                WHERE DATE(timestamp) = CURRENT_DATE
                GROUP BY provider
                ORDER BY 
                    CASE provider 
                        WHEN 'openai' THEN 1 
                        WHEN 'claude' THEN 2 
                        ELSE 3 
                    END, cost DESC
            """)
            
            for p in providers:
                # Ajouter un indicateur pour le provider principal
                primary_indicator = " 🥇" if p['provider'] == 'openai' else " 🥈" if p['provider'] == 'claude' else ""
                print(f"  📊 {p['provider']}{primary_indicator}: {format_cost(p['cost'] or 0)} ({p['calls']} appels)")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


async def show_monthly_stats():
    """Affiche les coûts du mois en cours."""
    print_section("COÛTS DU MOIS EN COURS")
    
    try:
        conn = await get_db_connection()
        
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as calls,
                SUM(estimated_cost) as cost,
                SUM(total_tokens) as tokens
            FROM ai_usage_logs 
            WHERE EXTRACT(YEAR FROM timestamp) = EXTRACT(YEAR FROM CURRENT_DATE)
            AND EXTRACT(MONTH FROM timestamp) = EXTRACT(MONTH FROM CURRENT_DATE)
        """)
        
        if not stats['calls']:
            print("💤 Aucune activité ce mois")
        else:
            cost = stats['cost'] or 0
            calls = stats['calls']
            tokens = stats['tokens'] or 0
            avg_cost = cost / calls if calls > 0 else 0
            
            print(f"💰 Coût total: {format_cost(cost)}")
            print(f"📞 Appels API: {calls:,}")
            print(f"🔤 Tokens: {format_tokens(tokens)}")
            print(f"📊 Coût moyen/appel: {format_cost(avg_cost)}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


async def show_provider_stats():
    """Affiche les statistiques par provider."""
    print_section("STATISTIQUES PAR PROVIDER")
    
    try:
        conn = await get_db_connection()
        
        providers = await conn.fetch("""
            SELECT 
                provider,
                model,
                COUNT(*) as calls,
                SUM(estimated_cost) as cost,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                AVG(duration_seconds) as avg_duration,
                COUNT(CASE WHEN success THEN 1 END) as successful_calls
            FROM ai_usage_logs
            GROUP BY provider, model
            ORDER BY 
                CASE provider 
                    WHEN 'openai' THEN 1 
                    WHEN 'claude' THEN 2 
                    ELSE 3 
                END, cost DESC
        """)
        
        if not providers:
            print("💤 Aucune donnée trouvée")
        else:
            for p in providers:
                success_rate = (p['successful_calls'] / p['calls'] * 100) if p['calls'] > 0 else 0
                avg_duration = p['avg_duration'] or 0
                
                # Ajouter un indicateur pour le provider principal
                primary_indicator = " 🥇" if p['provider'] == 'openai' else " 🥈" if p['provider'] == 'claude' else ""
                print(f"🤖 {p['provider']} ({p['model']}){primary_indicator}")
                print(f"   💰 {format_cost(p['cost'] or 0)} | {p['calls']} appels | {success_rate:.1f}% succès")
                print(f"   📝 {format_tokens(p['input_tokens'] or 0)} in + {format_tokens(p['output_tokens'] or 0)} out")
                print(f"   ⏱️ {avg_duration:.1f}s moyen")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


async def show_recent_activity():
    """Affiche l'activité récente."""
    print_section("ACTIVITÉ RÉCENTE (20 DERNIÈRES)")
    
    try:
        conn = await get_db_connection()
        
        recent = await conn.fetch("""
            SELECT 
                timestamp,
                provider,
                model,
                operation,
                estimated_cost,
                total_tokens,
                duration_seconds,
                success
            FROM ai_usage_logs 
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        
        if not recent:
            print("💤 Aucune activité récente")
        else:
            for r in recent:
                time_str = r['timestamp'].strftime('%H:%M:%S') if r['timestamp'] else 'N/A'
                provider = r['provider']
                operation = r['operation'] or 'unknown'
                cost = r['estimated_cost'] or 0
                tokens = r['total_tokens'] or 0
                duration = r['duration_seconds'] or 0
                success = "✅" if r['success'] else "❌"
                
                print(f"{time_str} {success} {provider} {operation}: {format_cost(cost)} ({format_tokens(tokens)}, {duration:.1f}s)")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


async def show_expensive_workflows():
    """Affiche les workflows les plus coûteux."""
    print_section("TOP WORKFLOWS COÛTEUX")
    
    try:
        conn = await get_db_connection()
        
        workflows = await conn.fetch("""
            SELECT 
                workflow_id,
                COUNT(*) as calls,
                SUM(estimated_cost) as cost,
                SUM(total_tokens) as tokens,
                MIN(timestamp) as first_call,
                MAX(timestamp) as last_call
            FROM ai_usage_logs 
            GROUP BY workflow_id
            ORDER BY cost DESC
            LIMIT 10
        """)
        
        if not workflows:
            print("💤 Aucun workflow trouvé")
        else:
            for i, w in enumerate(workflows, 1):
                print(f"{i:2d}. {w['workflow_id']}")
                print(f"    💰 {format_cost(w['cost'] or 0)} ({w['calls']} appels, {format_tokens(w['tokens'] or 0)} tokens)")
                if w['first_call']:
                    print(f"    🗓️ {w['first_call'].strftime('%d/%m %H:%M')} → {w['last_call'].strftime('%d/%m %H:%M')}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


async def show_provider_configuration():
    """Affiche la configuration actuelle des providers."""
    print_section("CONFIGURATION PROVIDERS IA")
    
    try:
        # Import ici pour éviter les problèmes de dépendance
        from config.settings import get_settings
        from tools.ai_engine_hub import AIEngineHub, TaskType
        
        settings = get_settings()
        hub = AIEngineHub()
        
        print(f"🥇 Provider principal configuré: {settings.default_ai_provider}")
        print()
        print("📋 Priorités par type de tâche:")
        
        task_types = [
            TaskType.CODE_GENERATION,
            TaskType.CODE_REVIEW,
            TaskType.DEBUGGING,
            TaskType.DOCUMENTATION,
            TaskType.TESTING,
            TaskType.REFACTORING,
            TaskType.ANALYSIS
        ]
        
        for task_type in task_types:
            preferences = hub.task_preferences[task_type]
            primary = preferences[0].value
            secondary = preferences[1].value
            primary_icon = "🥇" if primary == "openai" else "🥈"
            secondary_icon = "🥈" if secondary == "claude" else "🥇"
            
            print(f"  {task_type.value:15} → {primary_icon} {primary:6} / {secondary_icon} {secondary:6}")
        
    except Exception as e:
        print(f"❌ Erreur configuration: {e}")


async def main():
    """Fonction principale."""
    print_header("MONITORING COÛTS IA - AI AGENT")
    print("🔄 Récupération des données depuis la base...")
    
    try:
        await show_provider_configuration()
        await show_table_info()
        await show_daily_stats()
        await show_monthly_stats()
        await show_provider_stats()
        await show_recent_activity()
        await show_expensive_workflows()
        
        print_section("RÉSUMÉ")
        print("✅ Analyse terminée avec succès")
        print("🥇 Provider principal: OpenAI (GPT-4)")
        print("🥈 Provider secondaire: Claude (Sonnet)")
        print("💡 Relancez après avoir exécuté des workflows pour voir l'évolution")
        
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        logger.error(f"Erreur dans main(): {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du monitoring...")
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        sys.exit(1) 
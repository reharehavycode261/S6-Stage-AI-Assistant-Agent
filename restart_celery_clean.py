#!/usr/bin/env python3
"""
Script pour redémarrer Celery proprement après les corrections.

Ce script :
1. Arrête Celery gracieusement
2. Nettoie les tâches en cours
3. Redémarre avec les nouvelles corrections
"""

import os
import sys
import subprocess
import time
import signal
import psutil
from typing import List

def find_celery_processes() -> List[psutil.Process]:
    """Trouve tous les processus Celery en cours."""
    celery_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline'] and any('celery' in cmd for cmd in proc.info['cmdline']):
                celery_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return celery_processes

def stop_celery_gracefully():
    """Arrête Celery gracieusement."""
    print("🛑 Arrêt de Celery...")
    
    # Trouver les processus Celery
    celery_procs = find_celery_processes()
    
    if not celery_procs:
        print("✅ Aucun processus Celery en cours")
        return True
    
    print(f"🔍 {len(celery_procs)} processus Celery trouvés")
    
    # Envoyer SIGTERM pour arrêt gracieux
    for proc in celery_procs:
        try:
            print(f"   📤 Envoi SIGTERM à PID {proc.pid}")
            proc.send_signal(signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"   ⚠️ Impossible d'arrêter PID {proc.pid}: {e}")
    
    # Attendre jusqu'à 30 secondes pour arrêt gracieux
    print("⏳ Attente d'arrêt gracieux (30s max)...")
    
    for i in range(30):
        remaining_procs = find_celery_processes()
        if not remaining_procs:
            print("✅ Tous les processus Celery arrêtés")
            return True
        
        time.sleep(1)
        if i % 5 == 0:
            print(f"   ⏳ {len(remaining_procs)} processus restants...")
    
    # Si toujours des processus, forcer l'arrêt
    remaining_procs = find_celery_processes()
    if remaining_procs:
        print("⚠️ Arrêt forcé des processus restants...")
        for proc in remaining_procs:
            try:
                print(f"   💀 SIGKILL à PID {proc.pid}")
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        time.sleep(2)
    
    final_procs = find_celery_processes()
    if not final_procs:
        print("✅ Tous les processus Celery arrêtés")
        return True
    else:
        print(f"❌ {len(final_procs)} processus toujours actifs")
        return False

def check_rabbitmq():
    """Vérifie que RabbitMQ fonctionne."""
    print("🐰 Vérification de RabbitMQ...")
    
    try:
        result = subprocess.run(
            ['rabbitmqctl', 'status'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ RabbitMQ fonctionne")
            return True
        else:
            print(f"❌ RabbitMQ erreur: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️ RabbitMQ timeout - peut-être pas installé")
        return False
    except FileNotFoundError:
        print("⚠️ rabbitmqctl non trouvé - RabbitMQ non installé?")
        return False

def check_database():
    """Vérifie la connexion à la base de données."""
    print("🗄️ Vérification de la base de données...")
    
    try:
        # Import local pour éviter les erreurs si modules manquants
        sys.path.insert(0, os.path.dirname(__file__))
        from services.database_persistence_service import DatabasePersistenceService
        
        import asyncio
        
        async def test_db():
            db_service = DatabasePersistenceService()
            await db_service.initialize()
            
            # Test simple
            async with db_service.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        
        success = asyncio.run(test_db())
        
        if success:
            print("✅ Base de données accessible")
            return True
        else:
            print("❌ Base de données inaccessible")
            return False
            
    except Exception as e:
        print(f"❌ Erreur base de données: {e}")
        return False

def start_celery():
    """Démarre Celery avec les nouvelles corrections."""
    print("🚀 Démarrage de Celery...")
    
    # Commande Celery
    cmd = [
        'celery', '-A', 'services.celery_app', 
        'worker', 
        '--loglevel=info',
        '--concurrency=8',
        '--queues=ai_generation,workflows,webhooks,tests,dlq'
    ]
    
    print(f"📝 Commande: {' '.join(cmd)}")
    
    try:
        # Démarrer en arrière-plan
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        print(f"✅ Celery démarré (PID: {process.pid})")
        
        # Afficher les premières lignes de log
        print("📋 Logs de démarrage:")
        for i in range(10):  # Premières 10 lignes
            line = process.stdout.readline()
            if line:
                print(f"   {line.strip()}")
            else:
                break
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur démarrage Celery: {e}")
        return False

def main():
    """Fonction principale."""
    print("🔄 Redémarrage propre de Celery avec corrections")
    print("=" * 60)
    
    # 1. Arrêter Celery
    if not stop_celery_gracefully():
        print("❌ Impossible d'arrêter Celery proprement")
        return False
    
    # 2. Vérifier les prérequis
    print("\n🔍 Vérification des prérequis...")
    
    rabbitmq_ok = check_rabbitmq()
    db_ok = check_database()
    
    if not db_ok:
        print("❌ Base de données non accessible - impossible de continuer")
        return False
    
    if not rabbitmq_ok:
        print("⚠️ RabbitMQ non accessible - Celery fonctionnera en mode dégradé")
    
    # 3. Attendre un peu
    print("\n⏳ Pause de 3 secondes...")
    time.sleep(3)
    
    # 4. Redémarrer Celery
    print("\n🚀 Redémarrage de Celery...")
    
    if start_celery():
        print("\n🎉 Celery redémarré avec succès!")
        print("\n💡 Suggestions:")
        print("   • Surveillez les logs pour vérifier le bon fonctionnement")
        print("   • Testez avec un webhook Monday.com")
        print("   • Vérifiez qu'aucune tâche dupliquée n'est créée")
        return True
    else:
        print("\n❌ Échec du redémarrage de Celery")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
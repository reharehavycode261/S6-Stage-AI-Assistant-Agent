#!/usr/bin/env python3
"""
Script pour analyser les logs Celery et identifier les problèmes.
"""

import json
import re
from typing import List, Dict, Any


class CeleryLogAnalyzer:
    """Analyseur de logs Celery."""
    
    def __init__(self, log_content: str):
        self.log_content = log_content
        self.warnings = []
        self.errors = []
        self.info = []
        
    def parse_logs(self):
        """Parse les logs et extrait les messages structurés."""
        lines = self.log_content.split('\n')
        
        for line in lines:
            # Chercher les JSON logs
            if '"event":' in line and '"level":' in line:
                try:
                    # Extraire le JSON
                    json_match = re.search(r'\{.*\}', line)
                    if json_match:
                        log_entry = json.loads(json_match.group(0))
                        
                        level = log_entry.get('level', '').lower()
                        event = log_entry.get('event', '')
                        
                        if level == 'error' or '❌' in event:
                            self.errors.append(log_entry)
                        elif level == 'warning' or '⚠️' in event:
                            self.warnings.append(log_entry)
                        elif '🔍' in event or 'DEBUG' in event.upper():
                            self.info.append(log_entry)
                except json.JSONDecodeError:
                    pass
    
    def analyze_issues(self) -> Dict[str, List[str]]:
        """Analyse les problèmes identifiés."""
        issues = {
            'critical': [],
            'warnings': [],
            'informational': []
        }
        
        # Analyser les erreurs
        for error in self.errors:
            event = error.get('event', '')
            issues['critical'].append({
                'type': 'ERROR',
                'message': event,
                'timestamp': error.get('timestamp', 'N/A')
            })
        
        # Analyser les warnings
        for warning in self.warnings:
            event = warning.get('event', '')
            
            # Catégoriser les warnings
            if 'Aucune colonne attendue trouvée' in event:
                issues['warnings'].append({
                    'type': 'COLONNES_MANQUANTES',
                    'message': event,
                    'fix': 'Vérifier le mapping des colonnes dans webhook_service.py'
                })
            elif 'URL repository nettoyée' in event:
                issues['warnings'].append({
                    'type': 'FORMAT_URL',
                    'message': event,
                    'fix': 'Le nettoyage fonctionne mais Monday.com devrait envoyer une URL propre'
                })
            elif 'avertissement(s) de linting' in event:
                issues['warnings'].append({
                    'type': 'LINTING',
                    'message': event,
                    'fix': 'Corriger les warnings de linting dans le code généré'
                })
            elif 'Branche protégée détectée' in event:
                issues['informational'].append({
                    'type': 'INFO',
                    'message': event,
                    'note': 'Comportement normal - création de branche feature'
                })
        
        return issues
    
    def print_analysis(self):
        """Affiche l'analyse des logs."""
        print("\n" + "="*60)
        print("🔍 ANALYSE DES LOGS CELERY")
        print("="*60)
        
        print(f"\nStatistiques:")
        print(f"  • {len(self.errors)} erreur(s)")
        print(f"  • {len(self.warnings)} avertissement(s)")
        print(f"  • {len(self.info)} message(s) informatif(s)")
        
        issues = self.analyze_issues()
        
        if issues['critical']:
            print("\n" + "="*60)
            print("❌ ERREURS CRITIQUES")
            print("="*60)
            for i, issue in enumerate(issues['critical'], 1):
                print(f"\n{i}. {issue['type']}")
                print(f"   Message: {issue['message'][:100]}...")
                print(f"   Timestamp: {issue['timestamp']}")
        
        if issues['warnings']:
            print("\n" + "="*60)
            print("⚠️  AVERTISSEMENTS À CORRIGER")
            print("="*60)
            for i, issue in enumerate(issues['warnings'], 1):
                print(f"\n{i}. Type: {issue['type']}")
                print(f"   Message: {issue['message'][:100]}...")
                if 'fix' in issue:
                    print(f"   🔧 Solution: {issue['fix']}")
        
        if issues['informational']:
            print("\n" + "="*60)
            print("ℹ️  INFORMATIONS")
            print("="*60)
            for i, issue in enumerate(issues['informational'], 1):
                print(f"\n{i}. {issue['type']}")
                print(f"   {issue['message'][:100]}...")
                if 'note' in issue:
                    print(f"   Note: {issue['note']}")


# Logs à analyser
CELERY_LOGS = """
Ligne 48-50: ⚠️ Aucune colonne attendue trouvée. Colonnes disponibles: ['task_owner', 'task_status', 'item_id', 'task_estimation', 'task_actual_effort']
Ligne 58: URL repository trouvée dans colonne configurée (link): GitHub - rehareha261/S2-GenericDAO - https://github.com/rehareha261/S2-GenericDAO
Ligne 177: ⚠️ 2 avertissement(s) de linting détecté(s) (non-bloquants)
"""

print("\n" + "="*60)
print("📊 PROBLÈMES IDENTIFIÉS DANS LES LOGS CELERY")
print("="*60)

print("\n1️⃣ PROBLÈME: Colonnes attendues non trouvées")
print("   Ligne 48-50 des logs")
print("   Message: '⚠️ Aucune colonne attendue trouvée'")
print("\n   🔍 Cause:")
print("      Le webhook_service.py cherche des colonnes qui n'existent pas")
print("      dans le nouveau board Monday.com")
print("\n   🔧 Solution:")
print("      Mettre à jour le mapping des colonnes dans webhook_service.py")

print("\n2️⃣ PROBLÈME: Format URL Monday.com incorrect")
print("   Ligne 58 des logs")
print("   Message: URL contient 'GitHub - user/repo - https://...'")
print("\n   🔍 Cause:")
print("      Monday.com envoie l'URL avec du texte supplémentaire")
print("\n   ✅ Status:")
print("      DÉJÀ CORRIGÉ - Le nettoyage d'URL fonctionne (ligne 100)")
print("      Mais on peut améliorer pour éviter ce nettoyage")

print("\n3️⃣ PROBLÈME: Avertissements de linting")
print("   Ligne 177 des logs")
print("   Message: '⚠️ 2 avertissement(s) de linting détecté(s)'")
print("\n   🔍 Cause:")
print("      Le code généré par l'IA contient des warnings de style")
print("\n   🔧 Solution:")
print("      Améliorer les prompts pour générer du code plus propre")

print("\n4️⃣ PROBLÈME: Contenu générique généré")
print("   Le main.txt ne correspond pas au projet réel (S2-GenericDAO)")
print("\n   🔍 Cause:")
print("      L'IA n'a pas analysé le contenu réel du repository")
print("      Elle a généré un résumé générique")
print("\n   🔧 Solution:")
print("      Améliorer le node implement pour lire le repository avant")

print("\n" + "="*60)
print("📝 RÉSUMÉ DES CORRECTIONS À EFFECTUER")
print("="*60)

print("\n✅ Priorité HAUTE:")
print("   1. Corriger le mapping des colonnes dans webhook_service.py")
print("   2. Améliorer l'analyse du repository avant génération")

print("\n⚠️  Priorité MOYENNE:")
print("   3. Améliorer les prompts pour éviter warnings de linting")

print("\n✓  Priorité BASSE (déjà géré):")
print("   4. Nettoyage URL Monday.com (fonctionne)")

print("\n" + "="*60)


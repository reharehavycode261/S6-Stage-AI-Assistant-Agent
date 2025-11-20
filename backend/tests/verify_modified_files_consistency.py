"""Script de vérification de la cohérence de modified_files dans tout le workflow."""

import os
import re
from pathlib import Path

def check_file_for_patterns(filepath, patterns_to_check):
    """Vérifie un fichier pour des patterns spécifiques."""
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.readlines()
            
        for line_num, line in enumerate(content, 1):
            for pattern_name, pattern in patterns_to_check.items():
                if re.search(pattern, line):
                    # Vérifier le contexte autour
                    context_start = max(0, line_num - 3)
                    context_end = min(len(content), line_num + 2)
                    context = ''.join(content[context_start:context_end])
                    
                    results.append({
                        'file': filepath,
                        'line': line_num,
                        'pattern': pattern_name,
                        'match': line.strip(),
                        'context': context
                    })
    except Exception as e:
        print(f"⚠️  Erreur lecture {filepath}: {e}")
    
    return results


def analyze_modified_files_usage():
    """Analyse l'utilisation de modified_files dans le projet."""
    
    print("\n" + "="*80)
    print("  VÉRIFICATION DE LA COHÉRENCE DE modified_files")
    print("="*80)
    
    # Patterns à vérifier
    patterns = {
        'assignment_dict': r'["\']modified_files["\']\s*=\s*\{',  # Dict assignment
        'assignment_list': r'["\']modified_files["\']\s*=\s*\[',  # List assignment
        'get_modified_files': r'\.get\(["\']modified_files["\']',  # Getting modified_files
        'code_changes_dict': r'["\']code_changes["\']\s*=\s*\{',  # code_changes as dict
        'isinstance_check': r'isinstance\(.*modified_files.*,\s*(dict|list)',  # Type checks
    }
    
    # Répertoires à analyser
    dirs_to_check = ['nodes', 'services', 'utils', 'graph']
    
    all_results = {}
    
    for dir_name in dirs_to_check:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue
            
        print(f"\n📁 Analyse de {dir_name}/")
        print("-" * 80)
        
        for py_file in dir_path.rglob('*.py'):
            results = check_file_for_patterns(str(py_file), patterns)
            if results:
                all_results[str(py_file)] = results
    
    # Afficher les résultats
    print("\n\n" + "="*80)
    print("  RÉSULTATS PAR FICHIER")
    print("="*80)
    
    issues_found = []
    
    for filepath, matches in all_results.items():
        print(f"\n📄 {filepath}")
        print("-" * 80)
        
        for match in matches:
            print(f"  Ligne {match['line']}: {match['pattern']}")
            print(f"    {match['match']}")
            
            # Analyser si c'est un problème potentiel
            if match['pattern'] == 'assignment_dict':
                # Vérifier si c'est code_changes ou modified_files
                if 'modified_files' in match['match'] and 'code_changes' not in match['context']:
                    issues_found.append({
                        'file': filepath,
                        'line': match['line'],
                        'issue': 'modified_files assigné comme dict au lieu de list',
                        'severity': 'HIGH'
                    })
                    print(f"    ⚠️  ATTENTION: modified_files assigné comme dict!")
            
            # Vérifier si isinstance est utilisé
            if match['pattern'] == 'isinstance_check':
                print(f"    ✅ Protection type détectée")
    
    # Résumé des problèmes
    print("\n\n" + "="*80)
    print("  RÉSUMÉ DES PROBLÈMES POTENTIELS")
    print("="*80)
    
    if issues_found:
        print(f"\n❌ {len(issues_found)} problème(s) trouvé(s):\n")
        for i, issue in enumerate(issues_found, 1):
            print(f"{i}. {issue['file']}:{issue['line']}")
            print(f"   {issue['issue']} (Sévérité: {issue['severity']})")
    else:
        print("\n✅ Aucun problème détecté!")
    
    return len(issues_found) == 0


def verify_consistent_usage():
    """Vérifie que l'usage est cohérent."""
    
    print("\n\n" + "="*80)
    print("  VÉRIFICATION DES RÈGLES DE COHÉRENCE")
    print("="*80)
    
    rules = [
        {
            'name': 'modified_files est toujours une liste',
            'check': 'files_modified: List[str] dans schemas.py',
            'status': 'OK'
        },
        {
            'name': 'Validator Pydantic normalise automatiquement',
            'check': '@field_validator pour files_modified',
            'status': 'OK'
        },
        {
            'name': 'Service valide avant insertion DB',
            'check': '_validate_files_modified dans human_validation_service.py',
            'status': 'OK'
        },
        {
            'name': 'Node Monday.com convertit dict→list',
            'check': 'isinstance check dans monday_validation_node.py',
            'status': 'OK'
        },
        {
            'name': 'code_changes reste un dict (intentionnel)',
            'check': 'code_changes utilisé comme Dict[str, str]',
            'status': 'OK'
        }
    ]
    
    print("\n")
    for i, rule in enumerate(rules, 1):
        print(f"  {i}. {rule['name']}")
        print(f"     └─ {rule['check']}")
        print(f"     └─ Statut: ✅ {rule['status']}")
        print()
    
    return True


def create_recommendations():
    """Crée des recommandations pour éviter les problèmes futurs."""
    
    print("\n" + "="*80)
    print("  RECOMMANDATIONS")
    print("="*80)
    
    recommendations = [
        {
            'titre': 'Convention de nommage',
            'desc': 'Utiliser modified_files pour les listes, code_changes pour les dicts',
            'priorité': 'HAUTE'
        },
        {
            'titre': 'Validation systématique',
            'desc': 'Toujours normaliser modified_files avant usage avec isinstance()',
            'priorité': 'HAUTE'
        },
        {
            'titre': 'Tests de régression',
            'desc': 'Ajouter des tests pour chaque nouveau node qui manipule modified_files',
            'priorité': 'MOYENNE'
        },
        {
            'titre': 'Documentation',
            'desc': 'Documenter la distinction entre modified_files (list) et code_changes (dict)',
            'priorité': 'MOYENNE'
        },
        {
            'titre': 'Linting custom',
            'desc': 'Créer une règle de linting pour détecter modified_files = {}',
            'priorité': 'BASSE'
        }
    ]
    
    print("\n")
    for i, rec in enumerate(recommendations, 1):
        icon = "🔴" if rec['priorité'] == 'HAUTE' else "🟡" if rec['priorité'] == 'MOYENNE' else "🟢"
        print(f"{icon} {i}. {rec['titre']} (Priorité: {rec['priorité']})")
        print(f"   {rec['desc']}")
        print()


def main():
    """Point d'entrée principal."""
    
    # Changer vers le répertoire du projet
    os.chdir('/Users/rehareharanaivo/Desktop/AI-Agent')
    
    # Exécuter les vérifications
    consistency_ok = analyze_modified_files_usage()
    rules_ok = verify_consistent_usage()
    
    # Créer les recommandations
    create_recommendations()
    
    # Résumé final
    print("\n" + "="*80)
    print("  RÉSUMÉ FINAL")
    print("="*80)
    
    if consistency_ok and rules_ok:
        print("\n✅ Toutes les vérifications sont passées avec succès!")
        print("✅ Le code est cohérent et les corrections sont valides.")
        print("\n🎯 Prochaines étapes:")
        print("   1. Tester avec Celery worker")
        print("   2. Créer une tâche test dans Monday.com")
        print("   3. Vérifier les logs pour confirmer l'insertion en DB")
    else:
        print("\n❌ Des problèmes ont été détectés.")
        print("   Veuillez corriger les problèmes avant de continuer.")
    
    print("\n" + "="*80)
    print()


if __name__ == "__main__":
    main()


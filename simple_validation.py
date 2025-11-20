#!/usr/bin/env python3
"""
Script de validation simple des corrections Monday.com.
Test les fonctions de base sans dépendances complexes.
"""

import re
from typing import Optional, Dict, Any


def extract_github_url_from_description(description: str) -> Optional[str]:
    """Version simplifiée de l'extraction d'URL GitHub."""
    if not description:
        return None
    
    # Patterns pour différents formats d'URL GitHub
    patterns = [
        r'https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?',
        r'git@github\.com:([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?',
        r'github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?',
        r'\[.*?\]\(https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?\)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description)
        if match:
            owner, repo = match.groups()
            # Normaliser en HTTPS
            return f"https://github.com/{owner}/{repo}"
    
    return None


def normalize_monday_columns(raw_columns) -> Dict[str, Any]:
    """Normalise les colonnes Monday.com en dictionnaire."""
    normalized_columns = {}
    
    if isinstance(raw_columns, list):
        # Format API Monday.com (liste)
        for col in raw_columns:
            if isinstance(col, dict) and "id" in col:
                normalized_columns[col["id"]] = col
        print(f"🔧 Conversion colonnes liste → dict: {len(normalized_columns)} colonnes")
    elif isinstance(raw_columns, dict):
        # Format webhook (dictionnaire)
        normalized_columns = raw_columns
    else:
        print(f"⚠️ Format colonnes non reconnu: {type(raw_columns)}")
        normalized_columns = {}
    
    return normalized_columns


def safe_extract_text(col_data: Dict[str, Any], default: str = "") -> str:
    """Extrait le texte d'une colonne de manière sécurisée."""
    if not isinstance(col_data, dict):
        return default
    
    # Essayer plusieurs propriétés possibles
    text_value = (col_data.get("text") or 
                 col_data.get("value") or 
                 str(col_data.get("display_value", "")) or 
                 default).strip()
    
    # Si c'est un dict dans value, essayer d'extraire le texte
    if not text_value and isinstance(col_data.get("value"), dict):
        value_dict = col_data.get("value", {})
        text_value = (
            value_dict.get("text") or
            value_dict.get("value") or
            str(value_dict.get("display_value", ""))
        ).strip()
    
    return text_value


def test_github_url_extraction():
    """Test l'extraction d'URLs GitHub."""
    print("🧪 Test extraction URLs GitHub...")
    
    test_cases = [
        ("Implémente login pour: https://github.com/user/repo", "https://github.com/user/repo"),
        ("Clone git@github.com:user/project.git", "https://github.com/user/project"),
        ("Voir [projet](https://github.com/user/app) ici", "https://github.com/user/app"),
        ("Aucune URL ici", None),
        ("URL complète: https://github.com/company/awesome-app.git", "https://github.com/company/awesome-app"),
        ("Repo SSH: git@github.com:test/repo.git", "https://github.com/test/repo")
    ]
    
    success_count = 0
    for description, expected in test_cases:
        result = extract_github_url_from_description(description)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{description[:40]}...' → {result}")
        if result != expected:
            print(f"    Attendu: {expected}, Obtenu: {result}")
        else:
            success_count += 1
    
    print(f"  📊 Résultat: {success_count}/{len(test_cases)} tests réussis\n")
    return success_count == len(test_cases)


def test_column_normalization():
    """Test la normalisation des colonnes Monday.com."""
    print("🧪 Test normalisation colonnes Monday.com...")
    
    # Test format dictionnaire (webhook)
    payload_dict = {
        "columnValues": {
            "description": {"text": "Description webhook"},
            "repo_url": {"text": "https://github.com/user/repo"},
            "priority": {"text": "high"}
        }
    }
    
    normalized_dict = normalize_monday_columns(payload_dict.get("columnValues", {}))
    dict_success = (
        len(normalized_dict) == 3 and
        safe_extract_text(normalized_dict.get("description", {})) == "Description webhook" and
        safe_extract_text(normalized_dict.get("repo_url", {})) == "https://github.com/user/repo"
    )
    
    status_dict = "✅" if dict_success else "❌"
    print(f"  {status_dict} Format dictionnaire traité correctement")
    
    # Test format liste (API)
    payload_list = {
        "column_values": [
            {"id": "description", "text": "Description API"},
            {"id": "repo_url", "text": "https://github.com/user/api-repo"},
            {"id": "priority", "text": "medium"}
        ]
    }
    
    normalized_list = normalize_monday_columns(payload_list.get("column_values", []))
    list_success = (
        len(normalized_list) == 3 and
        safe_extract_text(normalized_list.get("description", {})) == "Description API" and
        safe_extract_text(normalized_list.get("repo_url", {})) == "https://github.com/user/api-repo"
    )
    
    status_list = "✅" if list_success else "❌"
    print(f"  {status_list} Format liste normalisé et traité correctement")
    
    print(f"  📊 Résultat: {(dict_success + list_success)}/2 tests réussis\n")
    return dict_success and list_success


def test_description_extraction():
    """Test l'extraction robuste de descriptions."""
    print("🧪 Test extraction descriptions...")
    
    # Test colonnes avec différentes structures
    test_columns = [
        {"id": "description", "text": "Description simple"},
        {"id": "details", "value": "Description dans value"},
        {"id": "notes", "value": {"text": "Description imbriquée"}},
        {"id": "comment", "display_value": "Description display"}
    ]
    
    success_count = 0
    expected_results = [
        "Description simple",
        "Description dans value", 
        "Description imbriquée",
        "Description display"
    ]
    
    for i, col in enumerate(test_columns):
        result = safe_extract_text(col)
        expected = expected_results[i]
        status = "✅" if result == expected else "❌"
        print(f"  {status} Colonne '{col['id']}': '{result}'")
        if result != expected:
            print(f"    Attendu: '{expected}', Obtenu: '{result}'")
        else:
            success_count += 1
    
    print(f"  📊 Résultat: {success_count}/{len(test_columns)} tests réussis\n")
    return success_count == len(test_columns)


def test_integration_scenario():
    """Test d'un scénario d'intégration complet."""
    print("🧪 Test scénario d'intégration...")
    
    # Payload Monday.com simulé
    monday_payload = {
        "pulseId": "123456789",
        "boardId": "987654321",
        "pulseName": "Implémenter système de login",
        "columnValues": {
            "description": {
                "text": "Créer un système de login sécurisé avec JWT pour: https://github.com/company/awesome-app"
            },
            "priority": {"text": "high"},
            "repository_url": {"text": "https://github.com/company/old-repo"}
        }
    }
    
    # 1. Normalisation des colonnes
    raw_columns = monday_payload.get("columnValues", {})
    normalized_columns = normalize_monday_columns(raw_columns)
    
    # 2. Extraction des données
    description = safe_extract_text(normalized_columns.get("description", {}))
    repository_url = safe_extract_text(normalized_columns.get("repository_url", {}))
    priority = safe_extract_text(normalized_columns.get("priority", {}))
    
    # 3. Extraction URL depuis description (priorité à la description)
    github_url_from_desc = extract_github_url_from_description(description)
    final_url = github_url_from_desc if github_url_from_desc else repository_url
    
    # Vérifications
    checks = [
        (description.startswith("Créer un système"), "Description extraite"),
        (priority == "high", "Priorité extraite"),
        (github_url_from_desc == "https://github.com/company/awesome-app", "URL GitHub depuis description"),
        (final_url == "https://github.com/company/awesome-app", "URL finale priorité description")
    ]
    
    success_count = 0
    for check, name in checks:
        status = "✅" if check else "❌"
        print(f"  {status} {name}")
        if check:
            success_count += 1
    
    print(f"  📊 Résultat: {success_count}/{len(checks)} vérifications réussies\n")
    return success_count == len(checks)


def main():
    """Fonction principale de validation."""
    print("🔧 === VALIDATION SIMPLE DES CORRECTIONS MONDAY.COM ===\n")
    
    tests = [
        ("Extraction URLs GitHub", test_github_url_extraction),
        ("Normalisation colonnes", test_column_normalization),
        ("Extraction descriptions", test_description_extraction),
        ("Scénario d'intégration", test_integration_scenario)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Erreur dans {test_name}: {e}")
            results.append(False)
    
    success_count = sum(results)
    total_tests = len(tests)
    
    print("✅ === VALIDATION TERMINÉE ===")
    print(f"📊 Résultat global: {success_count}/{total_tests} groupes de tests réussis")
    
    if success_count == total_tests:
        print("🎉 Toutes les corrections fonctionnent correctement !")
        print("\n📝 Problèmes corrigés:")
        print("  1. ✅ Normalisation format colonnes Monday.com (dict/list)")
        print("  2. ✅ Extraction robuste URLs GitHub depuis descriptions")
        print("  3. ✅ Extraction sécurisée des valeurs de colonnes")
        print("  4. ✅ Priorité donnée aux URLs de description")
        return 0
    else:
        print(f"⚠️ {total_tests - success_count} groupe(s) de tests ont échoué")
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code) 
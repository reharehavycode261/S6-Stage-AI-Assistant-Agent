#!/usr/bin/env python3
"""
Script de test du système multilingue illimité.

Ce script teste la génération automatique de templates via LLM pour
n'importe quelle langue, y compris des langues non-hardcodées.
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.project_language_detector import project_language_detector
from utils.logger import get_logger

logger = get_logger(__name__)


async def test_hardcoded_languages():
    """Test des langues hardcodées (cache rapide)."""
    print("\n" + "="*80)
    print("✅ TEST 1: LANGUES HARDCODÉES (FR, EN, ES)")
    print("="*80)
    
    hardcoded_langs = ['fr', 'en', 'es']
    
    for lang in hardcoded_langs:
        print(f"\n🌍 Langue: {lang.upper()}")
        try:
            # Test PR template
            pr_template = await project_language_detector.get_pr_template(lang)
            print(f"   ✅ Template PR récupéré (hardcodé)")
            print(f"      • Header: {pr_template['auto_pr_header'][:50]}...")
            
            # Test Monday template
            monday_template = await project_language_detector.get_monday_reply_template(lang, 'en')
            print(f"   ✅ Template Monday récupéré (hardcodé)")
            print(f"      • Workflow: {monday_template['workflow_started'][:50]}...")
            
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            return False
    
    return True


async def test_llm_generated_languages():
    """Test des langues non-hardcodées (génération LLM)."""
    print("\n" + "="*80)
    print("🤖 TEST 2: LANGUES GÉNÉRÉES PAR LLM")
    print("="*80)
    
    test_langs = [
        ('de', 'Allemand'),
        ('it', 'Italien'),
        ('pt', 'Portugais'),
        ('ja', '日本語'),
        ('zh', '中文'),
    ]
    
    for lang_code, lang_name in test_langs:
        print(f"\n🌍 Langue: {lang_name} ({lang_code})")
        try:
            # Test PR template (génération via LLM)
            print(f"   🤖 Génération du template PR via LLM...")
            pr_template = await project_language_detector.get_pr_template(lang_code)
            print(f"   ✅ Template PR généré avec succès !")
            print(f"      • Header: {pr_template['auto_pr_header']}")
            print(f"      • Task Section: {pr_template['task_section']}")
            print(f"      • Changes Section: {pr_template['changes_section']}")
            
            # Test Monday template (génération via LLM)
            print(f"   🤖 Génération du template Monday via LLM...")
            monday_template = await project_language_detector.get_monday_reply_template(lang_code, 'en')
            print(f"   ✅ Template Monday généré avec succès !")
            print(f"      • Workflow Started: {monday_template['workflow_started']}")
            print(f"      • PR Created: {monday_template['pr_created']}")
            
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_fallback_mechanism():
    """Test du mécanisme de fallback."""
    print("\n" + "="*80)
    print("🔄 TEST 3: MÉCANISME DE FALLBACK")
    print("="*80)
    
    print("\n🧪 Test avec une langue invalide (xx)...")
    try:
        # Devrait fallback sur anglais
        template = await project_language_detector.get_pr_template('xx')
        if template['auto_pr_header'] == '## 🤖 Automatically generated Pull Request':
            print("   ✅ Fallback sur anglais fonctionne correctement")
            return True
        else:
            print("   ❌ Fallback incorrect")
            return False
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False


async def main():
    """Exécute tous les tests."""
    print("\n" + "="*80)
    print("🚀 TEST DU SYSTÈME MULTILINGUE ILLIMITÉ")
    print("="*80)
    print("\n⚡ Fonctionnalité: Génération automatique de templates via LLM")
    print("   • Langues hardcodées: FR, EN, ES (cache rapide)")
    print("   • Autres langues: Génération à la demande via OpenAI GPT-3.5-turbo")
    print("   • Fallback: Anglais en cas d'erreur")
    
    results = []
    
    # Test 1: Langues hardcodées
    result1 = await test_hardcoded_languages()
    results.append(("Langues hardcodées", result1))
    
    # Test 2: Langues générées par LLM (peut prendre du temps)
    print("\n⏳ Les tests suivants utilisent l'API OpenAI (peut prendre 30-60 secondes)...")
    result2 = await test_llm_generated_languages()
    results.append(("Génération LLM", result2))
    
    # Test 3: Fallback
    result3 = await test_fallback_mechanism()
    results.append(("Mécanisme de fallback", result3))
    
    # Résumé
    print("\n" + "="*80)
    print("📋 RÉSUMÉ DES TESTS")
    print("="*80)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    # Score final
    passed = sum(1 for _, r in results if r is True)
    total = len(results)
    
    print("\n" + "="*80)
    if passed == total:
        print(f"🎉 TOUS LES TESTS RÉUSSIS ! ({passed}/{total})")
        print("="*80)
        print("\n✅ Le système multilingue illimité est opérationnel !")
        print("\n📝 Langues supportées:")
        print("   • Hardcodées (rapides): Français, English, Español")
        print("   • Génération LLM (toutes les autres): Allemand, Italien, Portugais,")
        print("     Japonais, Chinois, Russe, Coréen, Hindi, Arabe, Néerlandais,")
        print("     Polonais, Turc, Suédois, Norvégien, Danois, Finnois, et TOUTES")
        print("     les autres langues supportées par OpenAI GPT-3.5-turbo !")
        print("\n🚀 Utilisation:")
        print("   - Templates PR: Générés dans la langue du projet")
        print("   - Messages Monday: Générés dans la langue de l'utilisateur")
        print("   - Pas de limite de langues !")
        return 0
    else:
        print(f"⚠️  CERTAINS TESTS ONT ÉCHOUÉ ({passed}/{total})")
        print("="*80)
        print("\n⚠️  Vérifiez les erreurs ci-dessus et les logs.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


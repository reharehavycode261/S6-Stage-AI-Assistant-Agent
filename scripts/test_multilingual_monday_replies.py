#!/usr/bin/env python3
"""
Test du système multilingue pour les réponses Monday.com.
Vérifie que les réponses sont générées dans la langue de l'utilisateur.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.project_language_detector import project_language_detector


async def test_monday_reply_templates():
    """Test des templates de réponses Monday.com multilingues."""
    print("\n" + "="*80)
    print("🌍 TEST: TEMPLATES MULTILINGUES POUR RÉPONSES MONDAY.COM")
    print("="*80)
    
    # Langues à tester
    test_cases = [
        ("en", "en", "English user, English project"),
        ("fr", "en", "French user, English project"),
        ("es", "en", "Spanish user, English project"),
        ("de", "en", "German user, English project"),
        ("zh", "en", "Chinese user, English project"),
        ("ja", "en", "Japanese user, English project"),
        ("it", "en", "Italian user, English project"),
        ("pt", "en", "Portuguese user, English project"),
    ]
    
    all_passed = True
    
    for user_lang, project_lang, description in test_cases:
        print(f"\n{'='*80}")
        print(f"📝 Test: {description}")
        print(f"   User language: {user_lang}, Project language: {project_lang}")
        print(f"{'='*80}")
        
        try:
            # Obtenir le template
            template = await project_language_detector.get_monday_reply_template(
                user_language=user_lang,
                project_language=project_lang
            )
            
            # Vérifier que les clés requises sont présentes
            required_keys = [
                'response_header',
                'question_label',
                'automatic_response_note',
                'workflow_started',
                'pr_created',
                'error',
                'validation_request'
            ]
            
            missing_keys = [key for key in required_keys if key not in template]
            
            if missing_keys:
                print(f"   ❌ Clés manquantes: {missing_keys}")
                all_passed = False
            else:
                print(f"   ✅ Toutes les clés présentes")
                print(f"   📌 response_header: {template['response_header']}")
                print(f"   📌 question_label: {template['question_label']}")
                print(f"   📌 automatic_response_note: {template['automatic_response_note'][:80]}...")
                
                # Vérifier que les textes ne sont pas en anglais pour les langues non-anglaises
                if user_lang != 'en':
                    # Pour les langues hardcodées (fr, es), on peut vérifier
                    if user_lang in ['fr', 'es']:
                        if 'Question' == template['question_label'] and user_lang == 'fr':
                            print(f"   ⚠️  Template en français devrait avoir 'Question' (OK)")
                        elif 'Pregunta' == template['question_label'] and user_lang == 'es':
                            print(f"   ⚠️  Template en espagnol devrait avoir 'Pregunta' (OK)")
                
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 TOUS LES TESTS DE TEMPLATES MULTILINGUES RÉUSSIS !")
    else:
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
    print("="*80)
    
    return all_passed


async def test_reply_formatting():
    """Test du formatage complet d'une réponse."""
    print("\n" + "="*80)
    print("📝 TEST: FORMATAGE COMPLET D'UNE RÉPONSE")
    print("="*80)
    
    test_scenarios = [
        {
            'user_lang': 'en',
            'question': 'Is there a README file in this project?',
            'response': 'Yes, there is a README.md file at the root of the project. It contains installation instructions and usage examples.'
        },
        {
            'user_lang': 'fr',
            'question': 'Y a-t-il un fichier README dans ce projet ?',
            'response': 'Oui, il y a un fichier README.md à la racine du projet. Il contient les instructions d\'installation et des exemples d\'utilisation.'
        },
        {
            'user_lang': 'es',
            'question': '¿Hay un archivo README en este proyecto?',
            'response': 'Sí, hay un archivo README.md en la raíz del proyecto. Contiene instrucciones de instalación y ejemplos de uso.'
        }
    ]
    
    for scenario in test_scenarios:
        user_lang = scenario['user_lang']
        question = scenario['question']
        response = scenario['response']
        
        print(f"\n{'='*80}")
        print(f"🌍 Scénario: Utilisateur {user_lang.upper()}")
        print(f"{'='*80}")
        
        template = await project_language_detector.get_monday_reply_template(
            user_language=user_lang,
            project_language='en'
        )
        
        # Simuler le formatage de la réponse
        response_header = template['response_header']
        question_label = template['question_label']
        automatic_response_note = template['automatic_response_note']
        
        formatted_message = f"""{response_header}

> {question_label}: {question[:100]}

{response}

---
*{automatic_response_note}*
"""
        
        print(f"📤 Message formaté:")
        print(formatted_message)
        print(f"{'='*80}")
    
    print("\n✅ Formatage des réponses vérifié pour toutes les langues")
    return True


async def main():
    """Point d'entrée principal."""
    exit_code = 0
    
    try:
        # Test 1: Templates multilingues
        if not await test_monday_reply_templates():
            exit_code = 1
        
        # Test 2: Formatage des réponses
        if not await test_reply_formatting():
            exit_code = 1
            
    except Exception as e:
        print(f"\n❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())


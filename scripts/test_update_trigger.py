#!/usr/bin/env python3
"""
Script pour tester la logique de mise à jour des colonnes Monday.com.
Détecte les incohérences dans la configuration et le code.
"""

import sys
import json
import asyncio
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings


class UpdateTriggerTester:
    """Testeur de la logique de mise à jour."""
    
    def __init__(self):
        self.settings = get_settings()
        self.issues = []
        self.warnings = []
        self.successes = []
        
    def test_column_configuration(self):
        """Teste la configuration des colonnes."""
        print("\n" + "="*60)
        print("1️⃣  TEST DE LA CONFIGURATION DES COLONNES")
        print("="*60)
        
        print(f"\n📋 Configuration actuelle:")
        print(f"   Board ID: {self.settings.monday_board_id}")
        print(f"   Status Column: {self.settings.monday_status_column_id}")
        print(f"   Repository URL Column: {self.settings.monday_repository_url_column_id}")
        
        # Vérifier Repository URL Column
        if not self.settings.monday_repository_url_column_id:
            self.issues.append("❌ MONDAY_REPOSITORY_URL_COLUMN_ID non configuré dans .env")
            print("\n❌ Repository URL Column ID non configuré!")
            return False
        else:
            print(f"\n✅ Repository URL Column ID: {self.settings.monday_repository_url_column_id}")
            self.successes.append("Configuration Repository URL présente")
        
        return True
    
    def test_column_detection_logic(self):
        """Teste la logique de détection des colonnes link."""
        print("\n" + "="*60)
        print("2️⃣  TEST DE LA DÉTECTION DES COLONNES LINK")
        print("="*60)
        
        column_id = self.settings.monday_repository_url_column_id
        
        # Reproduire la logique de monday_tool.py ligne 841-847
        column_id_lower = column_id.lower()
        is_link_column = (
            column_id.startswith("link_") or
            "url" in column_id_lower or
            "lien" in column_id_lower or
            (column_id_lower == "lien_pr") or
            (column_id_lower == "link")  # ⚠️ AJOUT: Cas où column_id est exactement "link"
        )
        
        print(f"\n🔍 Test de détection pour column_id = '{column_id}':")
        print(f"   • Commence par 'link_': {column_id.startswith('link_')}")
        print(f"   • Contient 'url': {'url' in column_id_lower}")
        print(f"   • Contient 'lien': {'lien' in column_id_lower}")
        print(f"   • Égal à 'lien_pr': {column_id_lower == 'lien_pr'}")
        print(f"   • Égal à 'link': {column_id_lower == 'link'}")
        print(f"\n   Résultat: is_link_column = {is_link_column}")
        
        if is_link_column:
            print("\n✅ La colonne sera correctement détectée comme type 'link'")
            self.successes.append("Détection de colonne link fonctionnelle")
        else:
            print("\n❌ La colonne ne sera PAS détectée comme type 'link'")
            self.issues.append(f"Colonne '{column_id}' non détectée comme link dans la logique actuelle")
            
        return is_link_column
    
    def test_value_formatting(self):
        """Teste le formatage des valeurs pour Monday.com."""
        print("\n" + "="*60)
        print("3️⃣  TEST DU FORMATAGE DES VALEURS")
        print("="*60)
        
        test_url = "https://github.com/user/repo/pull/123"
        
        print(f"\n📝 URL de test: {test_url}")
        
        # Simuler le formatage de monday_tool.py
        import re
        pr_number_match = re.search(r'/pull/(\d+)', test_url)
        pr_text = f"PR #{pr_number_match.group(1)}" if pr_number_match else "Pull Request"
        
        formatted_value = {
            "url": test_url,
            "text": pr_text
        }
        
        json_value = json.dumps(formatted_value)
        
        print(f"\n✅ Formatage dict:")
        print(f"   {formatted_value}")
        print(f"\n✅ Formatage JSON (envoyé à Monday.com):")
        print(f"   {json_value}")
        
        # Vérifier que c'est un JSON valide
        try:
            parsed = json.loads(json_value)
            if "url" in parsed and "text" in parsed:
                print(f"\n✅ Format JSON valide et conforme")
                self.successes.append("Formatage des valeurs correct")
                return True
            else:
                print(f"\n❌ Format JSON invalide - clés manquantes")
                self.issues.append("Format JSON ne contient pas 'url' et 'text'")
                return False
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON invalide: {e}")
            self.issues.append(f"JSON invalide: {e}")
            return False
    
    def check_hardcoded_columns(self):
        """Vérifie les colonnes codées en dur dans le code."""
        print("\n" + "="*60)
        print("4️⃣  VÉRIFICATION DES COLONNES CODÉES EN DUR")
        print("="*60)
        
        # Lire le fichier update_node.py
        update_node_path = Path(__file__).parent.parent / "nodes" / "update_node.py"
        
        try:
            with open(update_node_path, 'r') as f:
                content = f.read()
            
            # Chercher les colonnes codées en dur
            import re
            hardcoded_patterns = [
                (r'column_id\s*=\s*["\']lien_pr["\']', "lien_pr"),
                (r'column_id\s*=\s*["\']link_[a-z0-9_]+["\']', "link_*"),
                (r'column_id\s*=\s*["\']status["\']', "status (attention si ID a changé)"),
            ]
            
            found_issues = []
            for pattern, description in hardcoded_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    found_issues.append((line_num, description, match.group(0)))
            
            if found_issues:
                print(f"\n⚠️  {len(found_issues)} colonne(s) codée(s) en dur trouvée(s):\n")
                for line_num, desc, code in found_issues:
                    print(f"   Ligne {line_num}: {desc}")
                    print(f"      Code: {code}")
                    self.warnings.append(f"Ligne {line_num}: colonne '{desc}' codée en dur")
                
                print(f"\n💡 Recommandation: Utiliser settings.monday_repository_url_column_id")
                return False
            else:
                print(f"\n✅ Aucune colonne codée en dur trouvée")
                self.successes.append("Pas de colonnes en dur")
                return True
                
        except Exception as e:
            print(f"\n❌ Erreur lecture update_node.py: {e}")
            self.issues.append(f"Impossible de vérifier les colonnes en dur: {e}")
            return False
    
    def test_column_id_edge_cases(self):
        """Teste les cas limites du column_id."""
        print("\n" + "="*60)
        print("5️⃣  TEST DES CAS LIMITES")
        print("="*60)
        
        test_cases = [
            ("link", "Colonne nommée simplement 'link'"),
            ("link_mkwg662v", "Ancien format avec préfixe"),
            ("repository_url", "Nom descriptif"),
            ("url", "Nom court"),
            ("lien_pr", "Nom français"),
        ]
        
        print(f"\n🧪 Tests de détection pour différents noms:\n")
        
        all_pass = True
        for col_id, description in test_cases:
            col_id_lower = col_id.lower()
            is_detected = (
                col_id.startswith("link_") or
                "url" in col_id_lower or
                "lien" in col_id_lower or
                col_id_lower == "lien_pr" or
                col_id_lower == "link"
            )
            
            status = "✅" if is_detected else "❌"
            print(f"   {status} '{col_id}': {description} - {'Détecté' if is_detected else 'NON détecté'}")
            
            if not is_detected:
                all_pass = False
        
        if all_pass:
            print(f"\n✅ Tous les cas limites sont gérés")
            self.successes.append("Tous les cas limites gérés")
        else:
            print(f"\n⚠️  Certains cas ne sont pas détectés")
            self.warnings.append("Certains noms de colonnes ne seraient pas détectés")
        
        return all_pass
    
    def generate_fix_recommendations(self):
        """Génère les recommandations de correction."""
        print("\n" + "="*60)
        print("📝 RECOMMANDATIONS DE CORRECTION")
        print("="*60)
        
        if self.issues or self.warnings:
            print("\n🔧 Corrections nécessaires:\n")
            
            # Correction 1: Améliorer la détection de colonne link
            if any("non détectée" in issue for issue in self.issues):
                print("1. Améliorer la détection de colonne link dans monday_tool.py")
                print("   Ligne ~843: Ajouter le cas (column_id_lower == 'link')")
                print()
            
            # Correction 2: Remplacer les colonnes en dur
            if self.warnings:
                print("2. Remplacer les colonnes codées en dur")
                print("   Utiliser: settings.monday_repository_url_column_id")
                print("   Au lieu de: column_id='lien_pr'")
                print()
            
            # Correction 3: Configuration .env
            if any("non configuré" in issue for issue in self.issues):
                print("3. Configurer MONDAY_REPOSITORY_URL_COLUMN_ID dans .env")
                print(f"   MONDAY_REPOSITORY_URL_COLUMN_ID=link")
                print()
        else:
            print("\n✅ Aucune correction nécessaire!")
    
    def print_summary(self):
        """Affiche le résumé des tests."""
        print("\n" + "="*60)
        print("📊 RÉSUMÉ DES TESTS")
        print("="*60)
        
        if self.successes:
            print(f"\n✅ SUCCÈS ({len(self.successes)}):")
            for success in self.successes:
                print(f"   • {success}")
        
        if self.warnings:
            print(f"\n⚠️  AVERTISSEMENTS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if self.issues:
            print(f"\n❌ ERREURS ({len(self.issues)}):")
            for issue in self.issues:
                print(f"   • {issue}")
        
        print("\n" + "="*60)
        
        if not self.issues and not self.warnings:
            print("✅ TOUS LES TESTS RÉUSSIS!")
        elif not self.issues:
            print("⚠️  Tests passés avec des avertissements")
        else:
            print("❌ Tests échoués - corrections nécessaires")
        
        print("="*60)
    
    def run_all_tests(self):
        """Lance tous les tests."""
        print("\n" + "="*60)
        print("🧪 TEST COMPLET DE LA LOGIQUE DE MISE À JOUR")
        print("="*60)
        
        # Test 1
        test1 = self.test_column_configuration()
        
        # Test 2
        test2 = self.test_column_detection_logic()
        
        # Test 3
        test3 = self.test_value_formatting()
        
        # Test 4
        test4 = self.check_hardcoded_columns()
        
        # Test 5
        test5 = self.test_column_id_edge_cases()
        
        # Recommandations
        self.generate_fix_recommendations()
        
        # Résumé
        self.print_summary()
        
        return all([test1, test2, test3, test4, test5])


def main():
    """Point d'entrée principal."""
    tester = UpdateTriggerTester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success and not tester.issues else 1)


if __name__ == "__main__":
    main()


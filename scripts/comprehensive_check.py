#!/usr/bin/env python3
"""
Script pour vérifier toutes les incohérences potentielles dans le projet.
"""

import sys
import os
import re
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))


class ComprehensiveChecker:
    """Vérificateur complet d'incohérences."""
    
    def __init__(self):
        self.root_path = Path(__file__).parent.parent
        self.issues = []
        self.warnings = []
        self.successes = []
        
    def check_hardcoded_column_ids(self):
        """Cherche tous les column_id codés en dur."""
        print("\n" + "="*60)
        print("1️⃣  RECHERCHE DE COLUMN_ID CODÉS EN DUR")
        print("="*60)
        
        # Fichiers Python à vérifier
        py_files = [
            "nodes/update_node.py",
            "nodes/finalize_node.py",
            "nodes/merge_node.py",
            "services/webhook_service.py",
            "tools/monday_tool.py"
        ]
        
        hardcoded_patterns = [
            (r'column_id\s*=\s*["\'](?!settings\.|self\.settings\.)([a-z_0-9]+)["\']', "column_id avec valeur littérale"),
            (r'columnId["\']?\s*:\s*["\']([a-z_0-9]+)["\']', "columnId dans un dict"),
        ]
        
        found_any = False
        for py_file in py_files:
            file_path = self.root_path / py_file
            if not file_path.exists():
                continue
            
            with open(file_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
            
            for pattern, desc in hardcoded_patterns:
                for match in re.finditer(pattern, content):
                    line_num = content[:match.start()].count('\n') + 1
                    column_id = match.group(1)
                    
                    # Ignorer certains cas valides
                    if column_id in ['item_id', 'name', 'monday_status_column_id', 'monday_repository_url_column_id']:
                        continue
                    
                    # Vérifier si c'est dans un commentaire
                    line_content = lines[line_num - 1].strip()
                    if line_content.startswith('#'):
                        continue
                    
                    found_any = True
                    print(f"\n⚠️  {py_file} (ligne {line_num}):")
                    print(f"   Column ID codé en dur: '{column_id}'")
                    print(f"   Contexte: {line_content[:80]}")
                    self.warnings.append(f"{py_file}:{line_num} - column_id '{column_id}' codé en dur")
        
        if not found_any:
            print("\n✅ Aucun column_id codé en dur trouvé")
            self.successes.append("Pas de column_id codés en dur")
        
        return not found_any
    
    def check_status_usage(self):
        """Vérifie l'utilisation de la colonne status."""
        print("\n" + "="*60)
        print("2️⃣  VÉRIFICATION DE L'USAGE DE LA COLONNE STATUS")
        print("="*60)
        
        # Vérifier monday_tool.py
        monday_tool_path = self.root_path / "tools" / "monday_tool.py"
        
        with open(monday_tool_path, 'r') as f:
            content = f.read()
        
        # Chercher _update_item_status
        status_func_match = re.search(r'async def _update_item_status\(.*?\):(.*?)(?=async def|\Z)', content, re.DOTALL)
        
        if status_func_match:
            func_body = status_func_match.group(1)
            
            # Vérifier si elle utilise monday_status_column_id
            if 'monday_status_column_id' in func_body or 'self.settings.monday_status_column_id' in func_body:
                print("\n✅ _update_item_status utilise monday_status_column_id")
                self.successes.append("Fonction _update_item_status correctement configurée")
            else:
                # Chercher des valeurs codées en dur
                hardcoded_status_cols = re.findall(r'["\']status["\']|columnId["\']?\s*:\s*["\']status["\']', func_body)
                if hardcoded_status_cols:
                    print(f"\n⚠️  _update_item_status contient des références 'status' codées en dur")
                    self.warnings.append("_update_item_status pourrait avoir des valeurs codées en dur")
                else:
                    print("\n✅ _update_item_status semble correcte (pas de valeurs codées en dur trouvées)")
                    self.successes.append("_update_item_status OK")
        
        return True
    
    def check_env_consistency(self):
        """Vérifie la cohérence du fichier .env."""
        print("\n" + "="*60)
        print("3️⃣  COHÉRENCE DU FICHIER .ENV")
        print("="*60)
        
        env_path = self.root_path / ".env"
        
        if not env_path.exists():
            print("\n⚠️  Fichier .env non trouvé")
            self.warnings.append("Fichier .env absent")
            return False
        
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        # Variables requises
        required_vars = {
            'MONDAY_BOARD_ID': r'^\s*MONDAY_BOARD_ID\s*=\s*(\d+)',
            'MONDAY_STATUS_COLUMN_ID': r'^\s*MONDAY_STATUS_COLUMN_ID\s*=\s*(\S+)',
            'MONDAY_REPOSITORY_URL_COLUMN_ID': r'^\s*MONDAY_REPOSITORY_URL_COLUMN_ID\s*=\s*(\S+)',
        }
        
        print("\n📋 Variables configurées:\n")
        
        all_found = True
        for var_name, pattern in required_vars.items():
            match = re.search(pattern, env_content, re.MULTILINE)
            if match:
                value = match.group(1)
                print(f"   ✅ {var_name} = {value}")
            else:
                print(f"   ❌ {var_name} - NON TROUVÉ")
                self.issues.append(f"{var_name} manquant dans .env")
                all_found = False
        
        if all_found:
            self.successes.append("Toutes les variables requises présentes dans .env")
        
        return all_found
    
    def check_settings_file(self):
        """Vérifie que settings.py charge bien les variables."""
        print("\n" + "="*60)
        print("4️⃣  VÉRIFICATION DU FICHIER SETTINGS.PY")
        print("="*60)
        
        try:
            from config.settings import get_settings
            settings = get_settings()
            
            checks = [
                ('monday_board_id', settings.monday_board_id),
                ('monday_status_column_id', settings.monday_status_column_id),
                ('monday_repository_url_column_id', settings.monday_repository_url_column_id),
            ]
            
            print("\n📋 Chargement des settings:\n")
            
            all_loaded = True
            for name, value in checks:
                if value:
                    print(f"   ✅ {name} = {value}")
                else:
                    print(f"   ❌ {name} = (vide ou None)")
                    self.issues.append(f"Setting {name} vide")
                    all_loaded = False
            
            if all_loaded:
                self.successes.append("Tous les settings chargés correctement")
            
            return all_loaded
            
        except Exception as e:
            print(f"\n❌ Erreur chargement settings: {e}")
            self.issues.append(f"Impossible de charger settings: {e}")
            return False
    
    def check_webhook_service_consistency(self):
        """Vérifie la cohérence du service webhook."""
        print("\n" + "="*60)
        print("5️⃣  COHÉRENCE DU SERVICE WEBHOOK")
        print("="*60)
        
        webhook_service_path = self.root_path / "services" / "webhook_service.py"
        
        if not webhook_service_path.exists():
            print("\n⚠️  webhook_service.py non trouvé")
            return True
        
        with open(webhook_service_path, 'r') as f:
            content = f.read()
        
        # Vérifier que _extract_column_value est utilisé avec settings
        if 'settings.monday_repository_url_column_id' in content:
            print("\n✅ webhook_service utilise settings.monday_repository_url_column_id")
            self.successes.append("webhook_service utilise la configuration")
        else:
            print("\n⚠️  webhook_service pourrait ne pas utiliser la configuration")
            self.warnings.append("webhook_service à vérifier")
        
        return True
    
    def print_summary(self):
        """Affiche le résumé."""
        print("\n" + "="*60)
        print("📊 RÉSUMÉ DE LA VÉRIFICATION COMPLÈTE")
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
            print("✅ AUCUNE INCOHÉRENCE DÉTECTÉE!")
        elif not self.issues:
            print("⚠️  Quelques avertissements mais rien de bloquant")
        else:
            print("❌ Des erreurs doivent être corrigées")
        
        print("="*60 + "\n")
    
    def run_all_checks(self):
        """Lance toutes les vérifications."""
        print("\n" + "="*60)
        print("🔍 VÉRIFICATION COMPLÈTE D'INCOHÉRENCES")
        print("="*60)
        
        self.check_hardcoded_column_ids()
        self.check_status_usage()
        self.check_env_consistency()
        self.check_settings_file()
        self.check_webhook_service_consistency()
        
        self.print_summary()
        
        return len(self.issues) == 0


def main():
    """Point d'entrée principal."""
    checker = ComprehensiveChecker()
    success = checker.run_all_checks()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()


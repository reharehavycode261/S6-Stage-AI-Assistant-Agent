#!/usr/bin/env python3
"""
Script de correction automatique des erreurs Celery détectées.
Applique les 3 corrections critiques identifiées dans CORRECTIONS_URGENTES_CELERY.md
"""

import re
import sys
from pathlib import Path

# Couleurs pour l'affichage
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_step(step: str, message: str):
    """Affiche une étape de correction."""
    print(f"{BLUE}[{step}]{RESET} {message}")

def print_success(message: str):
    """Affiche un message de succès."""
    print(f"{GREEN}✅ {message}{RESET}")

def print_error(message: str):
    """Affiche un message d'erreur."""
    print(f"{RED}❌ {message}{RESET}")

def print_warning(message: str):
    """Affiche un avertissement."""
    print(f"{YELLOW}⚠️  {message}{RESET}")


def correction_1_settings_properties():
    """
    CORRECTION 1: Ajouter les propriétés db_host, db_port, etc. dans config/settings.py
    """
    print_step("1/3", "Ajout des propriétés DB dans config/settings.py")
    
    settings_path = Path("config/settings.py")
    if not settings_path.exists():
        print_error(f"Fichier introuvable: {settings_path}")
        return False
    
    content = settings_path.read_text()
    
    # Vérifier si déjà corrigé
    if "def db_host(self)" in content:
        print_warning("Propriété db_host déjà présente - correction ignorée")
        return True
    
    # Trouver où insérer (après celery_result_backend)
    insert_marker = "def celery_result_backend(self) -> str:"
    
    if insert_marker not in content:
        print_error("Marqueur d'insertion non trouvé")
        return False
    
    # Code à insérer
    db_properties = '''
    
    # Database component properties (extracted from database_url)
    @property
    def db_host(self) -> str:
        """Extrait le host de database_url."""
        import re
        match = re.search(r'@([^:]+):', self.database_url)
        return match.group(1) if match else "localhost"
    
    @property
    def db_port(self) -> int:
        """Extrait le port de database_url."""
        import re
        match = re.search(r':(\d+)/', self.database_url)
        return int(match.group(1)) if match else 5432
    
    @property
    def db_name(self) -> str:
        """Extrait le nom de DB de database_url."""
        import re
        match = re.search(r'/([^?]+)(?:\?|$)', self.database_url)
        return match.group(1) if match else "ai_agent_admin"
    
    @property
    def db_user(self) -> str:
        """Extrait le user de database_url."""
        import re
        match = re.search(r'://([^:]+):', self.database_url)
        return match.group(1) if match else "admin"
    
    @property
    def db_password(self) -> str:
        """Extrait le password de database_url."""
        import re
        match = re.search(r':([^@]+)@', self.database_url)
        return match.group(1) if match else "password"
'''
    
    # Trouver la fin de la méthode celery_result_backend
    lines = content.split('\n')
    insert_line = None
    
    for i, line in enumerate(lines):
        if "def celery_result_backend(self)" in line:
            # Chercher la fin de cette méthode (ligne vide ou nouvelle propriété)
            for j in range(i+1, len(lines)):
                if lines[j].strip() == "" or (lines[j].startswith("    @") or lines[j].startswith("    #") or lines[j].startswith("    def")):
                    insert_line = j
                    break
            break
    
    if insert_line is None:
        print_error("Impossible de trouver le point d'insertion")
        return False
    
    # Insérer le code
    lines.insert(insert_line, db_properties)
    new_content = '\n'.join(lines)
    
    # Backup
    settings_path.with_suffix('.py.backup').write_text(content)
    
    # Écrire le nouveau contenu
    settings_path.write_text(new_content)
    
    print_success("Propriétés DB ajoutées dans config/settings.py")
    return True


def correction_2_test_results_helper():
    """
    CORRECTION 2: Ajouter le helper _convert_test_results_to_dict 
    et l'utiliser dans monday_validation_node.py
    """
    print_step("2/3", "Correction test_results dans nodes/monday_validation_node.py")
    
    node_path = Path("nodes/monday_validation_node.py")
    if not node_path.exists():
        print_error(f"Fichier introuvable: {node_path}")
        return False
    
    content = node_path.read_text()
    
    # Vérifier si déjà corrigé
    if "_convert_test_results_to_dict" in content:
        print_warning("Fonction _convert_test_results_to_dict déjà présente - correction ignorée")
        return True
    
    # 1. Ajouter la fonction helper après les imports
    helper_function = '''

def _convert_test_results_to_dict(test_results) -> Optional[Dict[str, Any]]:
    """
    Convertit test_results en dictionnaire compatible avec HumanValidationRequest.
    
    Args:
        test_results: Peut être une liste ou un dictionnaire
        
    Returns:
        Dictionnaire structuré ou None
    """
    if not test_results:
        return None
    
    # Si déjà un dict, retourner tel quel
    if isinstance(test_results, dict):
        return test_results
    
    # Si c'est une liste, convertir en dict avec structure
    if isinstance(test_results, list):
        return {
            "tests": test_results,
            "count": len(test_results),
            "summary": f"{len(test_results)} test(s) exécuté(s)",
            "success": all(
                test.get("success", False) if isinstance(test, dict) else False 
                for test in test_results
            )
        }
    
    # Fallback: encapsuler dans un dict
    return {"raw": str(test_results), "type": str(type(test_results))}

'''
    
    # Trouver où insérer (après les imports)
    lines = content.split('\n')
    insert_line = None
    
    for i, line in enumerate(lines):
        if line.startswith("async def ") or line.startswith("def "):
            insert_line = i
            break
    
    if insert_line is None:
        print_error("Impossible de trouver le point d'insertion pour la fonction helper")
        return False
    
    lines.insert(insert_line, helper_function)
    
    # 2. Modifier l'appel test_results=workflow_results.get("test_results")
    content_modified = '\n'.join(lines)
    
    # Chercher le pattern et remplacer
    pattern = r'test_results=workflow_results\.get\("test_results"\)'
    replacement = r'test_results=_convert_test_results_to_dict(workflow_results.get("test_results"))'
    
    content_modified = re.sub(pattern, replacement, content_modified)
    
    # Vérifier que le remplacement a été fait
    if replacement.split('=')[1] not in content_modified:
        print_error("Remplacement test_results non effectué")
        return False
    
    # Backup
    node_path.with_suffix('.py.backup').write_text(content)
    
    # Écrire le nouveau contenu
    node_path.write_text(content_modified)
    
    print_success("Fonction _convert_test_results_to_dict ajoutée et utilisée")
    return True


def correction_3_validation_id():
    """
    CORRECTION 3: S'assurer que validation_id n'est jamais None 
    dans services/monday_validation_service.py
    """
    print_step("3/3", "Correction validation_id dans services/monday_validation_service.py")
    
    service_path = Path("services/monday_validation_service.py")
    if not service_path.exists():
        print_error(f"Fichier introuvable: {service_path}")
        return False
    
    content = service_path.read_text()
    
    # Vérifier si déjà corrigé
    if 'validation_id=validation_id or f"validation_' in content:
        print_warning("validation_id déjà corrigé - correction ignorée")
        return True
    
    # Chercher et remplacer les patterns problématiques
    # Pattern 1: return HumanValidationResponse(validation_id=validation_id, ...
    
    # On doit s'assurer que validation_id n'est jamais None
    # Solution: ajouter un import time et générer un ID si None
    
    # 1. Ajouter import time si absent
    if "import time" not in content:
        lines = content.split('\n')
        # Trouver la ligne des imports
        for i, line in enumerate(lines):
            if line.startswith("from datetime import"):
                lines.insert(i+1, "import time")
                break
        content = '\n'.join(lines)
    
    # 2. Remplacer les validation_id dans HumanValidationResponse
    # Pattern à chercher: validation_id=validation_id,
    # Remplacer par: validation_id=validation_id or f"validation_{int(time.time())}",
    
    pattern = r'(\s+)validation_id=validation_id,'
    replacement = r'\1validation_id=validation_id or f"validation_{int(time.time())}_{id(self)}",'
    
    content = re.sub(pattern, replacement, content)
    
    # Backup
    service_path.with_suffix('.py.backup').write_text(service_path.read_text())
    
    # Écrire le nouveau contenu
    service_path.write_text(content)
    
    print_success("validation_id sécurisé avec fallback automatique")
    return True


def main():
    """Applique toutes les corrections."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  🛠️  CORRECTION AUTOMATIQUE DES ERREURS CELERY{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # Vérifier qu'on est dans le bon répertoire
    if not Path("config/settings.py").exists():
        print_error("Veuillez exécuter ce script depuis la racine du projet AI-Agent")
        sys.exit(1)
    
    results = []
    
    # Appliquer les corrections
    results.append(("Propriétés DB (settings.py)", correction_1_settings_properties()))
    results.append(("test_results (monday_validation_node.py)", correction_2_test_results_helper()))
    results.append(("validation_id (monday_validation_service.py)", correction_3_validation_id()))
    
    # Résumé
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  📊 RÉSUMÉ DES CORRECTIONS{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    for name, success in results:
        if success:
            print(f"  {GREEN}✅{RESET} {name}")
        else:
            print(f"  {RED}❌{RESET} {name}")
    
    all_success = all(success for _, success in results)
    
    if all_success:
        print(f"\n{GREEN}{'='*60}")
        print("  ✅ TOUTES LES CORRECTIONS ONT ÉTÉ APPLIQUÉES")
        print(f"{'='*60}{RESET}\n")
        
        print(f"{YELLOW}📝 PROCHAINES ÉTAPES:{RESET}")
        print("  1. Vérifier les fichiers modifiés (des backups .backup ont été créés)")
        print("  2. Redémarrer Celery:")
        print(f"     {BLUE}pkill -f 'celery.*worker' && celery -A services.celery_app worker --loglevel=info{RESET}")
        print("  3. Tester un workflow complet dans Monday.com")
        print("  4. Vérifier les logs:")
        print(f"     {BLUE}tail -f logs/workflow.log | grep -E '(❌|⚠️|Erreur|Error)'{RESET}")
        
        return 0
    else:
        print(f"\n{RED}{'='*60}")
        print("  ❌ CERTAINES CORRECTIONS ONT ÉCHOUÉ")
        print(f"{'='*60}{RESET}\n")
        print("Veuillez appliquer manuellement les corrections qui ont échoué.")
        print("Consultez CORRECTIONS_URGENTES_CELERY.md pour les détails.")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())

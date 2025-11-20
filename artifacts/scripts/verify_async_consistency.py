#!/usr/bin/env python3
"""
Script de vérification de cohérence async/await.

Vérifie que tous les appels aux méthodes async sont correctement faits avec await.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))


class AsyncCallChecker(ast.NodeVisitor):
    """Visiteur AST pour vérifier les appels async."""
    
    def __init__(self):
        self.issues: List[Tuple[str, int, str]] = []
        self.current_file = ""
        self.in_async_function = False
        
        # Méthodes qui doivent être appelées avec await
        self.async_methods = {
            'get_pr_template',
            'get_monday_reply_template',
            '_generate_pr_template_with_llm',
            '_generate_monday_template_with_llm',
            '_generate_pr_content',
        }
    
    def visit_FunctionDef(self, node):
        """Vérifie si on est dans une fonction async."""
        was_async = self.in_async_function
        if isinstance(node, ast.AsyncFunctionDef):
            self.in_async_function = True
        
        self.generic_visit(node)
        
        self.in_async_function = was_async
    
    def visit_Call(self, node):
        """Vérifie les appels de méthodes."""
        # Récupérer le nom de la méthode appelée
        method_name = None
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            method_name = node.func.id
        
        # Si c'est une méthode async sans await
        if method_name in self.async_methods:
            # Vérifier si l'appel est dans un Await
            parent = getattr(node, '_parent', None)
            is_awaited = isinstance(parent, ast.Await)
            
            if not is_awaited:
                self.issues.append((
                    self.current_file,
                    node.lineno,
                    f"Appel à '{method_name}' sans 'await' (méthode async)"
                ))
        
        self.generic_visit(node)


def add_parent_info(node, parent=None):
    """Ajoute l'info du parent à chaque noeud."""
    node._parent = parent
    for child in ast.iter_child_nodes(node):
        add_parent_info(child, node)


def check_file(file_path: Path) -> List[Tuple[str, int, str]]:
    """Vérifie un fichier Python."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        add_parent_info(tree)
        
        checker = AsyncCallChecker()
        checker.current_file = str(file_path)
        checker.visit(tree)
        
        return checker.issues
    except SyntaxError as e:
        print(f"⚠️  Erreur de syntaxe dans {file_path}: {e}")
        return []
    except Exception as e:
        print(f"⚠️  Erreur lors de l'analyse de {file_path}: {e}")
        return []


def main():
    """Fonction principale."""
    print("=" * 80)
    print("🔍 VÉRIFICATION DE COHÉRENCE ASYNC/AWAIT")
    print("=" * 80)
    print()
    
    # Fichiers à vérifier
    project_root = Path(__file__).parent.parent
    files_to_check = [
        project_root / "services" / "project_language_detector.py",
        project_root / "services" / "pull_request_service.py",
        project_root / "services" / "vydata_orchestrator_service.py",
        project_root / "services" / "agent_response_service.py",
        project_root / "nodes" / "monday_validation_node.py",
    ]
    
    # Ajouter tous les fichiers Python dans services/ et nodes/
    for directory in ["services", "nodes"]:
        dir_path = project_root / directory
        if dir_path.exists():
            files_to_check.extend(dir_path.glob("*.py"))
    
    # Supprimer les doublons
    files_to_check = list(set(files_to_check))
    
    print(f"📁 Analyse de {len(files_to_check)} fichiers Python...\n")
    
    all_issues = []
    for file_path in sorted(files_to_check):
        if not file_path.exists():
            continue
        
        issues = check_file(file_path)
        all_issues.extend(issues)
    
    # Afficher les résultats
    if not all_issues:
        print("=" * 80)
        print("✅ AUCUN PROBLÈME DÉTECTÉ !")
        print("=" * 80)
        print()
        print("Tous les appels aux méthodes async utilisent correctement 'await'.")
        print()
        print("Méthodes vérifiées:")
        print("  • get_pr_template()")
        print("  • get_monday_reply_template()")
        print("  • _generate_pr_template_with_llm()")
        print("  • _generate_monday_template_with_llm()")
        print("  • _generate_pr_content()")
        print()
        return 0
    else:
        print("=" * 80)
        print(f"⚠️  {len(all_issues)} PROBLÈME(S) DÉTECTÉ(S)")
        print("=" * 80)
        print()
        
        # Grouper par fichier
        issues_by_file = {}
        for file_path, line_no, message in all_issues:
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append((line_no, message))
        
        for file_path, issues in sorted(issues_by_file.items()):
            print(f"📄 {file_path}")
            for line_no, message in sorted(issues):
                print(f"   Ligne {line_no}: {message}")
            print()
        
        print("💡 Correction suggérée:")
        print("   Ajouter 'await' devant les appels aux méthodes async:")
        print("   template = await project_language_detector.get_pr_template(lang)")
        print()
        
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)


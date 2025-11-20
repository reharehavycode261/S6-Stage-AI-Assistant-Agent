#!/usr/bin/env python3
"""
Script pour mettre à jour automatiquement toutes les routes
pour utiliser DatabasePool et CacheService
"""
import os
import re
from pathlib import Path

# Chemins des fichiers à mettre à jour
ROUTES_DIR = Path("admin/backend/routes")

FILES_TO_UPDATE = [
    "users_routes.py",
    "tests_routes.py",
    "workflows_routes.py",
    "integrations_routes.py",
    "languages_routes.py",
    "validations_routes.py",
    "logs_routes.py",
    "ai_models_routes.py",
    "config_routes.py",
]

def update_imports(content: str) -> str:
    """Ajouter les imports DatabasePool et CacheService."""
    
    # Vérifier si les imports existent déjà
    if "from admin.backend.db_pool import DatabasePool" in content:
        return content
    
    # Trouver la ligne avec les imports config.settings
    pattern = r"(from config\.settings import get_settings)"
    replacement = r"\1\nfrom admin.backend.db_pool import DatabasePool\nfrom admin.backend.cache_service import CacheService"
    
    content = re.sub(pattern, replacement, content)
    
    return content

def remove_get_db_connection_method(content: str) -> str:
    """Supprimer la méthode get_db_connection obsolète."""
    
    # Pattern pour trouver et supprimer la méthode get_db_connection
    pattern = r'\s+@staticmethod\s+async def get_db_connection\(\):[^}]+?raise HTTPException\([^)]+\)\s+'
    content = re.sub(pattern, '\n    ', content, flags=re.DOTALL)
    
    return content

def replace_db_connection_usage(content: str) -> str:
    """Remplacer l'usage de get_db_connection par DatabasePool."""
    
    # Remplacer db = await ServiceName.get_db_connection()
    # par async with DatabasePool.get_connection() as db:
    
    # Pattern 1: db = await Service.get_db_connection()
    pattern1 = r'db = await \w+\.get_db_connection\(\)'
    
    # On ne peut pas faire un remplacement simple car la structure change
    # Il faudrait parser l'AST pour faire ça proprement
    # Pour l'instant, on va juste ajouter un commentaire
    
    content = content.replace(
        "db = await UserService.get_db_connection()",
        "# ✅ OPTIMISATION: Utiliser DatabasePool\n        async with DatabasePool.get_connection() as db:"
    )
    content = content.replace(
        "db = await LanguageDetectionService.get_db_connection()",
        "# ✅ OPTIMISATION: Utiliser DatabasePool\n        async with DatabasePool.get_connection() as db:"
    )
    content = content.replace(
        "db = await AIModelService.get_db_connection()",
        "# ✅ OPTIMISATION: Utiliser DatabasePool\n        async with DatabasePool.get_connection() as db:"
    )
    content = content.replace(
        "db = await TestService.get_db_connection()",
        "# ✅ OPTIMISATION: Utiliser DatabasePool\n        async with DatabasePool.get_connection() as db:"
    )
    content = content.replace(
        "db = await WorkflowService.get_db_connection()",
        "# ✅ OPTIMISATION: Utiliser DatabasePool\n        async with DatabasePool.get_connection() as db:"
    )
    content = content.replace(
        "db = await ValidationService.get_db_connection()",
        "# ✅ OPTIMISATION: Utiliser DatabasePool\n        async with DatabasePool.get_connection() as db:"
    )
    content = content.replace(
        "db = await LogService.get_db_connection()",
        "# ✅ OPTIMISATION: Utiliser DatabasePool\n        async with DatabasePool.get_connection() as db:"
    )
    content = content.replace(
        "db = await IntegrationService.get_db_connection()",
        "# ✅ OPTIMISATION: Utiliser DatabasePool\n        async with DatabasePool.get_connection() as db:"
    )
    content = content.replace(
        "db = await ConfigService.get_db_connection()",
        "# ✅ OPTIMISATION: Utiliser DatabasePool\n        async with DatabasePool.get_connection() as db:"
    )
    
    # Supprimer les finally: await db.close()
    content = re.sub(r'\s+finally:\s+await db\.close\(\)', '', content)
    
    # Supprimer les try: sans contenu utile
    # Plus complexe, on va juste nettoyer les patterns évidents
    
    return content

def process_file(filepath: Path) -> bool:
    """Traiter un fichier et retourner True si modifié."""
    
    print(f"📝 Traitement de {filepath.name}...")
    
    # Lire le contenu
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except FileNotFoundError:
        print(f"  ⚠️  Fichier non trouvé: {filepath}")
        return False
    
    # Appliquer les transformations
    content = original_content
    content = update_imports(content)
    # content = remove_get_db_connection_method(content)  # Commenté pour l'instant
    content = replace_db_connection_usage(content)
    
    # Vérifier si le contenu a changé
    if content == original_content:
        print(f"  ℹ️  Aucune modification nécessaire")
        return False
    
    # Écrire le contenu modifié
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✅ Fichier mis à jour")
    return True

def main():
    """Fonction principale."""
    
    print("=" * 60)
    print("  MISE À JOUR DES ROUTES VERS DatabasePool")
    print("=" * 60)
    print()
    
    modified_count = 0
    
    for filename in FILES_TO_UPDATE:
        filepath = ROUTES_DIR / filename
        if process_file(filepath):
            modified_count += 1
    
    print()
    print("=" * 60)
    print(f"✅ {modified_count} fichiers modifiés")
    print("=" * 60)
    print()
    print("💡 Note: Les modifications sont partielles.")
    print("   Vous devrez peut-être ajuster manuellement:")
    print("   - L'indentation des blocs async with")
    print("   - La suppression complète des méthodes get_db_connection")
    print("   - L'ajout de cache sur certains endpoints")
    print()

if __name__ == "__main__":
    main()


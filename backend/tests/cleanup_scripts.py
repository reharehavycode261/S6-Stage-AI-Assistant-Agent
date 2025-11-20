#!/usr/bin/env python3
"""Script pour nettoyer les scripts de correction temporaires."""

import os
import shutil

def cleanup_scripts():
    """Supprime tous les scripts de correction temporaires."""
    scripts_dir = "scripts"
    
    if os.path.exists(scripts_dir):
        print(f"🗑️ Suppression du dossier {scripts_dir}/...")
        shutil.rmtree(scripts_dir)
        print("✅ Scripts de correction supprimés")
    else:
        print("ℹ️ Aucun script de correction à supprimer")

def main():
    """Fonction principale de nettoyage."""
    print("🧹 Nettoyage des scripts de correction temporaires")
    print("=" * 50)
    
    cleanup_scripts()
    
    print("\n🎉 Nettoyage terminé!")
    print("📁 Les tests fonctionnels sont conservés dans tests/workflow/")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour exporter le Golden Dataset vers Google Sheets.

Ce script permet de :
1. Lire le fichier CSV golden_sets.csv
2. Se connecter à Google Sheets API
3. Créer ou mettre à jour une feuille Google Sheets
4. Exporter les données avec formatage

Prérequis:
    pip install gspread oauth2client
    ou
    pip install gspread google-auth google-auth-oauthlib google-auth-httplib2

Configuration:
    1. Créer un projet sur Google Cloud Console
    2. Activer Google Sheets API
    3. Créer des credentials (Service Account ou OAuth)
    4. Télécharger le fichier credentials.json
"""

import sys
from pathlib import Path
import pandas as pd

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import get_logger

logger = get_logger(__name__)


def export_to_google_sheets_manual():
    """
    Guide pour exporter manuellement vers Google Sheets.
    
    Cette fonction affiche les instructions et génère un fichier
    prêt à être importé dans Google Sheets.
    """
    print("\n" + "="*70)
    print("📊 EXPORT VERS GOOGLE SHEETS - Guide Manuel")
    print("="*70)
    
    # 1. Lire le fichier CSV
    csv_path = Path(__file__).parent.parent / "data/golden_datasets/golden_sets_10_exemples.csv"
    
    if not csv_path.exists():
        # Utiliser le fichier principal si l'exemple n'existe pas
        csv_path = Path(__file__).parent.parent / "data/golden_datasets/golden_sets.csv"
    
    print(f"\n📂 Lecture du fichier: {csv_path}")
    df = pd.read_csv(csv_path)
    
    print(f"✅ {len(df)} lignes chargées")
    print(f"📝 Colonnes: {list(df.columns)}")
    
    # 2. Afficher les instructions
    print("\n" + "="*70)
    print("📋 INSTRUCTIONS POUR GOOGLE SHEETS")
    print("="*70)
    
    print("\n1️⃣  Créer une nouvelle Google Sheet:")
    print("   • Aller sur https://sheets.google.com")
    print("   • Cliquer sur '+ Nouveau' puis 'Google Sheets'")
    print("   • Nommer la feuille: 'Golden Dataset - AI Agent'")
    
    print("\n2️⃣  Importer les données:")
    print("   • Option A - Copier/Coller:")
    print(f"     - Ouvrir le fichier: {csv_path}")
    print("     - Sélectionner tout (Cmd+A ou Ctrl+A)")
    print("     - Copier (Cmd+C ou Ctrl+C)")
    print("     - Dans Google Sheets, coller en A1 (Cmd+V ou Ctrl+V)")
    
    print("\n   • Option B - Import de fichier:")
    print("     - Dans Google Sheets: Fichier > Importer")
    print(f"     - Uploader: {csv_path}")
    print("     - Choisir 'Remplacer la feuille actuelle'")
    print("     - Séparateur: Virgule")
    print("     - Cliquer sur 'Importer les données'")
    
    print("\n3️⃣  Formater la feuille:")
    print("   • Sélectionner la ligne 1 (en-têtes)")
    print("   • Format > Gras")
    print("   • Format > Couleur de remplissage > Bleu clair")
    print("   • Ajuster la largeur des colonnes (double-clic sur les séparateurs)")
    print("   • Activer le filtrage: Données > Créer un filtre")
    
    print("\n4️⃣  Partager la feuille:")
    print("   • Cliquer sur 'Partager' en haut à droite")
    print("   • Ajouter les emails des collaborateurs")
    print("   • Choisir les permissions (Éditeur/Lecteur)")
    
    # 3. Générer un fichier TSV pour copier-coller facile
    tsv_path = csv_path.parent / "golden_sets_for_sheets.tsv"
    df.to_csv(tsv_path, sep='\t', index=False)
    
    print(f"\n✅ Fichier TSV généré: {tsv_path}")
    print("   (Format optimisé pour copier-coller dans Google Sheets)")
    
    # 4. Afficher un aperçu
    print("\n" + "="*70)
    print("📄 APERÇU DES DONNÉES (5 premières lignes)")
    print("="*70)
    print()
    
    for i in range(min(5, len(df))):
        row = df.iloc[i]
        print(f"📝 Ligne {i+1}:")
        print(f"   Input: {row['input_reference'][:80]}...")
        print(f"   Output: {row['output_reference'][:80]}...")
        print()
    
    print("="*70)
    print("✅ Instructions générées avec succès!")
    print("="*70)
    print()


def export_to_google_sheets_api():
    """
    Export automatique vers Google Sheets via API.
    
    Nécessite:
    - pip install gspread google-auth
    - Fichier credentials.json dans le dossier config/
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("\n❌ Bibliothèques manquantes!")
        print("   Installer avec: pip install gspread google-auth")
        return
    
    print("\n" + "="*70)
    print("📊 EXPORT AUTOMATIQUE VERS GOOGLE SHEETS")
    print("="*70)
    
    # 1. Configuration
    credentials_path = Path(__file__).parent.parent / "config/google_sheets_credentials.json"
    
    if not credentials_path.exists():
        print("\n❌ Fichier credentials manquant!")
        print(f"   Attendu: {credentials_path}")
        print("\n📋 Pour créer le fichier credentials:")
        print("   1. Aller sur https://console.cloud.google.com")
        print("   2. Créer un projet ou sélectionner un existant")
        print("   3. Activer 'Google Sheets API'")
        print("   4. Créer un Service Account")
        print("   5. Télécharger la clé JSON")
        print(f"   6. Placer le fichier dans: {credentials_path}")
        return
    
    # 2. Authentification
    print("\n🔐 Authentification...")
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    client = gspread.authorize(creds)
    
    print("✅ Authentifié")
    
    # 3. Lire le CSV
    csv_path = Path(__file__).parent.parent / "data/golden_datasets/golden_sets_10_exemples.csv"
    df = pd.read_csv(csv_path)
    
    print(f"\n📂 Données chargées: {len(df)} lignes")
    
    # 4. Créer ou ouvrir la feuille
    sheet_name = "Golden Dataset - AI Agent"
    
    try:
        # Essayer d'ouvrir la feuille existante
        spreadsheet = client.open(sheet_name)
        print(f"✅ Feuille existante ouverte: {sheet_name}")
    except gspread.SpreadsheetNotFound:
        # Créer une nouvelle feuille
        spreadsheet = client.create(sheet_name)
        print(f"✅ Nouvelle feuille créée: {sheet_name}")
    
    # 5. Obtenir la première worksheet
    worksheet = spreadsheet.sheet1
    worksheet.clear()  # Effacer le contenu existant
    
    # 6. Écrire les en-têtes
    worksheet.update('A1:B1', [list(df.columns)])
    
    # 7. Formater les en-têtes
    worksheet.format('A1:B1', {
        "backgroundColor": {"red": 0.2, "green": 0.5, "blue": 0.8},
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    })
    
    # 8. Écrire les données
    data = df.values.tolist()
    worksheet.update('A2', data)
    
    # 9. Ajuster la largeur des colonnes
    worksheet.set_column_width('A:A', 400)  # input_reference
    worksheet.set_column_width('B:B', 600)  # output_reference
    
    # 10. Activer le retour à la ligne
    worksheet.format('A:B', {"wrapStrategy": "WRAP"})
    
    print(f"\n✅ Export terminé!")
    print(f"🔗 URL: {spreadsheet.url}")
    print(f"📊 {len(df)} lignes exportées")
    
    print("\n💡 Pour partager la feuille:")
    print(f"   1. Ouvrir: {spreadsheet.url}")
    print("   2. Cliquer sur 'Partager'")
    print("   3. Ajouter les collaborateurs")


def main():
    """Point d'entrée principal."""
    print("\n" + "="*70)
    print("📊 EXPORT GOLDEN DATASET VERS GOOGLE SHEETS")
    print("="*70)
    
    print("\nChoisissez une méthode:")
    print("  1. Export manuel (copier-coller)")
    print("  2. Export automatique via API (nécessite credentials)")
    
    choice = input("\nVotre choix (1 ou 2): ").strip()
    
    if choice == "1":
        export_to_google_sheets_manual()
    elif choice == "2":
        export_to_google_sheets_api()
    else:
        print("❌ Choix invalide")


if __name__ == "__main__":
    main()


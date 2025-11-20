#!/usr/bin/env python3
"""Affiche les résultats d'évaluation de manière lisible."""

import json
import glob
from pathlib import Path

# Trouver le dernier rapport
reports_dir = Path("data/evaluation_reports")
reports = sorted(reports_dir.glob("evaluation_questions_*.json"), reverse=True)

if not reports:
    print("❌ Aucun rapport trouvé")
    exit(1)

latest_report = reports[0]
print(f"📄 Rapport: {latest_report.name}\n")

with open(latest_report) as f:
    data = json.load(f)

print("="*70)
print("🎯 RÉSULTATS D'ÉVALUATION")
print("="*70)
print(f"\n📊 Score de fiabilité: {data['reliability_score']}/100 ({data['reliability_status']})")
print(f"✅ Tests réussis: {data['tests_passed']}/{data['total_tests']}")
print(f"📈 Score moyen: {data['average_score']}/100\n")

print("="*70)
print("📋 DÉTAIL DES TESTS")
print("="*70)

for i, r in enumerate(data['results'], 1):
    emoji = "✅" if r['passed'] else "❌"
    print(f"\n{emoji} Test {i}: {r['item_id']}")
    print(f"   Score: {r['score']}/100")
    
    if r.get('error'):
        print(f"   ❌ Erreur: {r['error']}")
    elif r['reasoning']:
        reasoning = r['reasoning'][:200]
        print(f"   💭 {reasoning}...")

print("\n" + "="*70)
if data.get('recommendations'):
    print("💡 RECOMMANDATIONS:")
    for rec in data['recommendations']:
        print(f"   • {rec}")
else:
    print("💡 Aucune recommandation")
print("="*70 + "\n")


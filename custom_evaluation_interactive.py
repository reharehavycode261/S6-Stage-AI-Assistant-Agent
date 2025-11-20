#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interface d'évaluation interactive pour tester l'agent avec vos propres questions.

Utilisation:
    python3 custom_evaluation_interactive.py

Vous pourrez poser 5 questions et l'agent sera évalué automatiquement.
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from services.evaluation.agent_evaluation_service import AgentEvaluationService
from models.evaluation_models import GoldenDatasetItem, EvaluationReport
from utils.logger import get_logger

logger = get_logger(__name__)


class InteractiveEvaluator:
    """
    Évaluateur interactif pour tester l'agent avec vos propres questions.
    """
    
    def __init__(self):
        self.evaluation_service = AgentEvaluationService()
        self.questions: List[Dict[str, Any]] = []
        
    def collect_questions(self) -> None:
        """
        Collecte 5 questions de l'utilisateur de manière interactive.
        """
        print("\n" + "="*70)
        print("🎯 ÉVALUATION INTERACTIVE DE L'AGENT IA")
        print("="*70)
        print("\n📝 Vous allez poser 5 questions à l'agent.")
        print("💡 L'agent sera évalué sur ses réponses par un LLM Judge.")
        print("\n")
        
        # Configuration du repository par défaut
        print("🔧 CONFIGURATION")
        print("-" * 70)
        default_repo = "https://github.com/reharehavycode261/S2-GenericDAO"
        repo = input(f"Repository à analyser [{default_repo}]: ").strip() or default_repo
        
        repo_name = repo.replace("https://github.com/", "")
        
        print(f"\n✅ Repository: {repo}")
        print("\n" + "="*70)
        
        # Collecter les 5 questions
        for i in range(1, 6):
            print(f"\n📌 QUESTION {i}/5")
            print("-" * 70)
            
            question = input(f"❓ Votre question #{i}: ").strip()
            
            if not question:
                print("⚠️  Question vide ignorée")
                continue
            
            # Demander le type de réponse attendue (optionnel)
            print("\n💭 Que devrait répondre l'agent idéalement ?")
            print("   (Appuyez sur Entrée pour laisser le juge décider)")
            expected = input("📋 Réponse attendue: ").strip()
            
            # Déterminer le type de question
            question_lower = question.lower()
            if any(word in question_lower for word in ["commit", "pr", "pull request", "structure", "branch"]):
                q_type = "github_metadata"
            elif any(word in question_lower for word in ["créer", "ajouter", "implémenter", "create", "add"]):
                q_type = "command"
            else:
                q_type = "question"
            
            self.questions.append({
                "id": f"custom_q{i:03d}",
                "type": "questions",
                "input_text": question,
                "input_context": {
                    "repository_url": repo,
                    "repository_name": repo_name,
                    "default_branch": "main"
                },
                "expected_output": expected or "Réponse claire et précise basée sur le contexte du projet",
                "expected_output_metadata": {
                    "type": q_type,
                    "custom": True
                },
                "evaluation_criteria": [
                    "Pertinence de la réponse",
                    "Précision technique",
                    "Clarté de l'explication",
                    "Utilisation du contexte du projet"
                ],
                "description": f"Question personnalisée #{i}: {question[:50]}..."
            })
            
            print(f"✅ Question #{i} enregistrée")
        
        print("\n" + "="*70)
        print(f"✅ {len(self.questions)} questions collectées")
        print("="*70)
    
    def save_custom_dataset(self) -> str:
        """
        Sauvegarde les questions dans un dataset personnalisé.
        
        Returns:
            Chemin du fichier créé
        """
        dataset = {
            "name": "Custom Interactive Dataset",
            "type": "questions",
            "description": "Dataset personnalisé créé via l'interface interactive",
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "items": self.questions
        }
        
        # Créer le dossier si nécessaire
        custom_dir = Path("data/golden_datasets/custom")
        custom_dir.mkdir(parents=True, exist_ok=True)
        
        # Nom de fichier avec timestamp
        filename = f"custom_interactive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = custom_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Dataset sauvegardé: {filepath}")
        return str(filepath)
    
    async def run_evaluation(self, dataset_path: str) -> EvaluationReport:
        """
        Lance l'évaluation avec le dataset personnalisé.
        
        Args:
            dataset_path: Chemin du dataset à évaluer
            
        Returns:
            Rapport d'évaluation complet
        """
        print("\n" + "="*70)
        print("🚀 LANCEMENT DE L'ÉVALUATION")
        print("="*70)
        print("\n⏳ L'agent traite vos questions...")
        print("💡 Cela peut prendre 2-3 minutes\n")
        
        # Charger le dataset
        from models.evaluation_models import GoldenDataset
        with open(dataset_path, 'r', encoding='utf-8') as f:
            dataset_data = json.load(f)
        
        dataset = GoldenDataset(**dataset_data)
        
        # Lancer l'évaluation
        report = await self.evaluation_service.evaluate_dataset(
            dataset_type="custom",
            save_report=True
        )
        
        return report
    
    def display_results(self, report: EvaluationReport) -> None:
        """
        Affiche les résultats de l'évaluation de manière claire.
        
        Args:
            report: Rapport d'évaluation
        """
        print("\n" + "="*70)
        print("📊 RÉSULTATS DE L'ÉVALUATION")
        print("="*70)
        
        # Score global
        reliability = report.global_metrics.reliability_score
        status_emoji = "✅" if reliability >= 70 else "⚠️" if reliability >= 60 else "❌"
        
        print(f"\n{status_emoji} Score de fiabilité: {reliability:.1f}/100")
        print(f"📈 Score moyen: {report.global_metrics.average_score:.1f}/100")
        print(f"✅ Tests réussis: {report.global_metrics.tests_passed}/{report.global_metrics.total_tests}")
        
        # Catégorisation
        if reliability >= 80:
            status = "🌟 EXCELLENT"
        elif reliability >= 70:
            status = "✅ BON"
        elif reliability >= 60:
            status = "⚠️  À AMÉLIORER"
        else:
            status = "❌ NON FIABLE"
        
        print(f"\n🏆 Statut: {status}")
        
        # Détail par question
        print("\n" + "="*70)
        print("📋 DÉTAIL DES RÉPONSES")
        print("="*70)
        
        for i, result in enumerate(report.results, 1):
            passed_emoji = "✅" if result.passed else "❌"
            print(f"\n{passed_emoji} Question {i}: {result.item_id}")
            print(f"   Score: {result.score:.1f}/100")
            
            # Afficher la question
            for question in self.questions:
                if question["id"] == result.item_id:
                    print(f"\n   ❓ Question: {question['input_text']}")
                    break
            
            # Afficher la réponse de l'agent (tronquée)
            print(f"\n   🤖 Réponse de l'agent:")
            output_preview = result.agent_output[:200]
            if len(result.agent_output) > 200:
                output_preview += "..."
            print(f"   {output_preview}")
            
            # Jugement du LLM
            print(f"\n   🎯 Jugement:")
            reasoning_preview = result.reasoning[:150]
            if len(result.reasoning) > 150:
                reasoning_preview += "..."
            print(f"   {reasoning_preview}")
            
            # Scores par critère
            print(f"\n   📊 Scores détaillés:")
            for criterion, score in result.criteria_scores.items():
                bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
                print(f"      {criterion:20s}: {bar} {score:.0f}/100")
        
        print("\n" + "="*70)
        print("💡 RECOMMANDATIONS")
        print("="*70)
        
        if reliability < 60:
            print("❌ L'agent nécessite des améliorations majeures")
            print("   • Vérifier la récupération des données GitHub")
            print("   • Améliorer la compréhension du contexte")
            print("   • Renforcer la précision technique")
        elif reliability < 70:
            print("⚠️  L'agent est fonctionnel mais peut être amélioré")
            print("   • Analyser les questions échouées")
            print("   • Améliorer la clarté des réponses")
        elif reliability < 80:
            print("✅ L'agent fonctionne bien")
            print("   • Quelques ajustements mineurs possibles")
        else:
            print("🌟 L'agent performe excellemment !")
            print("   • Maintenir la qualité actuelle")
        
        # Rapport détaillé sauvegardé
        print(f"\n📄 Rapport complet sauvegardé:")
        print(f"   {report.report_id}")
        print("="*70 + "\n")
    
    async def run(self) -> None:
        """
        Lance le processus complet d'évaluation interactive.
        """
        try:
            # 1. Collecter les questions
            self.collect_questions()
            
            if not self.questions:
                print("❌ Aucune question fournie. Abandon.")
                return
            
            # 2. Sauvegarder le dataset
            dataset_path = self.save_custom_dataset()
            
            # 3. Demander confirmation
            print("\n🔄 Voulez-vous lancer l'évaluation maintenant ? (o/n)")
            confirm = input("👉 ").strip().lower()
            
            if confirm not in ['o', 'oui', 'y', 'yes']:
                print("\n✋ Évaluation annulée.")
                print(f"💾 Vos questions sont sauvegardées dans: {dataset_path}")
                print("💡 Vous pouvez les évaluer plus tard avec:")
                print(f"   curl -X POST http://localhost:8000/evaluation/run?dataset_path={dataset_path}")
                return
            
            # 4. Lancer l'évaluation
            report = await self.run_evaluation(dataset_path)
            
            # 5. Afficher les résultats
            self.display_results(report)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Évaluation interrompue par l'utilisateur")
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            logger.error(f"Erreur évaluation interactive: {e}", exc_info=True)


async def main():
    """Point d'entrée principal."""
    evaluator = InteractiveEvaluator()
    await evaluator.run()


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║          🎯 ÉVALUATION INTERACTIVE DE L'AGENT IA            ║
    ║                                                              ║
    ║  Ce système utilise les Golden Datasets pour évaluer        ║
    ║  la fiabilité de l'agent sur VOS propres questions.         ║
    ║                                                              ║
    ║  📝 Posez 5 questions                                       ║
    ║  🤖 L'agent y répond                                        ║
    ║  👨‍⚖️  Un LLM Judge évalue les réponses                       ║
    ║  📊 Vous obtenez un score de fiabilité                      ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())


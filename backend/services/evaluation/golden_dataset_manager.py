"""
Golden Dataset Manager - Gestion des datasets d'évaluation.

Responsabilités:
    - Charger/sauvegarder les Golden Datasets (EXCEL/CSV)
    - Valider la structure des datasets
    - Gérer les résultats d'évaluation
    - Calculer les métriques de performance
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class GoldenDatasetManager:
    """
    Gestionnaire des Golden Datasets pour l'évaluation de l'agent - Version simplifiée.
    
    Structure simplifiée:
    - golden_sets.csv: Seulement 2 colonnes (input_reference, output_reference)
    - evaluation_results.csv: Résultats avec scores LLM-as-judge
    """
    
    def __init__(self, datasets_dir: Optional[Path] = None):
        """
        Initialise le gestionnaire de datasets.
        
        Args:
            datasets_dir: Répertoire contenant les datasets.
                         Par défaut: <project_root>/data/golden_datasets/
        """
        if datasets_dir is None:
            project_root = Path(__file__).parent.parent.parent
            datasets_dir = project_root / "data" / "golden_datasets"
        
        self.datasets_dir = Path(datasets_dir)
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        
        self.golden_sets_csv = self.datasets_dir / "golden_sets.csv"
        self.evaluation_results_csv = self.datasets_dir / "evaluation_results.csv"
        
        logger.info(f"✅ GoldenDatasetManager initialisé: {self.datasets_dir} (Mode simplifié: input_reference + output_reference)")
    
    def load_golden_sets(self) -> pd.DataFrame:
        """
        Charge les tests du Golden Set depuis CSV (structure simplifiée).
        
        Le CSV contient seulement 2 colonnes:
        - input_reference: La question/commande de test
        - output_reference: La réponse attendue
            
        Returns:
            DataFrame avec les tests (input_reference, output_reference)
        """
        try:
            if not self.golden_sets_csv.exists():
                logger.error(f"❌ Fichier Golden Sets introuvable: {self.golden_sets_csv}")
                raise FileNotFoundError(f"Golden Sets CSV not found: {self.golden_sets_csv}")
            
            df = pd.read_csv(self.golden_sets_csv)
            
            required_cols = ['input_reference', 'output_reference']
            if not all(col in df.columns for col in required_cols):
                raise ValueError(f"Le CSV doit contenir les colonnes: {required_cols}")
            
            logger.info(f"📂 Chargé {len(df)} tests depuis Golden Sets")
            return df
        
        except Exception as e:
            logger.error(f"❌ Erreur chargement Golden Sets: {e}", exc_info=True)
            raise
    
    def get_test_by_index(self, index: int) -> Dict[str, Any]:
        """
        Récupère un test spécifique par son index (ligne).
        
        Args:
            index: Index du test (0-based).
            
        Returns:
            Dictionnaire avec input_reference et output_reference.
        """
        df = self.load_golden_sets()
        
        if index < 0 or index >= len(df):
            raise ValueError(f"Index invalide: {index}. Le dataset contient {len(df)} tests.")
        
        return df.iloc[index].to_dict()
    
    def save_evaluation_result(self, result: Dict[str, Any]) -> None:
        """
        Sauvegarde un résultat d'évaluation dans CSV (structure simplifiée).
        
        Args:
            result: Dictionnaire avec: input_reference, output_reference, agent_output, 
                    score, reasoning, passed, evaluated_at
        """
        try:
            try:
                df_results = pd.read_csv(self.evaluation_results_csv)
            except FileNotFoundError:
                df_results = pd.DataFrame(columns=[
                    'timestamp', 'input_reference', 'output_reference', 'agent_output',
                    'llm_score', 'llm_reasoning', 'passed', 'duration_seconds'
                ])
            
            new_row = pd.DataFrame([result])
            
            df_results = pd.concat([df_results, new_row], ignore_index=True)
            
            df_results.to_csv(self.evaluation_results_csv, index=False)
            
            logger.info(f"✅ Résultat d'évaluation sauvegardé (score: {result.get('llm_score', 'N/A')})")
        
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde résultat: {e}", exc_info=True)
            raise
    
    
    def get_evaluation_results(self, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Récupère les résultats d'évaluation.
        
        Args:
            limit: Limiter le nombre de résultats (les plus récents).
            
        Returns:
            DataFrame avec les résultats.
        """
        try:
            df = pd.read_csv(self.evaluation_results_csv)
            
            if 'timestamp' in df.columns:
                df = df.sort_values('timestamp', ascending=False)
            
            if limit:
                df = df.head(limit)
            
            return df
            
        except FileNotFoundError:
            logger.warning("⚠️ Aucun résultat d'évaluation trouvé")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"❌ Erreur récupération résultats: {e}", exc_info=True)
            raise
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """
        Génère un résumé statistique simplifié.
        
        Returns:
            Dictionnaire avec statistiques globales.
        """
        try:
            df_results = pd.read_csv(self.evaluation_results_csv)
            
            total_evals = len(df_results)
            if total_evals == 0:
                return {"message": "Aucune évaluation disponible"}
            
            summary = {
                "total_evaluations": total_evals,
                "passed": len(df_results[df_results['passed'] == True]),
                "failed": len(df_results[df_results['passed'] == False]),
                "pass_rate": round((df_results['passed'] == True).sum() / total_evals * 100, 1),
                "avg_score": round(df_results['llm_score'].mean(), 1),
                "best_score": round(df_results['llm_score'].max(), 1),
                "worst_score": round(df_results['llm_score'].min(), 1),
                "avg_duration_seconds": round(df_results['duration_seconds'].mean(), 1) if 'duration_seconds' in df_results.columns else None
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Erreur génération statistiques: {e}", exc_info=True)
            return {"error": str(e)}

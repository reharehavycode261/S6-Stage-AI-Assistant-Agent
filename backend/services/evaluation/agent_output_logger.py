"""
Agent Output Logger - Service pour logger automatiquement les inputs/outputs de l'agent dans Excel.

Flux simplifié:
1. Update Monday → Agent traite
2. Agent génère output (analyse ou PR)
3. Logger stocke automatiquement input + output dans Excel
4. Calcul de performance se fait plus tard à partir des données Excel

Pas de feedback humain requis, juste du logging automatique.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class AgentOutputLogger:
    """
    Service pour logger automatiquement les interactions de l'agent dans Excel/CSV.
    """
    
    def __init__(self, datasets_dir: Optional[Path] = None):
        """
        Initialise le logger.
        
        Args:
            datasets_dir: Répertoire des datasets. Par défaut: data/golden_datasets/
        """
        if datasets_dir is None:
            project_root = Path(__file__).parent.parent.parent
            datasets_dir = project_root / "data" / "golden_datasets"
        
        self.datasets_dir = Path(datasets_dir)
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        
        self.agent_interactions_csv = self.datasets_dir / "agent_interactions_log.csv"
        
        self._initialize_log_file()
        
        logger.info(f"✅ AgentOutputLogger initialisé: {self.agent_interactions_csv}")
    
    def _initialize_log_file(self):
        """Crée le fichier CSV de log s'il n'existe pas."""
        if not self.agent_interactions_csv.exists():
            df = pd.DataFrame(columns=[
                'interaction_id',
                'timestamp',
                'monday_update_id',
                'monday_item_id',
                'interaction_type',  
                'input_text',
                'agent_output',
                'duration_seconds',
                'success',
                'error_message',
                'metadata',
                'repository_url',
                'branch_name',
                'pr_number',
                'pr_url',
                'assigned_to',
                'creator_name'
            ])
            df.to_csv(self.agent_interactions_csv, index=False)
            logger.info(f"📄 Fichier de log créé: {self.agent_interactions_csv}")
    
    def log_agent_interaction(
        self,
        monday_update_id: str,
        monday_item_id: str,
        input_text: str,
        agent_output: str,
        interaction_type: str,
        duration_seconds: float = 0.0,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        repository_url: Optional[str] = None,
        branch_name: Optional[str] = None,
        pr_number: Optional[str] = None,
        pr_url: Optional[str] = None,
        assigned_to: Optional[str] = None,
        creator_name: Optional[str] = None
    ) -> str:
        """
        Log une interaction de l'agent dans Excel/CSV.
        
        Args:
            monday_update_id: ID de l'update Monday qui a déclenché l'agent.
            monday_item_id: ID de l'item Monday.
            input_text: Le texte d'entrée (question ou commande).
            agent_output: La réponse générée par l'agent.
            interaction_type: Type d'interaction ('analysis' ou 'pr').
            duration_seconds: Durée d'exécution.
            success: Si l'interaction a réussi.
            error_message: Message d'erreur si échec.
            metadata: Métadonnées additionnelles (dict).
            repository_url: URL du repository GitHub.
            branch_name: Nom de la branche (pour les PRs).
            pr_number: Numéro de la PR (pour les PRs).
            pr_url: URL de la PR (pour les PRs).
            assigned_to: Utilisateur assigné.
            creator_name: Créateur de la tâche.
            
        Returns:
            interaction_id: ID unique de l'interaction loggée.
        """
        try:
            interaction_id = f"INT_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            df_log = pd.read_csv(self.agent_interactions_csv)
            
            new_interaction = {
                'interaction_id': interaction_id,
                'timestamp': datetime.now().isoformat(),
                'monday_update_id': monday_update_id,
                'monday_item_id': monday_item_id,
                'interaction_type': interaction_type,
                'input_text': input_text,
                'agent_output': agent_output,
                'duration_seconds': round(duration_seconds, 2),
                'success': success,
                'error_message': error_message if error_message else '',
                'metadata': str(metadata) if metadata else '',
                'repository_url': repository_url if repository_url else '',
                'branch_name': branch_name if branch_name else '',
                'pr_number': pr_number if pr_number else '',
                'pr_url': pr_url if pr_url else '',
                'assigned_to': assigned_to if assigned_to else '',
                'creator_name': creator_name if creator_name else ''
            }
            
            df_log = pd.concat([df_log, pd.DataFrame([new_interaction])], ignore_index=True)
            
            df_log.to_csv(self.agent_interactions_csv, index=False)
            
            logger.info(
                f"✅ Interaction loggée: {interaction_id} "
                f"(type={interaction_type}, success={success})"
            )
            
            return interaction_id
            
        except Exception as e:
            logger.error(f"❌ Erreur logging interaction: {e}", exc_info=True)
            raise
    
    def get_interactions(
        self,
        interaction_type: Optional[str] = None,
        success_only: bool = False,
        limit: Optional[int] = None,
        since_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Récupère les interactions loggées avec filtres.
        
        Args:
            interaction_type: Filtrer par type ('analysis' ou 'pr').
            success_only: Ne retourner que les interactions réussies.
            limit: Limiter le nombre de résultats.
            since_date: Filtrer depuis une date (format: 'YYYY-MM-DD').
            
        Returns:
            DataFrame avec les interactions.
        """
        try:
            df = pd.read_csv(self.agent_interactions_csv)
            
            if interaction_type:
                df = df[df['interaction_type'] == interaction_type]
            
            if success_only:
                df = df[df['success'] == True]
            
            if since_date:
                df['date'] = pd.to_datetime(df['timestamp']).dt.date
                df = df[df['date'] >= pd.to_datetime(since_date).date()]
            
            if limit:
                df = df.tail(limit)  
            
            return df
            
        except FileNotFoundError:
            logger.warning("⚠️ Aucune interaction loggée")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"❌ Erreur récupération interactions: {e}", exc_info=True)
            raise
    
    def calculate_performance_metrics(
        self,
        date: Optional[str] = None,
        save_to_metrics: bool = True
    ) -> Dict[str, Any]:
        """
        Calcule les métriques de performance à partir des interactions loggées.
        
        Args:
            date: Date pour calculer les métriques (format: 'YYYY-MM-DD'). 
                  Par défaut: aujourd'hui.
            save_to_metrics: Si True, sauvegarde dans performance_metrics.csv.
            
        Returns:
            Dictionnaire avec les métriques calculées.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        try:
            df = self.get_interactions(since_date=date)
            df['date'] = pd.to_datetime(df['timestamp']).dt.date
            df_day = df[df['date'] == pd.to_datetime(date).date()]
            
            if len(df_day) == 0:
                logger.warning(f"⚠️ Aucune interaction pour {date}")
                return {
                    'metric_date': date,
                    'total_interactions': 0,
                    'message': 'Aucune interaction ce jour'
                }
            
            total = len(df_day)
            success_count = len(df_day[df_day['success'] == True])
            failed_count = total - success_count
            
            success_rate = (success_count / total * 100) if total > 0 else 0
            avg_duration = df_day['duration_seconds'].mean()
            
            interactions_analysis = len(df_day[df_day['interaction_type'] == 'analysis'])
            interactions_pr = len(df_day[df_day['interaction_type'] == 'pr'])
            
            metrics = {
                'metric_date': date,
                'total_interactions': total,
                'interactions_analysis': interactions_analysis,
                'interactions_pr': interactions_pr,
                'success_count': success_count,
                'failed_count': failed_count,
                'success_rate_percent': round(success_rate, 1),
                'avg_duration_seconds': round(avg_duration, 2),
                'reliability_status': self._compute_reliability_status(success_rate),
                'notes': f"{failed_count} échecs" if failed_count > 0 else "Tout OK"
            }
            
            if save_to_metrics:
                self._save_to_performance_metrics(metrics)
            
            logger.info(
                f"📊 Métriques calculées pour {date}: "
                f"{success_count}/{total} succès ({success_rate:.1f}%)"
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul métriques: {e}", exc_info=True)
            raise
    
    def _save_to_performance_metrics(self, metrics: Dict[str, Any]):
        """Sauvegarde les métriques dans performance_metrics.csv."""
        try:
            metrics_file = self.datasets_dir / "performance_metrics.csv"
            
            try:
                df_metrics = pd.read_csv(metrics_file)
            except FileNotFoundError:
                df_metrics = pd.DataFrame()
            
            metric_date = metrics['metric_date']
            df_metrics = df_metrics[df_metrics['metric_date'] != metric_date]
            
            new_metric = pd.DataFrame([metrics])
            df_metrics = pd.concat([df_metrics, new_metric], ignore_index=True)
            
            df_metrics = df_metrics.sort_values('metric_date', ascending=False)
            
            df_metrics.to_csv(metrics_file, index=False)
            
            logger.info(f"✅ Métriques sauvegardées dans {metrics_file}")
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde métriques: {e}", exc_info=True)
    
    @staticmethod
    def _compute_reliability_status(success_rate: float) -> str:
        """Calcule le statut de fiabilité basé sur le taux de succès."""
        if success_rate >= 95:
            return "excellent"
        elif success_rate >= 85:
            return "good"
        elif success_rate >= 70:
            return "acceptable"
        else:
            return "needs_improvement"
    
    def get_statistics_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Génère un résumé statistique sur les N derniers jours.
        
        Args:
            days: Nombre de jours à analyser.
            
        Returns:
            Dictionnaire avec statistiques globales.
        """
        try:
            start_date = (datetime.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
            
            df = self.get_interactions(since_date=start_date)
            
            if df.empty:
                return {"message": f"Aucune interaction dans les {days} derniers jours"}
            
            total = len(df)
            success = len(df[df['success'] == True])
            failed = total - success
            
            summary = {
                "period_days": days,
                "start_date": start_date,
                "end_date": datetime.now().strftime("%Y-%m-%d"),
                "total_interactions": total,
                "success_count": success,
                "failed_count": failed,
                "success_rate": round((success / total * 100), 1) if total > 0 else 0,
                "interactions_analysis": len(df[df['interaction_type'] == 'analysis']),
                "interactions_pr": len(df[df['interaction_type'] == 'pr']),
                "avg_duration_seconds": round(df['duration_seconds'].mean(), 2),
                "total_duration_hours": round(df['duration_seconds'].sum() / 3600, 2)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Erreur génération statistiques: {e}", exc_info=True)
            return {"error": str(e)}
    
    def export_to_excel(self, output_file: Optional[Path] = None):
        """
        Exporte toutes les interactions vers un fichier Excel avec formatage.
        
        Args:
            output_file: Chemin du fichier de sortie. 
                        Par défaut: agent_interactions_export.xlsx
        """
        try:
            if output_file is None:
                output_file = self.datasets_dir / "agent_interactions_export.xlsx"
            
            df = pd.read_csv(self.agent_interactions_csv)
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Interactions', index=False)
            
            logger.info(f"✅ Export Excel créé: {output_file} ({len(df)} interactions)")
            
            return str(output_file)
            
        except Exception as e:
            logger.error(f"❌ Erreur export Excel: {e}", exc_info=True)
            raise


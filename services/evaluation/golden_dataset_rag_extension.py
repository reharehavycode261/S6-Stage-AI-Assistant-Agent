"""
Extension RAG pour Golden Dataset - Support Multilingue avec Embeddings.

Cette extension AJOUTE les fonctionnalités suivantes AU système existant:
- Stockage des embeddings des golden examples
- Recherche sémantique multilingue
- Détection automatique de langue
- Enrichissement de l'évaluation avec similarité vectorielle

⚠️ NE SUPPRIME PAS la logique existante du GoldenDatasetManager.
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import asyncio

from services.embedding_service import embedding_service, EmbeddingResult
from services.vector_store_service import vector_store_service, SimilaritySearchResult
from services.semantic_search_service import semantic_search_service
from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from utils.logger import get_logger

logger = get_logger(__name__)


class GoldenDatasetRAGExtension:
    """
    Extension RAG pour le Golden Dataset Manager.
    
    Fonctionnalités ajoutées:
    - Indexation des golden examples dans le vector store
    - Recherche sémantique multilingue
    - Détection de langue automatique
    - Métriques de similarité pour l'évaluation
    
    Utilise le GoldenDatasetManager existant comme base.
    """
    
    def __init__(self, golden_dataset_manager: Optional[GoldenDatasetManager] = None):
        """
        Initialise l'extension RAG.
        
        Args:
            golden_dataset_manager: Instance du manager existant (optionnel).
        """
        self.manager = golden_dataset_manager or GoldenDatasetManager()
        self.vector_store_initialized = False
        
        logger.info("✅ GoldenDatasetRAGExtension initialisée (Extension multilingue)")
    
    async def initialize(self):
        """Initialise les services d'embeddings et vector store."""
        if not self.vector_store_initialized:
            await vector_store_service.initialize()
            self.vector_store_initialized = True
            logger.info("✅ Vector store initialisé pour golden datasets")
    
    async def index_golden_dataset(
        self,
        dataset_df: Optional[pd.DataFrame] = None,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Indexe les golden examples dans le vector store avec embeddings.
        
        Args:
            dataset_df: DataFrame à indexer (optionnel, charge depuis manager si None)
            force_reindex: Forcer la réindexation même si déjà indexé
            
        Returns:
            Statistiques d'indexation
        """
        await self.initialize()
        
        logger.info("📚 Indexation des golden examples avec embeddings...")
        
        if dataset_df is None:
            dataset_df = self.manager.load_golden_sets()
        
        if not force_reindex:
            existing_stats = await vector_store_service.get_statistics()
            if existing_stats.get('total_contexts', 0) > 0:
                logger.info(f"ℹ️  {existing_stats['total_contexts']} golden examples déjà indexés")
                user_choice = input("Réindexer? (o/n): ").strip().lower()
                if user_choice != 'o':
                    return {"message": "Indexation annulée par l'utilisateur", "indexed_count": 0}
        
        indexed_count = 0
        languages_detected = {}
        errors = []
        
        for idx, row in dataset_df.iterrows():
            try:
                input_ref = str(row.get('input_reference', ''))
                output_ref = str(row.get('output_reference', ''))
                
                if not input_ref or input_ref == 'nan':
                    logger.warning(f"⚠️  Ligne {idx}: input_reference vide, ignorée")
                    continue
                
                language = await semantic_search_service._detect_language(input_ref)
                languages_detected[language] = languages_detected.get(language, 0) + 1
                
                embedding_result = await embedding_service.generate_embedding(input_ref)
                
                context_type = "golden_example"
                repository_url = "golden_dataset"  
                
                context_text = f"Question: {input_ref}\nRéponse attendue: {output_ref[:500]}"
                
                record_id = await vector_store_service.store_project_context_embedding(
                    repository_url=repository_url,
                    repository_name="Golden Dataset",
                    context_text=context_text,
                    context_type=context_type,
                    embedding=embedding_result.embedding,
                    metadata={
                        "dataset_index": int(idx),
                        "input_reference": input_ref,
                        "output_reference": output_ref[:200],  
                        "language": language,
                        "indexed_at": datetime.now().isoformat(),
                        "type": row.get('type', 'unknown')
                    }
                )
                
                indexed_count += 1
                logger.info(f"✅ Golden example {idx} indexé (ID={record_id}, lang={language})")
                
            except Exception as e:
                error_msg = f"Ligne {idx}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"❌ Erreur indexation ligne {idx}: {e}")
        
        stats = {
            "total_rows": len(dataset_df),
            "indexed_count": indexed_count,
            "errors_count": len(errors),
            "languages_detected": languages_detected,
            "errors": errors[:10]  
        }
        
        logger.info(f"✅ Indexation terminée: {indexed_count}/{len(dataset_df)} golden examples")
        logger.info(f"   • Langues détectées: {languages_detected}")
        
        return stats
    
    async def find_similar_golden_examples(
        self,
        query: str,
        top_k: int = 3,
        language: Optional[str] = None,
        match_threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Trouve les golden examples les plus similaires à une requête.
        
        Args:
            query: Question/commande à rechercher
            top_k: Nombre d'exemples à retourner
            language: Filtrer par langue (optionnel)
            match_threshold: Seuil de similarité (0.0-1.0)
            
        Returns:
            Liste de golden examples similaires avec scores
        """
        await self.initialize()
        
        query_embedding_result = await embedding_service.generate_embedding(query)
        
        similar_contexts = await vector_store_service.search_similar_project_contexts(
            query_embedding=query_embedding_result.embedding,
            repository_url="golden_dataset",
            context_type="golden_example",
            match_threshold=match_threshold,
            top_k=top_k
        )
        
        if language:
            similar_contexts = [
                ctx for ctx in similar_contexts
                if ctx.metadata.get('language') == language
            ]
        
        results = []
        for ctx in similar_contexts:
            results.append({
                "dataset_index": ctx.metadata.get('dataset_index'),
                "input_reference": ctx.metadata.get('input_reference'),
                "output_reference": ctx.metadata.get('output_reference'),
                "language": ctx.metadata.get('language'),
                "similarity_score": ctx.similarity,
                "type": ctx.metadata.get('type', 'unknown')
            })
        
        logger.info(f"🔍 Trouvé {len(results)} golden examples similaires (seuil: {match_threshold})")
        
        return results
    
    async def evaluate_with_similarity_context(
        self,
        agent_input: str,
        agent_output: str,
        find_similar: bool = True,
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Évalue une réponse de l'agent avec contexte de similarité.
        
        Ajoute des golden examples similaires pour enrichir l'évaluation.
        
        Args:
            agent_input: Question/commande envoyée à l'agent
            agent_output: Réponse de l'agent
            find_similar: Chercher des exemples similaires
            top_k: Nombre d'exemples similaires
            
        Returns:
            Contexte d'évaluation enrichi
        """
        await self.initialize()
    
        input_language = await semantic_search_service._detect_language(agent_input)
        
        similar_examples = []
        if find_similar:
            similar_examples = await self.find_similar_golden_examples(
                query=agent_input,
                top_k=top_k,
                language=input_language  
            )
        
        evaluation_context = {
            "agent_input": agent_input,
            "agent_output": agent_output,
            "input_language": input_language,
            "similar_golden_examples": similar_examples,
            "similar_count": len(similar_examples),
            "max_similarity": max([ex['similarity_score'] for ex in similar_examples], default=0.0),
            "evaluated_at": datetime.now().isoformat()
        }
        
        return evaluation_context
    
    async def get_golden_dataset_statistics(self) -> Dict[str, Any]:
        """
        Récupère des statistiques sur le golden dataset indexé.
        
        Returns:
            Statistiques détaillées
        """
        await self.initialize()
        
        vector_stats = await vector_store_service.get_statistics()
        
        classic_stats = self.manager.get_statistics_summary()
        
        combined_stats = {
            "classic_evaluation": classic_stats,
            "vector_store": {
                "total_indexed_contexts": vector_stats.get('total_contexts', 0),
                "total_messages": vector_stats.get('total_messages', 0),
                "languages_count": vector_stats.get('languages_count', 0)
            },
            "rag_extension_enabled": True,
            "timestamp": datetime.now().isoformat()
        }
        
        return combined_stats
    
    async def compare_evaluation_methods(
        self,
        agent_input: str,
        agent_output: str,
        expected_output: str
    ) -> Dict[str, Any]:
        """
        Compare l'évaluation classique vs évaluation enrichie avec RAG.
        
        Args:
            agent_input: Question/commande
            agent_output: Réponse de l'agent
            expected_output: Réponse attendue
            
        Returns:
            Comparaison des deux méthodes
        """
        await self.initialize()
        
        classic_result = {
            "method": "classic",
            "input": agent_input,
            "output": agent_output,
            "expected": expected_output
        }
        
        rag_context = await self.evaluate_with_similarity_context(
            agent_input=agent_input,
            agent_output=agent_output,
            find_similar=True,
            top_k=3
        )
        
        rag_result = {
            "method": "rag_enriched",
            "input": agent_input,
            "output": agent_output,
            "expected": expected_output,
            "similar_examples_found": rag_context['similar_count'],
            "max_similarity": rag_context['max_similarity'],
            "language": rag_context['input_language'],
            "similar_examples": rag_context['similar_golden_examples']
        }
        
        comparison = {
            "classic_evaluation": classic_result,
            "rag_enriched_evaluation": rag_result,
            "improvement": {
                "has_similar_context": rag_context['similar_count'] > 0,
                "similarity_boost": rag_context['max_similarity'] > 0.7,
                "language_detected": True
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return comparison


golden_dataset_rag_extension = GoldenDatasetRAGExtension()


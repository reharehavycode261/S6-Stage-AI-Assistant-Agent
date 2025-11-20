# -*- coding: utf-8 -*-
"""Utilitaires pour formater les commentaires Monday.com avec signatures d'agent."""

import uuid
from datetime import datetime
from typing import Optional


class MondayCommentFormatter:
    """Formateur de commentaires Monday.com avec signatures d'agent."""
    
    # Signature cachée pour identifier les messages de l'agent
    AGENT_SIGNATURE = "<!-- AI_AGENT_SIGNATURE_{uuid} -->"
    
    # Signature visible pour les utilisateurs
    AGENT_FOOTER = "\n\n---\n🤖 **AI-AGENT** 🤖 - Workflow automatisé"
    
    @classmethod
    def format_creator_tag(cls, creator_name: Optional[str]) -> str:
        """
        Formate un tag pour mentionner le créateur du ticket.
        
        Args:
            creator_name: Nom du créateur (peut être None)
            
        Returns:
            Tag formaté (ex: "@Jean Dupont") ou chaîne vide si pas de créateur
        """
        if not creator_name or not isinstance(creator_name, str) or not creator_name.strip():
            return ""
        
        # Monday.com utilise le format @{nom} pour les mentions
        return f"@{creator_name.strip()}"
    
    @classmethod
    def format_agent_comment(cls, comment: str, include_visible_signature: bool = True) -> str:
        """
        Formate un commentaire avec les signatures d'agent.
        
        Args:
            comment: Commentaire original
            include_visible_signature: Inclure la signature visible pour l'utilisateur
            
        Returns:
            Commentaire formaté avec signatures
        """
        # Générer un UUID unique pour ce commentaire
        comment_uuid = str(uuid.uuid4())[:8]
        
        # Ajouter la signature cachée (HTML comment)
        hidden_signature = cls.AGENT_SIGNATURE.format(uuid=comment_uuid)
        formatted_comment = f"{hidden_signature}\n{comment}"
        
        # Ajouter la signature visible si demandée
        if include_visible_signature:
            formatted_comment += cls.AGENT_FOOTER
        
        return formatted_comment
    
    @classmethod
    def format_workflow_completion(
        cls, 
        success: bool, 
        pr_url: Optional[str] = None,
        test_results: Optional[str] = None,
        errors: Optional[str] = None
    ) -> str:
        """
        Formate un commentaire de fin de workflow.
        
        Args:
            success: True si le workflow a réussi
            pr_url: URL de la pull request créée
            test_results: Résultats des tests
            errors: Erreurs rencontrées
            
        Returns:
            Commentaire formaté
        """
        if success:
            comment = "🎯 **Workflow terminé avec succès !**\n\n"
            
            if pr_url:
                comment += f"✅ **Pull Request créée:** {pr_url}\n"
            
            if test_results:
                comment += f"📊 **Tests:** {test_results}\n"
            
            comment += "\n✨ **Prochaines étapes:**\n"
            comment += "1. Reviewer le code dans la Pull Request\n"
            comment += "2. Valider les modifications\n"
            comment += "3. Merger si tout est OK\n"
            
        else:
            comment = "❌ **Workflow échoué**\n\n"
            
            if errors:
                comment += f"🔧 **Erreurs rencontrées:**\n{errors}\n\n"
            
            comment += "🔄 **Actions suggérées:**\n"
            comment += "1. Vérifier les erreurs ci-dessus\n"
            comment += "2. Corriger les problèmes identifiés\n"
            comment += "3. Relancer le workflow si nécessaire\n"
        
        return cls.format_agent_comment(comment)
    
    @classmethod
    def format_validation_request(
        cls,
        pr_url: str,
        test_summary: str,
        changes_summary: str
    ) -> str:
        """
        Formate une demande de validation humaine.
        
        Args:
            pr_url: URL de la pull request
            test_summary: Résumé des tests
            changes_summary: Résumé des modifications
            
        Returns:
            Commentaire formaté
        """
        comment = "🤝 **Validation humaine requise**\n\n"
        comment += f"📋 **Pull Request créée:** {pr_url}\n\n"
        comment += f"📊 **Tests:** {test_summary}\n\n"
        comment += f"🔧 **Modifications:** {changes_summary}\n\n"
        comment += "**Répondez dans ce thread:**\n"
        comment += "• ✅ **'oui'** ou **'approve'** pour valider et merger\n"
        comment += "• ❌ **'non'** ou **'debug'** pour corriger\n"
        comment += "• ❓ Toute question pour plus de détails\n"
        
        return cls.format_agent_comment(comment)
    
    @classmethod
    def format_reactivation_acknowledgment(cls, original_update: str, creator_name: Optional[str] = None) -> str:
        """
        Formate un accusé de réception de réactivation.
        
        Args:
            original_update: Texte de l'update qui a déclenché la réactivation
            creator_name: Nom du créateur du ticket (pour tagging)
            
        Returns:
            Commentaire formaté
        """
        # ✅ NOUVEAU: Tag du créateur pour notification
        creator_tag = ""
        if creator_name:
            creator_tag = cls.format_creator_tag(creator_name)
            if creator_tag:
                creator_tag = f"{creator_tag} "  # Ajouter espace après le tag
        
        # ⚠️ IMPORTANT: Ne pas inclure @vydata dans la citation pour éviter les boucles
        update_without_mention = original_update.replace("@vydata", "").replace("@VyData", "").strip()
        
        comment = f"{creator_tag}🔄 **Nouvelle demande détectée - Réactivation du workflow**\n\n"
        comment += f"📝 **Demande:** {update_without_mention[:200]}{'...' if len(update_without_mention) > 200 else ''}\n\n"
        comment += "⚡ **Statut:** En cours de traitement...\n"
        comment += "🕐 **Statut mis à jour:** Working on it\n\n"
        comment += "Je vais traiter cette nouvelle demande et vous tenir informé des résultats.\n"
        
        return cls.format_agent_comment(comment)
    
    @classmethod
    def is_agent_comment(cls, comment_text: str) -> bool:
        """
        Vérifie si un commentaire a été généré par l'agent.
        
        Args:
            comment_text: Texte du commentaire à vérifier
            
        Returns:
            True si le commentaire provient de l'agent
        """
        # Vérifier la signature cachée
        if "AI_AGENT_SIGNATURE_" in comment_text:
            return True
        
        # Vérifier la signature visible
        if "🤖 **AI-AGENT** 🤖" in comment_text:
            return True
        
        # Vérifier les patterns d'emojis typiques
        agent_patterns = [
            "🎯 **Workflow terminé",
            "🤝 **Validation humaine requise",
            "🔄 **Nouvelle demande détectée",
            "❌ **Workflow échoué",
            "✅ **Pull Request créée"
        ]
        
        for pattern in agent_patterns:
            if pattern in comment_text:
                return True
        
        return False


# Instance globale
monday_formatter = MondayCommentFormatter()

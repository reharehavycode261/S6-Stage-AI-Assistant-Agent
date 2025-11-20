# -*- coding: utf-8 -*-
"""Utilitaires pour formater les commentaires Monday.com avec signatures d'agent."""

import uuid
from datetime import datetime


class MondayCommentFormatter:
    """Formateur de commentaires Monday.com avec signatures d'agent."""
    
    # Signature cachee pour identifier les messages de l'agent
    AGENT_SIGNATURE = "<!-- AI_AGENT_SIGNATURE_{uuid} -->"
    
    # Signature visible pour les utilisateurs
    AGENT_FOOTER = "\n\n---\n[AI-AGENT] - Workflow automatise"
    
    @classmethod
    def format_agent_comment(cls, comment, include_visible_signature=True):
        """Formate un commentaire avec les signatures d'agent."""
        # Generer un UUID unique pour ce commentaire
        comment_uuid = str(uuid.uuid4())[:8]
        
        # Ajouter la signature cachee (HTML comment)
        hidden_signature = cls.AGENT_SIGNATURE.format(uuid=comment_uuid)
        formatted_comment = hidden_signature + "\n" + comment
        
        # Ajouter la signature visible si demandee
        if include_visible_signature:
            formatted_comment += cls.AGENT_FOOTER
        
        return formatted_comment
    
    @classmethod
    def format_workflow_completion(cls, success, pr_url=None, test_results=None, errors=None):
        """Formate un commentaire de fin de workflow."""
        if success:
            comment = "Workflow termine avec succes !\n\n"
            
            if pr_url:
                comment += "Pull Request creee: " + pr_url + "\n"
            
            if test_results:
                comment += "Tests: " + test_results + "\n"
            
            comment += "\nProchaines etapes:\n"
            comment += "1. Reviewer le code dans la Pull Request\n"
            comment += "2. Valider les modifications\n"
            comment += "3. Merger si tout est OK\n"
            
        else:
            comment = "Workflow echoue\n\n"
            
            if errors:
                comment += "Erreurs rencontrees:\n" + errors + "\n\n"
            
            comment += "Actions suggerees:\n"
            comment += "1. Verifier les erreurs ci-dessus\n"
            comment += "2. Corriger les problemes identifies\n"
            comment += "3. Relancer le workflow si necessaire\n"
        
        return cls.format_agent_comment(comment)
    
    @classmethod
    def is_agent_comment(cls, comment_text):
        """Verifie si un commentaire a ete genere par l'agent."""
        # Verifier la signature cachee
        if "AI_AGENT_SIGNATURE_" in comment_text:
            return True
        
        # Verifier la signature visible
        if "[AI-AGENT]" in comment_text:
            return True
        
        # Verifier les patterns typiques
        agent_patterns = [
            "Workflow termine",
            "Validation humaine requise",
            "Nouvelle demande detectee",
            "Workflow echoue",
            "Pull Request creee"
        ]
        
        for pattern in agent_patterns:
            if pattern in comment_text:
                return True
        
        return False


# Instance globale
monday_formatter = MondayCommentFormatter()

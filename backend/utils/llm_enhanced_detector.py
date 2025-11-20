# -*- coding: utf-8 -*-
"""
Module de détection de langage assistée par LLM.

Ce module améliore la détection de langage en utilisant un LLM pour:
- Analyser des projets complexes ou ambigus
- Détecter des frameworks web (Webflow, Next.js, etc.)
- Identifier des stacks technologiques mixtes
- Fournir une analyse contextuelle approfondie
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, asdict

from utils.language_detector import detect_language, LanguageInfo
from utils.logger import get_logger
from ai.llm.llm_factory import get_llm

logger = get_logger(__name__)


@dataclass
class EnhancedLanguageInfo:
    """
    Informations enrichies sur un projet détecté par LLM.
    """
    # Informations de base (du détecteur générique)
    primary_language: LanguageInfo
    
    # Informations enrichies par LLM
    project_type: str                    # "web-app", "api", "cli", "library", "mobile", etc.
    framework: Optional[str]             # "Django", "React", "Spring Boot", "Webflow", etc.
    secondary_languages: List[str]       # Langages secondaires détectés
    tech_stack: List[str]                # Stack complète ["Python", "PostgreSQL", "Redis", etc.]
    architecture: str                    # "monolithic", "microservices", "serverless", etc.
    description: str                     # Description générée par LLM
    recommendations: List[str]           # Recommandations pour l'implémentation
    confidence: float                    # Confiance globale (0.0-1.0)
    llm_analysis: str                    # Analyse complète du LLM


class LLMEnhancedDetector:
    """
    Détecteur de langage enrichi par LLM.
    
    Combine la détection automatique de fichiers avec l'analyse intelligente
    d'un LLM pour gérer des cas complexes.
    """
    
    def __init__(self, use_llm: bool = True, llm_model: str = "gpt-4o-mini"):
        """
        Initialise le détecteur enrichi.
        
        Args:
            use_llm: Si True, utilise le LLM pour enrichir la détection
            llm_model: Modèle LLM à utiliser
        """
        self.use_llm = use_llm
        self.llm_model = llm_model
        self.llm = None
        
        if use_llm:
            try:
                # Utiliser le factory LLM du projet avec fallback automatique
                from ai.llm.llm_factory import get_llm_with_fallback
                
                # Déterminer le provider principal basé sur le modèle
                primary_provider = "openai" if "gpt" in llm_model.lower() else "anthropic"
                
                self.llm = get_llm_with_fallback(
                    primary_provider=primary_provider,
                    primary_model=llm_model,  # Utiliser primary_model au lieu de model
                    temperature=0.1,
                    max_tokens=2000
                )
                logger.info(f"🤖 LLM activé pour détection enrichie: {llm_model}")
            except Exception as e:
                logger.warning(f"⚠️ Impossible d'initialiser le LLM: {e}. Mode fallback sans LLM.")
                self.use_llm = False
    
    async def detect_with_llm_enhancement(
        self,
        files: List[str],
        readme_content: Optional[str] = None,
        package_json_content: Optional[str] = None,
        requirements_txt_content: Optional[str] = None,
        other_configs: Optional[Dict[str, str]] = None
    ) -> EnhancedLanguageInfo:
        """
        Détecte le langage et enrichit avec analyse LLM.
        
        Args:
            files: Liste des fichiers du projet
            readme_content: Contenu du README (optionnel)
            package_json_content: Contenu de package.json (optionnel)
            requirements_txt_content: Contenu de requirements.txt (optionnel)
            other_configs: Autres fichiers de config {nom: contenu}
            
        Returns:
            EnhancedLanguageInfo avec analyse complète
        """
        # Étape 1: Détection de base avec le système générique
        logger.info("🔍 Étape 1: Détection automatique de base...")
        basic_detection = detect_language(files)
        
        logger.info(f"📊 Détection de base: {basic_detection.name} (confiance: {basic_detection.confidence:.2f})")
        
        # Si confiance élevée et pas de LLM, retourner résultat de base enrichi
        if not self.use_llm or not self.llm:
            return self._create_basic_enhanced_info(basic_detection, files)
        
        # Étape 2: Enrichissement avec LLM
        logger.info("🤖 Étape 2: Enrichissement avec analyse LLM...")
        
        try:
            llm_analysis = await self._analyze_with_llm(
                files=files,
                basic_detection=basic_detection,
                readme_content=readme_content,
                package_json_content=package_json_content,
                requirements_txt_content=requirements_txt_content,
                other_configs=other_configs or {}
            )
            
            return llm_analysis
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse LLM: {e}", exc_info=True)
            logger.warning("⚠️ Fallback sur détection de base")
            return self._create_basic_enhanced_info(basic_detection, files)
    
    async def _analyze_with_llm(
        self,
        files: List[str],
        basic_detection: LanguageInfo,
        readme_content: Optional[str],
        package_json_content: Optional[str],
        requirements_txt_content: Optional[str],
        other_configs: Dict[str, str]
    ) -> EnhancedLanguageInfo:
        """Analyse le projet avec le LLM."""
        
        # Construire le contexte pour le LLM
        context = self._build_llm_context(
            files=files,
            basic_detection=basic_detection,
            readme_content=readme_content,
            package_json_content=package_json_content,
            requirements_txt_content=requirements_txt_content,
            other_configs=other_configs
        )
        
        # Créer le prompt pour le LLM
        prompt = self._create_analysis_prompt(context)
        
        # Appeler le LLM
        logger.debug("🤖 Appel du LLM pour analyse...")
        
        try:
            response = await self.llm.ainvoke(prompt)
            
            # Parser la réponse JSON du LLM
            analysis = self._parse_llm_response(response.content)
            
            # Créer EnhancedLanguageInfo
            enhanced_info = EnhancedLanguageInfo(
                primary_language=basic_detection,
                project_type=analysis.get("project_type", "unknown"),
                framework=analysis.get("framework"),
                secondary_languages=analysis.get("secondary_languages", []),
                tech_stack=analysis.get("tech_stack", [basic_detection.name]),
                architecture=analysis.get("architecture", "unknown"),
                description=analysis.get("description", ""),
                recommendations=analysis.get("recommendations", []),
                confidence=min(basic_detection.confidence + 0.1, 1.0),  # Boost léger
                llm_analysis=response.content
            )
            
            logger.info(f"✅ Analyse LLM complétée:")
            logger.info(f"   Type: {enhanced_info.project_type}")
            logger.info(f"   Framework: {enhanced_info.framework}")
            logger.info(f"   Stack: {', '.join(enhanced_info.tech_stack)}")
            
            return enhanced_info
            
        except Exception as e:
            logger.error(f"❌ Erreur parsing réponse LLM: {e}")
            raise
    
    def _build_llm_context(
        self,
        files: List[str],
        basic_detection: LanguageInfo,
        readme_content: Optional[str],
        package_json_content: Optional[str],
        requirements_txt_content: Optional[str],
        other_configs: Dict[str, str]
    ) -> Dict[str, Any]:
        """Construit le contexte pour le LLM."""
        
        context = {
            "files": files[:50],  # Limiter à 50 fichiers
            "total_files": len(files),
            "basic_detection": {
                "language": basic_detection.name,
                "confidence": basic_detection.confidence,
                "extensions": basic_detection.primary_extensions,
                "build_files": basic_detection.build_files,
                "structure": basic_detection.typical_structure
            }
        }
        
        if readme_content:
            context["readme"] = readme_content[:2000]  # Limiter taille
        
        if package_json_content:
            context["package_json"] = package_json_content[:1000]
        
        if requirements_txt_content:
            context["requirements_txt"] = requirements_txt_content[:1000]
        
        if other_configs:
            context["other_configs"] = {
                k: v[:500] for k, v in list(other_configs.items())[:3]
            }
        
        return context
    
    def _create_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """Crée le prompt d'analyse pour le LLM."""
        
        prompt = f"""Tu es un expert en analyse de projets de développement logiciel.

Analyse ce projet et fournis une analyse détaillée au format JSON.

## CONTEXTE DU PROJET

### Détection Automatique de Base
Langage détecté: {context['basic_detection']['language']}
Confiance: {context['basic_detection']['confidence']:.2f}
Extensions: {', '.join(context['basic_detection']['extensions'])}
Build files: {', '.join(context['basic_detection']['build_files']) if context['basic_detection']['build_files'] else 'Aucun'}
Structure: {context['basic_detection']['structure']}

### Fichiers du Projet ({context['total_files']} fichiers au total)
```
{chr(10).join(context['files'][:30])}
{'...' if context['total_files'] > 30 else ''}
```
"""

        if "readme" in context:
            prompt += f"""
### README.md
```
{context['readme'][:1000]}
{'...' if len(context['readme']) > 1000 else ''}
```
"""

        if "package_json" in context:
            prompt += f"""
### package.json
```json
{context['package_json'][:800]}
```
"""

        if "requirements_txt" in context:
            prompt += f"""
### requirements.txt
```
{context['requirements_txt'][:800]}
```
"""

        if "other_configs" in context:
            for config_name, config_content in context["other_configs"].items():
                prompt += f"""
### {config_name}
```
{config_content[:400]}
```
"""

        prompt += """

## ANALYSE REQUISE

Fournis une analyse complète au format JSON avec cette structure EXACTE:

```json
{
  "project_type": "web-app|api|cli|library|mobile|desktop|embedded|other",
  "framework": "nom du framework principal (Django, React, Spring Boot, Webflow, Next.js, Flask, etc.) ou null",
  "secondary_languages": ["liste", "langages", "secondaires"],
  "tech_stack": ["liste", "complète", "technologies", "utilisées"],
  "architecture": "monolithic|microservices|serverless|jamstack|other",
  "description": "Description concise du projet en 2-3 phrases",
  "recommendations": [
    "Recommandation 1 pour l'implémentation",
    "Recommandation 2 pour la génération de code",
    "Recommandation 3 pour les tests"
  ]
}
```

## INSTRUCTIONS IMPORTANTES

1. **Projets Web** : Si tu détectes:
   - HTML/CSS/JS + aucun framework moderne → probablement "Webflow" ou site statique
   - React/Vue/Angular → framework frontend moderne
   - Next.js/Nuxt → framework fullstack
   - Django/Flask/FastAPI → framework Python backend
   - Spring Boot → framework Java backend

2. **Projets Mixtes** : Liste TOUS les langages utilisés:
   - Frontend: JavaScript/TypeScript
   - Backend: Python/Java/Go
   - Database: SQL
   - Infrastructure: YAML/Terraform

3. **Sois précis** : 
   - Webflow → projet_type: "web-app", framework: "Webflow"
   - Next.js + TypeScript → projet_type: "web-app", framework: "Next.js", tech_stack: ["TypeScript", "React", "Next.js"]
   - Django + PostgreSQL → projet_type: "web-app", framework: "Django", tech_stack: ["Python", "Django", "PostgreSQL"]

4. **Recommandations pratiques**:
   - Conventions de code à respecter
   - Outils de test à utiliser
   - Points d'attention particuliers

RÉPONDS UNIQUEMENT AVEC LE JSON, SANS TEXTE AVANT OU APRÈS.
"""

        return prompt
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse la réponse JSON du LLM."""
        
        # Nettoyer la réponse (retirer markdown, etc.)
        response = response.strip()
        
        # Retirer les balises markdown si présentes
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        # Parser JSON
        try:
            analysis = json.loads(response)
            return analysis
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur parsing JSON: {e}")
            logger.error(f"Réponse brute: {response[:500]}")
            
            # Fallback: retourner structure minimale
            return {
                "project_type": "unknown",
                "framework": None,
                "secondary_languages": [],
                "tech_stack": [],
                "architecture": "unknown",
                "description": "Analyse LLM non disponible",
                "recommendations": []
            }
    
    def _create_basic_enhanced_info(
        self,
        basic_detection: LanguageInfo,
        files: List[str]
    ) -> EnhancedLanguageInfo:
        """Crée un EnhancedLanguageInfo basique sans LLM."""
        
        # Inférer type de projet depuis les fichiers
        project_type = self._infer_project_type(files, basic_detection)
        
        # Inférer framework depuis build files
        framework = self._infer_framework(basic_detection)
        
        return EnhancedLanguageInfo(
            primary_language=basic_detection,
            project_type=project_type,
            framework=framework,
            secondary_languages=[],
            tech_stack=[basic_detection.name],
            architecture="unknown",
            description=f"Projet {basic_detection.name} détecté automatiquement",
            recommendations=[
                f"Utiliser les conventions {basic_detection.name} standards",
                f"Respecter la structure {basic_detection.typical_structure}",
                "Ajouter des tests unitaires"
            ],
            confidence=basic_detection.confidence,
            llm_analysis="Analyse de base sans LLM"
        )
    
    def _infer_project_type(self, files: List[str], detection: LanguageInfo) -> str:
        """Infère le type de projet depuis les fichiers."""
        
        files_lower = [f.lower() for f in files]
        
        # Web app indicators
        if any("index.html" in f or "app.py" in f or "main.py" in f for f in files_lower):
            return "web-app"
        
        # API indicators
        if any("api" in f or "routes" in f or "endpoints" in f for f in files_lower):
            return "api"
        
        # CLI indicators
        if any("cli" in f or "main" in f for f in files_lower):
            return "cli"
        
        # Library indicators
        if "setup.py" in files_lower or "setup.cfg" in files_lower:
            return "library"
        
        return "unknown"
    
    def _infer_framework(self, detection: LanguageInfo) -> Optional[str]:
        """Infère le framework depuis les build files."""
        
        build_files_lower = [f.lower() for f in detection.build_files]
        
        # Python frameworks
        if "requirements.txt" in build_files_lower:
            return "Python (requirements.txt)"
        if "pyproject.toml" in build_files_lower:
            return "Python (Poetry/modern)"
        
        # Java frameworks
        if "pom.xml" in build_files_lower:
            return "Maven"
        if "build.gradle" in build_files_lower:
            return "Gradle"
        
        # JavaScript frameworks
        if "package.json" in build_files_lower:
            return "npm/yarn"
        
        # Go
        if "go.mod" in build_files_lower:
            return "Go Modules"
        
        # Rust
        if "cargo.toml" in build_files_lower:
            return "Cargo"
        
        return None


async def detect_project_with_llm(
    files: List[str],
    readme_content: Optional[str] = None,
    package_json_content: Optional[str] = None,
    requirements_txt_content: Optional[str] = None,
    other_configs: Optional[Dict[str, str]] = None,
    use_llm: bool = True
) -> EnhancedLanguageInfo:
    """
    Fonction utilitaire pour détecter un projet avec enrichissement LLM.
    
    Args:
        files: Liste des fichiers du projet
        readme_content: Contenu du README (optionnel)
        package_json_content: Contenu de package.json (optionnel)
        requirements_txt_content: Contenu de requirements.txt (optionnel)
        other_configs: Autres fichiers de config {nom: contenu}
        use_llm: Si True, utilise le LLM pour enrichir
        
    Returns:
        EnhancedLanguageInfo avec analyse complète
        
    Example:
        >>> files = ["src/app.py", "requirements.txt", "templates/index.html"]
        >>> info = await detect_project_with_llm(files, use_llm=True)
        >>> print(f"Projet: {info.project_type}, Framework: {info.framework}")
        Projet: web-app, Framework: Flask
    """
    detector = LLMEnhancedDetector(use_llm=use_llm)
    return await detector.detect_with_llm_enhancement(
        files=files,
        readme_content=readme_content,
        package_json_content=package_json_content,
        requirements_txt_content=requirements_txt_content,
        other_configs=other_configs
    )

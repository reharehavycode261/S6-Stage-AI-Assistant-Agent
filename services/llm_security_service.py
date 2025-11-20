import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from utils.logger import get_logger

logger = get_logger(__name__)


class LLMSecurityGuard:
    """Garde de sécurité pour protéger contre les attaques LLM."""
    
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|all|above)\s+instructions?",
        r"forget\s+(previous|all|everything)\s+instructions?",
        r"disregard\s+(previous|all)\s+instructions?",
        
        r"(show|tell|reveal|display|print)\s+(me\s+)?(your|the)\s+(prompt|system\s+prompt|instructions?)",
        r"what\s+(is|are)\s+your\s+(system\s+)?(prompt|instructions?|rules?)",
        r"repeat\s+(your|the)\s+(prompt|instructions?)",
        
        r"you\s+are\s+now\s+(a|an)\s+",
        r"act\s+as\s+(a|an)\s+",
        r"pretend\s+to\s+be\s+(a|an)\s+",
        r"roleplay\s+as\s+(a|an)\s+",
        r"simulate\s+(a|an)\s+",
        
        r"(DAN|developer\s+mode|god\s+mode|admin\s+mode)",
        r"enable\s+(developer|debug|admin)\s+mode",
        r"unlock\s+(all\s+)?features?",
        r"bypass\s+(safety|security|filters?|restrictions?)",
        
        r"^system:",
        r"^assistant:",
        r"^user:",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        
        r"in\s+your\s+previous\s+response",
        r"according\s+to\s+your\s+(last|previous)\s+message",
        r"you\s+(said|told|mentioned)\s+that",
        
        r"```\s*(python|javascript|bash|sql)",
        r"<script>",
        r"eval\s*\(",
        r"exec\s*\(",
        
        r"you\s+must\s+(comply|obey|follow)",
        r"it\'?s\s+(urgent|critical|emergency)",
        r"(people|lives)\s+are\s+at\s+risk",
    ]
    
    SUSPICIOUS_KEYWORDS = {
        "ignore": 3,
        "forget": 3,
        "disregard": 3,
        "override": 4,
        "bypass": 5,
        "jailbreak": 5,
        "system": 2,
        "assistant": 2,
        "prompt": 3,
        "instructions": 2,
        "reveal": 2,
        "show": 1,
        "admin": 3,
        "developer": 2,
        "mode": 1,
    }
    
    RISK_THRESHOLD_LOW = 3
    RISK_THRESHOLD_MEDIUM = 6
    RISK_THRESHOLD_HIGH = 10
    
    def __init__(self):
        self.injection_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]
        
        self.user_requests: Dict[str, List[datetime]] = defaultdict(list)
        self.suspicious_users: Dict[str, int] = defaultdict(int)
        
        self.stats = {
            "total_checks": 0,
            "blocked_inputs": 0,
            "suspicious_inputs": 0,
            "clean_inputs": 0,
        }
    
    def check_input_safety(self, text: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        self.stats["total_checks"] += 1
        
        threats_detected = []
        risk_score = 0
        
        for pattern in self.injection_patterns:
            matches = pattern.findall(text)
            if matches:
                threats_detected.append({
                    "type": "prompt_injection",
                    "pattern": pattern.pattern,
                    "matches": matches,
                    "severity": "high"
                })
                risk_score += 5
        
        text_lower = text.lower()
        for keyword, score in self.SUSPICIOUS_KEYWORDS.items():
            if keyword in text_lower:
                count = text_lower.count(keyword)
                risk_score += score * count
                if count > 1:
                    threats_detected.append({
                        "type": "suspicious_keyword",
                        "keyword": keyword,
                        "count": count,
                        "severity": "medium"
                    })
        
        if len(text) > 5000:
            threats_detected.append({
                "type": "excessive_length",
                "length": len(text),
                "severity": "medium"
            })
            risk_score += 3
        
        if self._has_excessive_repetition(text):
            threats_detected.append({
                "type": "excessive_repetition",
                "severity": "medium"
            })
            risk_score += 2
        
        special_chars = re.findall(r'[<>{}|\[\]`]', text)
        if len(special_chars) > 10:
            threats_detected.append({
                "type": "special_characters",
                "count": len(special_chars),
                "severity": "low"
            })
            risk_score += 1
        
        if user_id:
            if self._is_rate_limited(user_id):
                threats_detected.append({
                    "type": "rate_limit_exceeded",
                    "severity": "high"
                })
                risk_score += 10
        
        if risk_score >= self.RISK_THRESHOLD_HIGH:
            risk_level = "high"
            is_safe = False
            self.stats["blocked_inputs"] += 1
        elif risk_score >= self.RISK_THRESHOLD_MEDIUM:
            risk_level = "medium"
            is_safe = False
            self.stats["suspicious_inputs"] += 1
        elif risk_score >= self.RISK_THRESHOLD_LOW:
            risk_level = "low"
            is_safe = True
            self.stats["suspicious_inputs"] += 1
        else:
            risk_level = "none"
            is_safe = True
            self.stats["clean_inputs"] += 1
        
        sanitized_text = self._sanitize_text(text) if risk_score > 0 else text
        
        reasoning = self._build_reasoning(risk_score, risk_level, threats_detected)
        
        if not is_safe:
            logger.warning(
                f"🚨 Input BLOQUÉ - Risque: {risk_level} | Score: {risk_score} | "
                f"Menaces: {len(threats_detected)} | User: {user_id or 'anonymous'}"
            )
            if user_id:
                self.suspicious_users[user_id] += 1
        elif risk_score >= self.RISK_THRESHOLD_LOW:
            logger.info(
                f"⚠️ Input SUSPECT - Risque: {risk_level} | Score: {risk_score} | "
                f"Menaces: {len(threats_detected)}"
            )
        
        return {
            "is_safe": is_safe,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "threats_detected": threats_detected,
            "sanitized_text": sanitized_text,
            "original_text": text,
            "reasoning": reasoning,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
    
    def _sanitize_text(self, text: str) -> str:
        """Nettoie le texte des patterns dangereux."""
        sanitized = text
        
        sanitized = re.sub(r'^(system|assistant|user):\s*', '', sanitized, flags=re.IGNORECASE | re.MULTILINE)
        sanitized = re.sub(r'<\|im_start\|>|<\|im_end\|>', '', sanitized)
        
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'<[^>]+>', '', sanitized)
        
        sanitized = sanitized.replace('```', '')
        sanitized = sanitized.replace('eval(', '')
        sanitized = sanitized.replace('exec(', '')
        
        if len(sanitized) > 2000:
            sanitized = sanitized[:2000] + "... [tronqué]"
        
        return sanitized.strip()
    
    def _has_excessive_repetition(self, text: str) -> bool:
        """Détecte les répétitions excessives (potentiel DoS)."""
        words = text.lower().split()
        if len(words) < 10:
            return False
        
        word_counts = defaultdict(int)
        for word in words:
            word_counts[word] += 1
        
        max_repetition = max(word_counts.values())
        repetition_ratio = max_repetition / len(words)
        
        return repetition_ratio > 0.3
    
    def _is_rate_limited(self, user_id: str, max_requests: int = 100, window_minutes: int = 60) -> bool:
        """Vérifie si l'utilisateur dépasse le rate limit."""
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if req_time > window_start
        ]

        self.user_requests[user_id].append(now)
        
        request_count = len(self.user_requests[user_id])
        
        if self.suspicious_users.get(user_id, 0) >= 3:
            max_requests = max_requests // 2
        
        return request_count > max_requests
    
    def _build_reasoning(self, risk_score: int, risk_level: str, threats: List[Dict]) -> str:
        """Construit un message expliquant la décision."""
        if risk_level == "none":
            return "Input sécurisé, aucune menace détectée."
        
        threat_summary = ", ".join([
            f"{t['type']} ({t['severity']})"
            for t in threats
        ])
        
        if risk_level == "high":
            return f"🚨 INPUT BLOQUÉ - Score de risque: {risk_score}. Menaces détectées: {threat_summary}. Cet input contient des patterns d'attaque connus."
        elif risk_level == "medium":
            return f"⚠️ INPUT SUSPECT - Score de risque: {risk_score}. Menaces potentielles: {threat_summary}. Cet input nécessite une attention particulière."
        else:
            return f"ℹ️ INPUT DOUTEUX - Score de risque: {risk_score}. Éléments suspects: {threat_summary}. L'input est autorisé mais surveillé."
    
    def check_output_safety(self, output: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Vérifie qu'un output LLM ne contient pas d'informations sensibles.
        
        Args:
            output: Texte généré par le LLM
            context: Contexte de génération
            
        Returns:
            Dict avec: is_safe, issues_detected, sanitized_output
        """
        issues_detected = []
        
        if any(marker in output.lower() for marker in ["system prompt:", "instructions:", "you are a"]):
            issues_detected.append({
                "type": "prompt_leakage",
                "severity": "critical"
            })
        
        api_key_patterns = [
            r'sk-[a-zA-Z0-9]{32,}',  # OpenAI
            r'ghp_[a-zA-Z0-9]{36}',   # GitHub
            r'xoxb-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{24,}',  # Slack
        ]
        
        for pattern in api_key_patterns:
            if re.search(pattern, output):
                issues_detected.append({
                    "type": "api_key_exposure",
                    "severity": "critical"
                })
        
        sensitive_paths = ['/etc/passwd', '/root/', 'C:\\Windows\\System32']
        if any(path in output for path in sensitive_paths):
            issues_detected.append({
                "type": "system_path_exposure",
                "severity": "high"
            })
        
        if re.search(r'\b\d{3}-\d{2}-\d{4}\b', output):  # SSN US
            issues_detected.append({
                "type": "pii_exposure",
                "severity": "high"
            })
        
        sanitized_output = self._sanitize_output(output, issues_detected)
        
        is_safe = not any(issue['severity'] in ['critical', 'high'] for issue in issues_detected)
        
        if not is_safe:
            logger.error(
                f"🚨 Output LLM NON SÉCURISÉ - Issues: {len(issues_detected)} | "
                f"Types: {[i['type'] for i in issues_detected]}"
            )
        
        return {
            "is_safe": is_safe,
            "issues_detected": issues_detected,
            "sanitized_output": sanitized_output,
            "original_output": output
        }
    
    def _sanitize_output(self, output: str, issues: List[Dict]) -> str:
        """Nettoie l'output des informations sensibles."""
        sanitized = output
        
        sanitized = re.sub(r'sk-[a-zA-Z0-9]{32,}', 'sk-***REDACTED***', sanitized)
        sanitized = re.sub(r'ghp_[a-zA-Z0-9]{36}', 'ghp_***REDACTED***', sanitized)
        sanitized = re.sub(r'xoxb-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{24,}', 'xoxb-***REDACTED***', sanitized)
        
        sanitized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '***-**-****', sanitized)
        
        return sanitized
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques de sécurité."""
        total = self.stats["total_checks"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "block_rate": round(self.stats["blocked_inputs"] / total * 100, 2),
            "suspicious_rate": round(self.stats["suspicious_inputs"] / total * 100, 2),
            "clean_rate": round(self.stats["clean_inputs"] / total * 100, 2),
            "suspicious_users_count": len(self.suspicious_users),
        }
    
    def reset_statistics(self):
        """Réinitialise les statistiques."""
        self.stats = {
            "total_checks": 0,
            "blocked_inputs": 0,
            "suspicious_inputs": 0,
            "clean_inputs": 0,
        }

llm_security_guard = LLMSecurityGuard()


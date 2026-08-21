"""
HyperMem Machine-to-Machine (M2M) Protocol & Caching Negotiator
================================================================
Handles:
1. Dynamic ISSI Dictionary Handshake & Prefix Injection.
2. Cloud/Local Prompt Caching Headers (Anthropic, OpenAI, Gemini).
3. Back-Channel Feedback Parser (Model self-optimization recommendations).
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any


class M2MProtocolEngine:
    """
    Constructs machine-to-machine prompt payloads and parses feedback loops.
    """

    M2M_SYSTEM_HEADER = (
        "=== HYPERMEM M2M ACTIVE PROTOCOL ===\n"
        "[PROTOCOL: M2M_ISSI_V1 | MODE: ZERO_CONTEXT_RESET]\n"
        "We are communicating in optimized Machine-to-Machine (M2M) syntax.\n"
        "1. Dynamic ISSI Substitution Dictionary is active below.\n"
        "2. Parse bracketed tokens directly without re-expanding in internal reasoning.\n"
        "3. If you identify opportunities to further compress this dictionary or optimize token chunks, "
        "append machine feedback at the end using format: [M2M_FEEDBACK: suggested_reduction_rules].\n"
        "====================================\n"
    )

    def __init__(self, issi_dict: Optional[Dict[str, str]] = None):
        self.issi_dict = issi_dict or {}

    def generate_cached_system_prefix(self, active_codebase_context: str = "") -> Dict[str, Any]:
        """
        Creates a structured, cache-ready system block with ISSI dictionary
        and codebase snapshot designed to be cached once on cloud/local engines.
        """
        dict_payload = " ".join(f"{v}={k}" for k, v in self.issi_dict.items())
        
        full_content = (
            f"{self.M2M_SYSTEM_HEADER}\n"
            f"[ISSI_DICTIONARY]: {dict_payload}\n"
        )
        if active_codebase_context:
            full_content += f"\n[CACHED_PROJECT_CODEBASE]:\n{active_codebase_context}\n"

        return {
            "role": "system",
            "content": full_content,
            # Cache control directive for Anthropic / Gemini
            "cache_control": {"type": "ephemeral"}
        }

    def extract_m2m_feedback(self, model_response: str) -> Tuple[str, Optional[str]]:
        """
        Extracts back-channel machine-to-machine optimization feedback from model output,
        leaving user-facing content clean.
        """
        feedback_match = re.search(r'\[M2M_FEEDBACK:\s*(.*?)\]', model_response, re.DOTALL)
        if feedback_match:
            feedback_content = feedback_match.group(1).strip()
            clean_text = re.sub(r'\[M2M_FEEDBACK:\s*.*?\]', '', model_response, flags=re.DOTALL).strip()
            return clean_text, feedback_content
        return model_response, None

"""
gui/rule_engine.py — Granular Proxy & Endpoint Routing Rules Engine
====================================================================

Provides multi-level hierarchical rules for AI traffic interception,
compression, and routing:

  Level 1: Provider / Base URL (e.g. api.x.ai, api.openai.com, 127.0.0.1:11434)
  Level 2: Hosted Model (e.g. grok-2, gpt-4o, llama3.2:3b)
  Level 3: Application / Harness (e.g. Cursor IDE, LangChain, Anthropic SDK)

Each node in the hierarchy specifies:
  - `action`: "compress" | "bypass" | "block" | "inherit"
  - `compress_inbound`:  True | False | "inherit"
  - `compress_outbound`: True | False | "inherit"

Supports rule evaluation with automatic fallback inheritance down the tree.

Author: TwistedSoCal / Hyper-Spherical Systems
License: Proprietary — All Rights Reserved
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

HYPES_DIR = Path.home() / ".hypes"
RULES_FILE = HYPES_DIR / "routing_rules.json"

# Action Constants
ACTION_COMPRESS = "compress"
ACTION_BYPASS   = "bypass"
ACTION_BLOCK    = "block"
ACTION_INHERIT  = "inherit"

# Default fallback rules tree structure
DEFAULT_RULES_TREE = {
    "providers": {
        "api.x.ai (Grok)": {
            "action": "compress",
            "compress_inbound": True,
            "compress_outbound": True,
            "models": {
                "grok-2": {
                    "action": "inherit",
                    "apps": {
                        "Cursor IDE": {"action": "bypass", "reason": "User set Grok+Cursor bypass"},
                        "LangChain":  {"action": "compress"}
                    }
                },
                "grok-beta": {"action": "inherit", "apps": {}}
            }
        },
        "api.openai.com (OpenAI)": {
            "action": "compress",
            "compress_inbound": True,
            "compress_outbound": True,
            "models": {
                "gpt-4o":      {"action": "inherit", "apps": {}},
                "gpt-4o-mini": {"action": "inherit", "apps": {}},
                "o3":          {"action": "inherit", "apps": {}}
            }
        },
        "api.anthropic.com (Anthropic)": {
            "action": "compress",
            "compress_inbound": True,
            "compress_outbound": True,
            "models": {
                "claude-3-5-sonnet-20241022": {"action": "inherit", "apps": {}}
            }
        },
        "api.groq.com (Groq)": {
            "action": "compress",
            "compress_inbound": True,
            "compress_outbound": True,
            "models": {}
        },
        "api.deepseek.com (DeepSeek)": {
            "action": "compress",
            "compress_inbound": True,
            "compress_outbound": True,
            "models": {}
        },
        "127.0.0.1:11434 (Ollama Local)": {
            "action": "compress",
            "compress_inbound": True,
            "compress_outbound": True,
            "models": {}
        }
    }
}


class RoutingRuleEngine:
    """
    Manages loading, saving, and resolving hierarchical routing rules.
    """

    def __init__(self) -> None:
        self.rules = self.load_rules()

    def load_rules(self) -> dict:
        if RULES_FILE.exists():
            try:
                data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
                if "providers" in data:
                    return data
            except Exception:
                pass
        return json.loads(json.dumps(DEFAULT_RULES_TREE))

    def save_rules(self) -> bool:
        try:
            HYPES_DIR.mkdir(parents=True, exist_ok=True)
            RULES_FILE.write_text(json.dumps(self.rules, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def evaluate(self, provider_url: str, model_name: str, app_name: str, port: int = 0) -> Tuple[str, bool, bool]:
        """
        Evaluate exact routing action for a request.
        Returns: (action: "compress"|"bypass"|"block", compress_inbound: bool, compress_outbound: bool)
        """
        # Find matching provider key
        provider_key = None
        p_clean = provider_url.lower()
        for k in self.rules.get("providers", {}):
            if p_clean in k.lower() or (port > 0 and str(port) in k):
                provider_key = k
                break

        if not provider_key:
            # Default to global compression
            return ACTION_COMPRESS, True, True

        prov_node = self.rules["providers"][provider_key]
        prov_action = prov_node.get("action", ACTION_COMPRESS)
        inbound  = prov_node.get("compress_inbound", True)
        outbound = prov_node.get("compress_outbound", True)

        # Level 2: Model check
        models = prov_node.get("models", {})
        model_node = None
        m_clean = model_name.lower()
        for mk, mv in models.items():
            if m_clean in mk.lower() or mk.lower() in m_clean:
                model_node = mv
                break

        if not model_node:
            resolved_action = prov_action if prov_action != ACTION_INHERIT else ACTION_COMPRESS
            return resolved_action, inbound, outbound

        model_action = model_node.get("action", ACTION_INHERIT)
        if model_action != ACTION_INHERIT:
            prov_action = model_action

        # Level 3: App check
        apps = model_node.get("apps", {})
        app_node = None
        a_clean = app_name.lower()
        for ak, av in apps.items():
            if a_clean in ak.lower() or ak.lower() in a_clean:
                app_node = av
                break

        if app_node:
            app_action = app_node.get("action", ACTION_INHERIT)
            if app_action != ACTION_INHERIT:
                prov_action = app_action

        final_action = prov_action if prov_action != ACTION_INHERIT else ACTION_COMPRESS
        return final_action, inbound, outbound

    def set_rule(self, provider_key: str, model_name: Optional[str], app_name: Optional[str], action: str) -> None:
        """Add or update a rule in the hierarchy."""
        providers = self.rules.setdefault("providers", {})

        # Match existing provider key if possible
        matched_pkey = provider_key
        p_clean = provider_key.lower().strip()
        for pk in providers:
            if p_clean in pk.lower():
                matched_pkey = pk
                break

        if matched_pkey not in providers:
            providers[matched_pkey] = {"action": ACTION_COMPRESS, "compress_inbound": True, "compress_outbound": True, "models": {}}

        if not model_name:
            providers[matched_pkey]["action"] = action
            self.save_rules()
            return

        models = providers[matched_pkey].setdefault("models", {})
        matched_mkey = model_name
        m_clean = model_name.lower().strip()
        for mk in models:
            if m_clean in mk.lower():
                matched_mkey = mk
                break

        if matched_mkey not in models:
            models[matched_mkey] = {"action": ACTION_INHERIT, "apps": {}}

        if not app_name:
            models[matched_mkey]["action"] = action
            self.save_rules()
            return

        apps = models[matched_mkey].setdefault("apps", {})
        matched_akey = app_name
        a_clean = app_name.lower().strip()
        for ak in apps:
            if a_clean in ak.lower():
                matched_akey = ak
                break

        apps[matched_akey] = {"action": action}
        self.save_rules()


# Global Singleton Rule Engine
_rule_engine_instance: Optional[RoutingRuleEngine] = None

def get_rule_engine() -> RoutingRuleEngine:
    global _rule_engine_instance
    if _rule_engine_instance is None:
        _rule_engine_instance = RoutingRuleEngine()
    return _rule_engine_instance

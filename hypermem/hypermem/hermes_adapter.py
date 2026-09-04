"""
HyperMem Native Adapter for Hermes Agent & Autonomous Harnesses
===============================================================
Enables Hermes Agent, OpenClaw, AutoGen, and native agent loops to hook
directly into HyperMem's infinite context, steer/veer branching, and ISSI compression.
"""

import sys
import os
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from synthuron_context.synthuron.context_engine import InfiniteContextEngine
from hypermem.m2m_protocol import M2MProtocolEngine


class HyperMemHermesHook:
    """
    Native hook for Hermes Agent execution loops.
    """

    def __init__(self, session_id: str = "hermes_primary_session", vault_dir: str = "./hypermem_vault"):
        self.session_id = session_id
        self.engine = InfiniteContextEngine(max_active_chars=3000, storage_dir=vault_dir, session_id=session_id)
        self.m2m = M2MProtocolEngine()

    def pre_process_turn(self, raw_user_prompt: str) -> Dict[str, Any]:
        """
        Intercepts incoming prompt, records in Synthuron memory graph,
        and returns optimized context-budgeted prompt with M2M headers.
        """
        turn_res = self.engine.add_turn(raw_user_prompt, role="user")
        
        # Build lean active context
        active_context = self.engine.get_active_context()
        self.m2m.issi_dict = {**self.engine.issi.static_dict, **self.engine.issi.dynamic_dict}
        m2m_prefix = self.m2m.generate_cached_system_prefix()

        return {
            "node_id": turn_res["node_id"],
            "transition": turn_res["transition"],
            "flag": turn_res["flag"],
            "system_header": m2m_prefix["content"],
            "formatted_active_context": active_context,
            "optimized_prompt": turn_res["issi_compressed"]
        }

    def post_process_turn(self, assistant_response: str):
        """Logs model completion, strips back-channel M2M feedback."""
        clean_text, feedback = self.m2m.extract_m2m_feedback(assistant_response)
        self.engine.add_turn(clean_text, role="assistant")
        return clean_text

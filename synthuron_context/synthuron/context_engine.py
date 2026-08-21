"""
Infinite Context & Synthuron Steering Engine
============================================
Unifies:
1. Arterial Synthurons (Tree Trunk Highways).
2. Two-Stage Hysteresis Staging Buffer (Touch-and-Bounce vs Full Commit).
3. 5-Factor SFIRE Mathematical Flagging.
4. Human-in-the-Loop Recursive Inflection Tuning & Memory Calibration.
"""

import time
import sys
import os
from typing import Dict, List, Optional, Set, Tuple, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from issi_compression.issi_engine import ISSICompressionEngine, prune_text

from synthuron.models import (
    MemoryNode, SynthuronLink, ArterialSynthuron, HyperHub, SubHub,
    NodeClass, PackedMetadataFlag
)
from synthuron.steer_veer import SteerVeerDetector, TransitionType
from synthuron.storage import SynthuronStorage


class InfiniteContextEngine:
    """
    Manages infinite conversational memory with mind-map clustering,
    arterial synthuron trunks, hysteresis warm staging, and recursive calibration.
    """

    def __init__(
        self,
        max_active_chars: int = 2000,
        storage_dir: str = "./synthuron_memory",
        session_id: str = "main_session"
    ):
        self.max_active_chars = max_active_chars
        self.session_id = session_id
        self.storage = SynthuronStorage(storage_dir=storage_dir)
        self.detector = SteerVeerDetector()
        self.issi = ISSICompressionEngine()

        self.all_nodes: Dict[str, MemoryNode] = {}
        self.active_nodes: List[MemoryNode] = []
        self.warm_staging: Dict[str, MemoryNode] = {}  # Hysteresis touch-and-bounce standby
        self.synthurons: List[SynthuronLink] = []
        self.hyperhubs: Dict[str, HyperHub] = {}
        self.subhubs: Dict[str, SubHub] = {}

        # Pending assistance alerts for the UI badge
        self.pending_assistance_nodes: List[str] = []

        self._load_initial_state()

    def _load_initial_state(self):
        state = self.storage.load_state()
        self.all_nodes = state["nodes"]
        self.synthurons = state["links"]
        self.active_nodes = [n for n in self.all_nodes.values() if n.active]

    def add_turn(self, text: str, role: str = "user") -> Dict[str, Any]:
        # 1. Detect Transition, SFIRE Flag & Confidence
        transition, ref_node_id, confidence = self.detector.detect_transition(
            text, self.active_nodes, self.all_nodes
        )
        node_class, flag, score_confidence = self.detector.analyze_sfire_flag(text, self.active_nodes)
        keywords = list(self.detector.extract_keywords(text))

        # 2. Build Memory Node
        node = MemoryNode(
            raw_text=text,
            role=role,
            node_class=node_class,
            flag=flag,
            session_id=self.session_id,
            keywords=keywords,
            confidence=score_confidence
        )

        if node.assistance_needed:
            self.pending_assistance_nodes.append(node.node_id)

        # 3. Apply Lexical Pruning & ISSI Compression
        prune_res = prune_text(text)
        node.pruned_text = prune_res["optimized_text"]
        node.issi_tokens = self.issi.compress(node.pruned_text)

        # 4. Hysteresis Staging vs Full Promotion
        recalled_nodes = []
        staged_nodes = []

        if transition == TransitionType.RECALL and ref_node_id and ref_node_id in self.all_nodes:
            target_node = self.all_nodes[ref_node_id]
            target_node.touch_count += 1
            
            # If touched once -> Stage in warm memory (0ms standby, no token inflation)
            # If touched twice or explicit command -> Full promotion to active window
            if target_node.touch_count >= 2 or "remember" in text.lower():
                target_node.active = True
                if target_node.node_id in self.warm_staging:
                    del self.warm_staging[target_node.node_id]
                if target_node not in self.active_nodes:
                    self.active_nodes.insert(0, target_node)
                recalled_nodes.append(target_node)
            else:
                # Place in warm hysteresis staging
                self.warm_staging[target_node.node_id] = target_node
                staged_nodes.append(target_node)

        # 5. Create Synthuron Links & Arterial Trunks
        if self.active_nodes:
            last_node = self.active_nodes[-1]
            if flag.eternal_weight >= 8.0 or node_class == NodeClass.MILESTONE:
                # Create Arterial Trunk Link (Zero Decay Highway)
                link = ArterialSynthuron(source_id=last_node.node_id, target_id=node.node_id, bandwidth=5.0)
            else:
                link_type = "tangent_bridge" if transition == TransitionType.VEER else "semantic"
                link = SynthuronLink(
                    source_id=last_node.node_id,
                    target_id=node.node_id,
                    weight=1.5 * (flag.eternal_weight / 5.0),
                    link_type=link_type
                )
            self.synthurons.append(link)

        if ref_node_id and ref_node_id in self.all_nodes:
            cross_link = SynthuronLink(
                source_id=ref_node_id,
                target_id=node.node_id,
                weight=2.5,
                link_type="hysteresis_bridge"
            )
            self.synthurons.append(cross_link)

        # 6. Store Node
        self.all_nodes[node.node_id] = node
        self.active_nodes.append(node)

        # 7. Apply Context Budgeting
        evicted = self._enforce_context_budget()

        # 8. Age out stale warm-staging nodes on complete veers
        if transition == TransitionType.VEER:
            for sid in list(self.warm_staging.keys()):
                self.warm_staging[sid].touch_count = max(0, self.warm_staging[sid].touch_count - 1)
                if self.warm_staging[sid].touch_count <= 0:
                    del self.warm_staging[sid]

        # 9. Save State
        self.storage.save_state(self.all_nodes, self.synthurons, self.hyperhubs, self.subhubs)

        return {
            "node_id": node.node_id,
            "transition": transition.value,
            "confidence": confidence,
            "class": node_class.value,
            "flag": flag.to_dict(),
            "assistance_needed": node.assistance_needed,
            "active_nodes_count": len(self.active_nodes),
            "warm_staged_count": len(self.warm_staging),
            "total_nodes_count": len(self.all_nodes),
            "evicted_count": len(evicted),
            "recalled_count": len(recalled_nodes),
            "staged_count": len(staged_nodes),
            "issi_compressed": node.issi_tokens
        }

    def _enforce_context_budget(self) -> List[MemoryNode]:
        current_chars = sum(len(n.raw_text) for n in self.active_nodes)
        evicted: List[MemoryNode] = []

        while current_chars > self.max_active_chars and len(self.active_nodes) > 2:
            candidates = self.active_nodes[:-2]
            candidates_sorted = sorted(candidates, key=lambda n: (n.flag.live_priority, n.energy))
            evicted_node = candidates_sorted[0]
            
            self.active_nodes.remove(evicted_node)
            evicted_node.active = False
            # Transition evicted node into warm staging temporarily before full cold storage
            self.warm_staging[evicted_node.node_id] = evicted_node
            evicted.append(evicted_node)
            current_chars = sum(len(n.raw_text) for n in self.active_nodes)

        return evicted

    def calibrate_user_memory(self, node_id: str, corrected_tag: int):
        """
        User reviews and corrects a node's SFIRE score.
        The engine updates the node AND recursively tunes its inflection profiler!
        """
        if node_id in self.all_nodes:
            node = self.all_nodes[node_id]
            old_flag = node.flag
            new_flag = PackedMetadataFlag.unpack(corrected_tag)
            node.flag = new_flag
            node.assistance_needed = False
            if node_id in self.pending_assistance_nodes:
                self.pending_assistance_nodes.remove(node_id)
            
            # Recursive tuning of user biases
            force_delta = new_flag.force - old_flag.force
            imp_delta = new_flag.cruciality - old_flag.cruciality
            self.detector.user_force_bias += force_delta * 0.2
            self.detector.user_importance_bias += imp_delta * 0.2
            
            self.storage.save_state(self.all_nodes, self.synthurons, self.hyperhubs, self.subhubs)
            return True
        return False

    def get_active_context(self) -> str:
        lines = []
        for n in self.active_nodes:
            f = n.flag
            lines.append(f"[{n.role.upper()} | {n.node_class.value} | Tag:{f.packed_tag}]: {n.raw_text}")
        return "\n".join(lines)

    def query_cold_memory(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        query_kw = self.detector.extract_keywords(query)
        scored_nodes = []

        for nid, node in self.all_nodes.items():
            if not query_kw:
                continue
            overlap = len(query_kw.intersection(node.keywords))
            if overlap > 0:
                score = (overlap * 2.0) + (node.flag.eternal_weight * 0.4) + (node.access_count * 0.2) + node.energy
                scored_nodes.append((score, node))

        scored_nodes.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, node in scored_nodes[:max_results]:
            decompressed = self.issi.decompress(node.issi_tokens) if node.issi_tokens else node.raw_text
            results.append({
                "node_id": node.node_id,
                "score": round(score, 2),
                "class": node.node_class.value,
                "flag": node.flag.to_dict(),
                "raw_text": node.raw_text,
                "decompressed_issi": decompressed,
                "timestamp": node.timestamp,
                "session_id": node.session_id
            })
        return results

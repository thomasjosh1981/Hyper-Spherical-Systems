"""
HyperMem 5-Tier Memory Lifecycle & Progression Engine
=====================================================
Structures memory nodes into 5 distinct lifecycle tiers:
1. Tier 1: LIVE DATA (In-flight active LLM prompt context).
2. Tier 2: NEAR DATA (Warm standby in hysteresis buffer, ready to steer/veer).
3. Tier 3: VEERED DATA (Topics discussed earlier, left behind, unreferenced).
4. Tier 4: SYNTHURON-LINKED DATA (Contextually irrelevant, but associatively bound).
5. Tier 5: DEEP COLD ARCHIVE (Encapsulated in blind vault storage).
"""

from enum import Enum
from typing import Dict, List, Any, Optional
import time


class MemoryTier(str, Enum):
    TIER_1_LIVE = "TIER_1_LIVE"
    TIER_2_NEAR = "TIER_2_NEAR"
    TIER_3_VEERED = "TIER_3_VEERED"
    TIER_4_SYNTHURON_LINKED = "TIER_4_SYNTHURON_LINKED"
    TIER_5_DEEP_COLD = "TIER_5_DEEP_COLD"


class FiveTierLifecycleManager:
    """
    Classifies and migrates memory nodes through the 5-tier progression.
    """

    def __init__(self):
        self.tiers: Dict[MemoryTier, List[Dict[str, Any]]] = {
            MemoryTier.TIER_1_LIVE: [],
            MemoryTier.TIER_2_NEAR: [],
            MemoryTier.TIER_3_VEERED: [],
            MemoryTier.TIER_4_SYNTHURON_LINKED: [],
            MemoryTier.TIER_5_DEEP_COLD: []
        }

    def categorize_node(
        self,
        node_id: str,
        text: str,
        packed_tag: int,
        is_active: bool,
        is_warm_staged: bool,
        cross_links_count: int,
        turns_since_mention: int
    ) -> MemoryTier:
        """
        Calculates exact tier based on active state, SFIRE tag, and turn age.
        """
        # Unpack SFIRE flag
        s = (packed_tag // 10000) % 10
        i = (packed_tag // 100) % 10
        r = (packed_tag // 10) % 10
        e = packed_tag % 10

        if is_active:
            return MemoryTier.TIER_1_LIVE
        elif is_warm_staged or turns_since_mention <= 2:
            return MemoryTier.TIER_2_NEAR
        elif turns_since_mention <= 8:
            return MemoryTier.TIER_3_VEERED
        elif cross_links_count > 0 or i >= 7 or e >= 7:
            # High intrinsic cruciality / milestone cross-links stay in Tier 4
            return MemoryTier.TIER_4_SYNTHURON_LINKED
        else:
            return MemoryTier.TIER_5_DEEP_COLD

    def build_tree_snapshot(self, all_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates a hierarchical tree representation for the side-panel UI.
        """
        snapshot = {
            "tier_counts": {t.value: 0 for t in MemoryTier},
            "tree": {t.value: [] for t in MemoryTier}
        }

        for n in all_nodes:
            tier = self.categorize_node(
                node_id=n["node_id"],
                text=n.get("raw_text", ""),
                packed_tag=n.get("flag", {}).get("packed_tag", 55551),
                is_active=n.get("active", False),
                is_warm_staged=n.get("touch_count", 0) == 1 and not n.get("active", False),
                cross_links_count=n.get("access_count", 1),
                turns_since_mention=n.get("turns_since_mention", 3)
            )

            snapshot["tier_counts"][tier.value] += 1
            snapshot["tree"][tier.value].append({
                "node_id": n["node_id"],
                "class": n.get("node_class", "TOPIC"),
                "tag": n.get("flag", {}).get("packed_tag", 55551),
                "preview": (n.get("raw_text", "")[:40] + "..."),
                "issi": n.get("issi_tokens", "")[:20]
            })

        return snapshot

"""
Synthuron Topological Memory & Neural Graph Data Models
======================================================
Implements:
1. Arterial Synthurons (High-capacity trunk highways connecting HyperHubs).
2. S-F-I-R-E Positional Mathematical Flagging.
3. User Inflection Profiler & Scoring Assistance flags.
"""

import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Set, Any


class NodeClass(str, Enum):
    IDEA = "IDEA"
    THOUGHT = "THOUGHT"
    SUBJECT = "SUBJECT"
    TOPIC = "TOPIC"
    TANGENT = "TANGENT"
    TIRADE = "TIRADE"
    GLIMPSE = "GLIMPSE"
    SIDETRACK = "SIDETRACK"
    TASK = "TASK"
    CODING = "CODING"
    MILESTONE = "MILESTONE"
    UNCLASSIFIED = "UNCLASSIFIED"


class PackedMetadataFlag:
    """Positional 5-Digit Mathematical Flag: PHI = S * 10000 + F * 1000 + I * 100 + R * 10 + E"""
    def __init__(
        self,
        seriousness: int = 5,
        force: int = 5,
        cruciality: int = 5,
        relevance: int = 5,
        epoch: int = 1
    ):
        self.seriousness = max(1, min(9, seriousness))
        self.force = max(1, min(9, force))
        self.cruciality = max(1, min(9, cruciality))
        self.relevance = max(1, min(9, relevance))
        self.epoch = max(1, min(9, epoch))

    @property
    def packed_tag(self) -> int:
        return (
            (self.seriousness * 10000) +
            (self.force * 1000) +
            (self.cruciality * 100) +
            (self.relevance * 10) +
            self.epoch
        )

    @property
    def live_priority(self) -> float:
        return (self.relevance * 0.60) + (self.force * 0.40)

    @property
    def eternal_weight(self) -> float:
        return (self.cruciality * 0.40) + (self.epoch * 0.35) + (self.seriousness * 0.25)

    @classmethod
    def unpack(cls, tag: int) -> "PackedMetadataFlag":
        s = (tag // 10000) % 10
        f = (tag // 1000) % 10
        i = (tag // 100) % 10
        r = (tag // 10) % 10
        e = tag % 10
        return cls(seriousness=s, force=f, cruciality=i, relevance=r, epoch=e)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packed_tag": self.packed_tag,
            "seriousness": self.seriousness,
            "force": self.force,
            "cruciality": self.cruciality,
            "relevance": self.relevance,
            "epoch": self.epoch,
            "live_priority": round(self.live_priority, 2),
            "eternal_weight": round(self.eternal_weight, 2)
        }


class MemoryNode:
    """Represents a single atomic conversational turn with mind-map coordinates."""
    def __init__(
        self,
        raw_text: str,
        role: str = "user",
        node_class: NodeClass = NodeClass.UNCLASSIFIED,
        flag: Optional[PackedMetadataFlag] = None,
        session_id: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        confidence: float = 1.0,
        node_id: Optional[str] = None
    ):
        self.node_id = node_id or str(uuid.uuid4())[:8]
        self.timestamp = time.time()
        self.role = role
        self.raw_text = raw_text
        self.pruned_text = ""
        self.issi_tokens = ""
        self.node_class = node_class
        self.flag = flag or PackedMetadataFlag()
        self.confidence = confidence
        self.assistance_needed: bool = (confidence < 0.70)
        self.session_id = session_id or "default_session"
        self.keywords: Set[str] = set(k.lower() for k in (keywords or []))
        self.energy: float = 1.0
        self.touch_count: int = 1  # For hysteresis staging (1=Warm, >=2=Hot)
        self.access_count: int = 1
        self.active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "role": self.role,
            "raw_text": self.raw_text,
            "pruned_text": self.pruned_text,
            "issi_tokens": self.issi_tokens,
            "node_class": self.node_class.value,
            "flag": self.flag.to_dict(),
            "confidence": round(self.confidence, 2),
            "assistance_needed": self.assistance_needed,
            "session_id": self.session_id,
            "keywords": list(self.keywords),
            "energy": self.energy,
            "touch_count": self.touch_count,
            "access_count": self.access_count,
            "active": self.active
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryNode":
        flag_data = data.get("flag", {})
        flag = PackedMetadataFlag.unpack(flag_data["packed_tag"]) if "packed_tag" in flag_data else PackedMetadataFlag()
        node = cls(
            raw_text=data["raw_text"],
            role=data.get("role", "user"),
            node_class=NodeClass(data.get("node_class", "UNCLASSIFIED")),
            flag=flag,
            session_id=data.get("session_id", "default_session"),
            keywords=data.get("keywords", []),
            confidence=data.get("confidence", 1.0),
            node_id=data.get("node_id")
        )
        node.timestamp = data.get("timestamp", time.time())
        node.pruned_text = data.get("pruned_text", "")
        node.issi_tokens = data.get("issi_tokens", "")
        node.energy = data.get("energy", 1.0)
        node.touch_count = data.get("touch_count", 1)
        node.access_count = data.get("access_count", 1)
        node.active = data.get("active", True)
        node.assistance_needed = data.get("assistance_needed", False)
        return node


class SynthuronLink:
    """Standard synaptic connection between memory nodes."""
    def __init__(self, source_id: str, target_id: str, weight: float = 1.0, link_type: str = "semantic", decay_rate: float = 0.05):
        self.source_id = source_id
        self.target_id = target_id
        self.weight = weight
        self.link_type = link_type  # 'semantic', 'arterial_trunk', 'milestone_anchor', 'tangent_bridge'
        self.decay_rate = decay_rate
        self.created_at = time.time()
        self.last_reinforced = time.time()

    def reinforce(self, boost: float = 0.5):
        self.weight = min(10.0, self.weight + boost)
        self.last_reinforced = time.time()

    def decay(self, resistance: float = 1.0):
        effective_decay = self.decay_rate / max(0.5, resistance / 3.0)
        self.weight = max(0.01, self.weight * (1.0 - effective_decay))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "weight": round(self.weight, 2),
            "link_type": self.link_type,
            "decay_rate": self.decay_rate,
            "created_at": self.created_at,
            "last_reinforced": self.last_reinforced
        }


class ArterialSynthuron(SynthuronLink):
    """
    High-capacity, zero-decay arterial trunk highway linking major HyperHubs
    to foundational root concepts.
    """
    def __init__(self, source_id: str, target_id: str, bandwidth: float = 5.0):
        super().__init__(source_id=source_id, target_id=target_id, weight=bandwidth, link_type="arterial_trunk", decay_rate=0.0)
        self.bandwidth = bandwidth


class SubHub:
    """Intermediate cluster directory organizing related nodes within a topic."""
    def __init__(self, name: str, parent_hub: Optional[str] = None):
        self.hub_id = f"sub_{uuid.uuid4().hex[:6]}"
        self.name = name
        self.parent_hub = parent_hub
        self.node_ids: List[str] = []
        self.created_at = time.time()

    def add_node(self, node_id: str):
        if node_id not in self.node_ids:
            self.node_ids.append(node_id)


class HyperHub:
    """Top-level thematic anchor (The Tree Trunk) coordinating multiple SubHubs and Arterial Synthurons."""
    def __init__(self, name: str, category: str = "general"):
        self.hub_id = f"hyper_{uuid.uuid4().hex[:6]}"
        self.name = name
        self.category = category
        self.sub_hub_ids: List[str] = []
        self.direct_node_ids: List[str] = []
        self.arterial_links: List[str] = []
        self.created_at = time.time()

    def add_subhub(self, sub_hub_id: str):
        if sub_hub_id not in self.sub_hub_ids:
            self.sub_hub_ids.append(sub_hub_id)

"""
Synthuron Multi-Tier Persistence & Archive Engine
=================================================
Manages hot/warm/cold memory tiers with ISSI compression and JSON/binary storage.
"""

import os
import json
import gzip
import time
from typing import Dict, List, Any, Optional
from synthuron.models import MemoryNode, SynthuronLink, HyperHub, SubHub


class SynthuronStorage:
    """Handles multi-tier long term memory storage, compression, and fast lookup."""

    def __init__(self, storage_dir: str = "./synthuron_memory"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.nodes_file = os.path.join(self.storage_dir, "memory_nodes.json")
        self.links_file = os.path.join(self.storage_dir, "synthurons.json")
        self.archive_file = os.path.join(self.storage_dir, "cold_archive.gz")

    def save_state(
        self,
        nodes: Dict[str, MemoryNode],
        links: List[SynthuronLink],
        hyperhubs: Dict[str, HyperHub],
        subhubs: Dict[str, SubHub]
    ):
        # 1. Hot & Warm Nodes
        node_payload = {nid: n.to_dict() for nid, n in nodes.items()}
        with open(self.nodes_file, "w", encoding="utf-8") as f:
            json.dump(node_payload, f, indent=2, ensure_ascii=False)

        # 2. Synthuron Links
        link_payload = [l.to_dict() for l in links]
        with open(self.links_file, "w", encoding="utf-8") as f:
            json.dump(link_payload, f, indent=2)

        # 3. Compressed Cold Archive
        cold_data = {
            "saved_at": time.time(),
            "nodes_count": len(nodes),
            "links_count": len(links),
            "nodes": node_payload,
            "links": link_payload
        }
        compressed_bytes = gzip.compress(json.dumps(cold_data).encode("utf-8"))
        with open(self.archive_file, "wb") as f:
            f.write(compressed_bytes)

    def load_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.nodes_file):
            return {"nodes": {}, "links": []}

        try:
            with open(self.nodes_file, "r", encoding="utf-8") as f:
                nodes_raw = json.load(f)
            nodes = {nid: MemoryNode.from_dict(data) for nid, data in nodes_raw.items()}
        except Exception:
            nodes = {}

        links = []
        if os.path.exists(self.links_file):
            try:
                with open(self.links_file, "r", encoding="utf-8") as f:
                    links_raw = json.load(f)
                for l in links_raw:
                    link = SynthuronLink(
                        source_id=l["source_id"],
                        target_id=l["target_id"],
                        weight=l.get("weight", 1.0),
                        link_type=l.get("link_type", "semantic"),
                        decay_rate=l.get("decay_rate", 0.05)
                    )
                    links.append(link)
            except Exception:
                links = []

        return {"nodes": nodes, "links": links}

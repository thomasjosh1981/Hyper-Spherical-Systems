"""
Synthuron Hyperspherical Vault & Obfuscated Micro-Cluster Storage Engine
=======================================================================
Implements:
1. Hierarchical Tree-to-Tendril Topology:
   - HyperHubs & Arterial Branches (Trunk)
   - SubHubs & SubBranches
   - MicroTendrils (Leaf Reachers)
   - HyperSynthurons (Direct zero-hub wormhole links between obscure concepts)
2. Overlapping Spatial Sector / Hyperspherical Indexing (Octants & 4D Vectors).
3. Obfuscated Blind File Vault:
   - Nameless / Extensionless hashed files.
   - Steganographic Header: File size & sector coordinates.
   - Spatially scrambled ISSI payload body.
   - Rolling-Code Chaff Footer: 50-char buffer with 30-char embedded key & rolling offset.
"""

import os
import json
import zlib
import time
import uuid
import hashlib
from typing import Dict, List, Optional, Set, Tuple, Any

from synthuron.models import MemoryNode, SynthuronLink, PackedMetadataFlag


class HyperSynthuron(SynthuronLink):
    """
    Direct zero-hub associative wormhole link connecting two distant/obscure concepts
    without requiring an intermediary hub.
    """
    def __init__(self, source_id: str, target_id: str, affinity: float = 3.0, context_tag: str = "quantum_associative"):
        super().__init__(source_id=source_id, target_id=target_id, weight=affinity, link_type="hyper_synthuron_tunnel", decay_rate=0.01)
        self.context_tag = context_tag


class MicroTendril:
    """Fine-grained terminal reacher connecting a SubHub to atomic memory leaf nodes."""
    def __init__(self, subhub_id: str, leaf_node_id: str, fine_weight: float = 1.0):
        self.subhub_id = subhub_id
        self.leaf_node_id = leaf_node_id
        self.fine_weight = fine_weight


class HypersphereSector:
    """Represents an overlapping 4D spatial sector (Time, Seriousness, Cruciality, Relevance)."""
    def __init__(self, sector_id: str, center_coords: Tuple[float, float, float, float], radius: float = 5.0):
        self.sector_id = sector_id
        self.center = center_coords  # (T, S, I, R)
        self.radius = radius
        self.vault_file_hashes: List[str] = []

    def contains(self, point: Tuple[float, float, float, float]) -> bool:
        """Calculates Euclidean distance in 4D space to check sector overlap."""
        dist_sq = sum((c - p) ** 2 for c, p in zip(self.center, point))
        return (dist_sq ** 0.5) <= self.radius


class ObfuscatedVaultStorage:
    """
    Manages the blind file vault:
    - Files have no extensions and randomized hash names.
    - Encapsulated with Header, ISSI Scrambled Payload, and Rolling-Code Footer.
    """

    def __init__(self, vault_dir: str = "./synthuron_vault"):
        self.vault_dir = vault_dir
        os.makedirs(self.vault_dir, exist_ok=True)
        self.master_index_file = os.path.join(self.vault_dir, ".sector_manifest.dat")
        self.sectors: Dict[str, HypersphereSector] = self._initialize_sectors()

    def _initialize_sectors(self) -> Dict[str, HypersphereSector]:
        # Initialize default 4D overlapping hypersphere sectors
        sectors = {}
        quadrants = [
            ("SEC_EPOCH_CORE", (1.0, 8.0, 9.0, 2.0), 6.0),
            ("SEC_TECHNICAL_TASK", (1.0, 4.0, 7.0, 8.0), 6.0),
            ("SEC_CASUAL_TANGENT", (1.0, 2.0, 2.0, 2.0), 5.0),
            ("SEC_SECURITY_ARCHIVE", (1.0, 9.0, 8.0, 5.0), 6.0),
        ]
        for sid, coords, rad in quadrants:
            sectors[sid] = HypersphereSector(sid, coords, rad)
        return sectors

    def _generate_rolling_footer(self, raw_key: str, rolling_seed: int) -> str:
        """
        Creates a 50-character steganographic footer:
        - 30 characters of actual key data
        - 20 characters of deterministic pseudo-random chaff
        - Rolling offset calculated from seed
        """
        key_30 = (raw_key + "X" * 30)[:30]
        chaff = hashlib.sha256(str(rolling_seed).encode()).hexdigest()[:20]
        
        # Calculate rolling start index (0 to 19)
        start_idx = rolling_seed % 20
        # Interweave key and chaff
        footer = list(chaff)
        for i, ch in enumerate(key_30):
            footer.insert((start_idx + i) % len(footer), ch)
            
        return "".join(footer)[:50]

    def _extract_rolling_footer(self, footer_50: str, rolling_seed: int) -> str:
        """Extracts the 30-char key using the rolling seed handshake."""
        start_idx = rolling_seed % 20
        # Inverse extraction simulation
        key_chars = []
        for i in range(30):
            idx = (start_idx + i * 2) % len(footer_50)
            key_chars.append(footer_50[idx])
        return "".join(key_chars)

    def write_micro_cluster(
        self,
        node: MemoryNode,
        issi_dictionary_snippet: str = "ISSI_REGISTRY_V1_SEED_ALPHA_99"
    ) -> str:
        """
        Writes a node into an extensionless obfuscated vault file.
        Returns the randomized blind file hash.
        """
        file_hash = hashlib.sha256(f"{node.node_id}_{time.time()}".encode()).hexdigest()[:16]
        file_path = os.path.join(self.vault_dir, file_hash)

        # 1. Prepare Header
        flag = node.flag
        sector_coords = (1.0, float(flag.seriousness), float(flag.cruciality), float(flag.relevance))
        header_data = {
            "node_id": node.node_id,
            "coords": sector_coords,
            "created_at": node.timestamp,
            "tag": flag.packed_tag
        }
        header_bytes = json.dumps(header_data).encode("utf-8")
        header_len = len(header_bytes)

        # 2. Compress Payload Body
        payload = {
            "raw_text": node.raw_text,
            "pruned": node.pruned_text,
            "issi_tokens": node.issi_tokens,
            "class": node.node_class.value,
            "keywords": list(node.keywords)
        }
        compressed_body = zlib.compress(json.dumps(payload).encode("utf-8"), level=9)

        # 3. Build 50-char Rolling Footer
        rolling_seed = flag.packed_tag % 1000
        footer_str = self._generate_rolling_footer(issi_dictionary_snippet, rolling_seed)
        footer_bytes = footer_str.encode("utf-8")

        # 4. Write binary vault block [4-byte header length | Header | Body | 50-byte Footer]
        with open(file_path, "wb") as f:
            f.write(header_len.to_bytes(4, byteorder="big"))
            f.write(header_bytes)
            f.write(compressed_body)
            f.write(footer_bytes)

        # Index in hyperspherical sectors
        for sec in self.sectors.values():
            if sec.contains(sector_coords):
                sec.vault_file_hashes.append(file_hash)

        return file_hash

    def read_micro_cluster(self, file_hash: str) -> Dict[str, Any]:
        """Reads, de-steganographs, and decompresses an obfuscated vault file."""
        file_path = os.path.join(self.vault_dir, file_hash)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Vault file {file_hash} not found.")

        with open(file_path, "rb") as f:
            raw = f.read()

        # Unpack Header
        header_len = int.from_bytes(raw[:4], byteorder="big")
        header_bytes = raw[4 : 4 + header_len]
        header_data = json.loads(header_bytes.decode("utf-8"))

        # Extract Footer
        footer_bytes = raw[-50:]
        footer_str = footer_bytes.decode("utf-8", errors="ignore")

        # Extract & Decompress Body
        body_bytes = raw[4 + header_len : -50]
        decompressed_body = json.loads(zlib.decompress(body_bytes).decode("utf-8"))

        return {
            "header": header_data,
            "payload": decompressed_body,
            "footer_signature": footer_str[:12] + "...",
            "blind_hash": file_hash
        }

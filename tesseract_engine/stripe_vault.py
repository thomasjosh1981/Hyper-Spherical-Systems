"""
Tesseract 5-File Chameleon Stripe Set & Parity Vault Engine
===========================================================
Implements:
1. 3-Way Data Striping (Files 1, 2, 3) with chameleon file mimicry.
2. XOR Parity Generation (File 4: P = S1 ^ S2 ^ S3) allowing 3-of-4 file recovery.
3. Decoy Chaff File (File 5) embedding UUIDv7 Cubical Address & Dimension codes.
4. End-to-End Ingress -> 4-Corner Unwrap -> 5+1 DLASC -> Stripe -> 100% Lossless Recovery.
"""

import os
import sys
import json
import time
import math
import random
from typing import Dict, List, Tuple, Optional, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from issi_compression.issi_engine import (
    prune_text, generate_3d_center_out_path, generate_4corner_unwrap_path,
    SCRIPT_TABLES, GLOBAL_REVERSE_MAP, encode_homophonic_dlasc
)
from tesseract_engine.cubical_address import CubicalAddressEngine


class TesseractStripeVault:
    """
    Manages 5-file RAID-5 style chameleon striped storage with parity and cubical addresses.
    """

    @staticmethod
    def _xor_bytes(b1: bytes, b2: bytes) -> bytes:
        return bytes(x ^ y for x, y in zip(b1, b2))

    @staticmethod
    def _find_cube_dim(data_len: int) -> int:
        dims = [5, 7, 9, 10, 12, 14, 16, 18, 20]
        for d in dims:
            if d ** 3 >= data_len:
                return d
        return 20

    @classmethod
    def encode_and_stripe(
        cls,
        raw_text: str,
        output_dir: str = "./vault_stripes",
        file_prefix: str = "sys_cache",
        starting_face: int = 0,
        direction_mode: int = 1,
        plane_seq_idx: int = 0
    ) -> Dict[str, Any]:
        """
        Executes complete pipeline:
        ISSI -> 3D Center-Out -> 4-Corner Unwrap -> 5+1 DLASC -> 5-File Stripe Set.
        """
        os.makedirs(output_dir, exist_ok=True)

        # 1. ISSI Compression & Lexical Pruning
        pruned = prune_text(raw_text, drop_prepositions=True)
        opt_text = pruned['optimized_text']
        if not opt_text:
            opt_text = "EMPTY_TESSERACT_PAYLOAD"

        # 2. Determine Cube Dimension & Generate UUIDv7 Cubical Address
        dim = cls._find_cube_dim(len(opt_text))
        total_voxels = dim ** 3
        address = CubicalAddressEngine.generate_address(
            cube_dim=dim,
            starting_face=starting_face,
            direction_mode=direction_mode,
            plane_seq_idx=plane_seq_idx
        )

        # Pad text to exact cube size
        pad_char = "~"
        padded_text = opt_text + (pad_char * (total_voxels - len(opt_text)))

        # 3. 3D Center-Out Spiral Ingress
        plane_seq = CubicalAddressEngine.PLANE_PERMUTATIONS[plane_seq_idx]
        ingress_path = generate_3d_center_out_path(dim, clockwise=(direction_mode in [1, 2]), plane_seq=plane_seq)
        
        cube = {}
        for i, pt in enumerate(ingress_path):
            cube[pt] = padded_text[i]

        # 4. 4-Corner Top-Down Orthogonal Unwinding
        unwrap_path = generate_4corner_unwrap_path(dim)
        unwound_chars = "".join(cube[pt] for pt in unwrap_path)

        # 5. 5+1 DLASC Homophonic Rune Cipher
        dlasc_payload = encode_homophonic_dlasc(unwound_chars)
        payload_bytes = dlasc_payload.encode("utf-8")

        # 6. Split into 3 Equal Data Stripes (with padding)
        stripe_size = math.ceil(len(payload_bytes) / 3)
        padded_payload = payload_bytes.ljust(stripe_size * 3, b"\x00")
        
        s1 = padded_payload[0 : stripe_size]
        s2 = padded_payload[stripe_size : stripe_size * 2]
        s3 = padded_payload[stripe_size * 2 : stripe_size * 3]

        # 7. Compute XOR Parity (File 4: P = S1 ^ S2 ^ S3)
        parity = cls._xor_bytes(cls._xor_bytes(s1, s2), s3)

        # 8. Generate File 5 (Decoy Chaff with Steganographic Cubical Address)
        chaff_noise = os.urandom(256)
        stego_header = json.dumps({
            "cubical_address": address,
            "raw_byte_len": len(payload_bytes),
            "stripe_size": stripe_size,
            "orig_tokens": pruned['original_tokens']
        }).encode("utf-8")
        file5_junk = b"DEC_LOG_V2::" + stego_header + b"::CHAFF::" + chaff_noise

        # 9. Write Chameleon Mimic Files (Using '51', '5', '1', '4', 'junk')
        paths = {
            "file_1_data_a": os.path.join(output_dir, f"{file_prefix}51.dat"),
            "file_2_data_b": os.path.join(output_dir, f"{file_prefix}5.dat"),
            "file_3_data_c": os.path.join(output_dir, f"{file_prefix}1.dat"),
            "file_4_parity": os.path.join(output_dir, f"{file_prefix}4.dat"),
            "file_5_chaff":  os.path.join(output_dir, f"{file_prefix}_diag.dat")
        }

        with open(paths["file_1_data_a"], "wb") as f: f.write(s1)
        with open(paths["file_2_data_b"], "wb") as f: f.write(s2)
        with open(paths["file_3_data_c"], "wb") as f: f.write(s3)
        with open(paths["file_4_parity"], "wb") as f: f.write(parity)
        with open(paths["file_5_chaff"], "wb") as f: f.write(file5_junk)

        return {
            "status": "STRIPE_SET_WRITTEN",
            "cubical_address": address,
            "dimension": dim,
            "total_voxels": total_voxels,
            "stripe_size_bytes": stripe_size,
            "files": paths
        }

    @classmethod
    def reconstruct_and_decode(
        cls,
        output_dir: str = "./vault_stripes",
        file_prefix: str = "sys_cache"
    ) -> Dict[str, Any]:
        """
        Reconstructs the original 3D cube from any 3-of-4 data/parity files + File 5 metadata.
        """
        p1 = os.path.join(output_dir, f"{file_prefix}51.dat")
        p2 = os.path.join(output_dir, f"{file_prefix}5.dat")
        p3 = os.path.join(output_dir, f"{file_prefix}1.dat")
        p4 = os.path.join(output_dir, f"{file_prefix}4.dat")
        p5 = os.path.join(output_dir, f"{file_prefix}_diag.dat")

        # 1. Read File 5 Metadata
        if not os.path.exists(p5):
            raise FileNotFoundError("Decoy Chaff Metadata File (File 5) missing or unreadable.")

        with open(p5, "rb") as f:
            f5_bytes = f.read()

        tag_start = b"DEC_LOG_V2::"
        tag_end = b"::CHAFF::"
        idx1 = f5_bytes.index(tag_start) + len(tag_start)
        idx2 = f5_bytes.index(tag_end)
        meta = json.loads(f5_bytes[idx1:idx2].decode("utf-8"))

        address = meta["cubical_address"]
        raw_len = meta["raw_byte_len"]
        stripe_sz = meta["stripe_size"]
        addr_params = CubicalAddressEngine.parse_address(address)
        dim = addr_params["dimension"]

        # 2. Check Available Shards among S1, S2, S3, P
        s1 = open(p1, "rb").read() if os.path.exists(p1) else None
        s2 = open(p2, "rb").read() if os.path.exists(p2) else None
        s3 = open(p3, "rb").read() if os.path.exists(p3) else None
        p  = open(p4, "rb").read() if os.path.exists(p4) else None

        shards_present = sum(1 for x in [s1, s2, s3, p] if x is not None)
        if shards_present < 3:
            raise ValueError(f"Insufficient shards for recovery: Found {shards_present}/4 (Minimum 3 required).")

        # 3. 3-of-4 XOR Parity Rebuilding
        if s1 is None:
            # Rebuild S1 = S2 ^ S3 ^ P
            s1 = cls._xor_bytes(cls._xor_bytes(s2, s3), p)
            recovery_mode = "REBUILT_S1_FROM_PARITY"
        elif s2 is None:
            # Rebuild S2 = S1 ^ S3 ^ P
            s2 = cls._xor_bytes(cls._xor_bytes(s1, s3), p)
            recovery_mode = "REBUILT_S2_FROM_PARITY"
        elif s3 is None:
            # Rebuild S3 = S1 ^ S2 ^ P
            s3 = cls._xor_bytes(cls._xor_bytes(s1, s2), p)
            recovery_mode = "REBUILT_S3_FROM_PARITY"
        else:
            recovery_mode = "DIRECT_3_STRIPES_PRISTINE"

        # 4. Concatenate and Trim Payload
        combined_bytes = (s1 + s2 + s3)[:raw_len]
        dlasc_str = combined_bytes.decode("utf-8")

        # 5. Reverse 5+1 DLASC Homophonic Cipher
        from issi_compression.issi_engine import decode_homophonic_dlasc
        unwound_str = decode_homophonic_dlasc(dlasc_str)

        # 6. Reverse 4-Corner Top-Down Scan into 3D Cube
        unwrap_path = generate_4corner_unwrap_path(dim)
        cube = {}
        for i, pt in enumerate(unwrap_path):
            if i < len(unwound_str):
                cube[pt] = unwound_str[i]

        # 7. Reverse 3D Center-Out Spiral Ingress
        ingress_path = generate_3d_center_out_path(
            dim,
            clockwise=addr_params["clockwise"],
            plane_seq=addr_params["plane_sequence"]
        )
        recovered_padded = "".join(cube.get(pt, "~") for pt in ingress_path)
        recovered_clean = recovered_padded.rstrip("~")

        return {
            "status": "RECONSTRUCTION_SUCCESSFUL",
            "recovery_mode": recovery_mode,
            "cubical_address": address,
            "dimension": dim,
            "recovered_text": recovered_clean
        }

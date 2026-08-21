"""
Tesseract UUIDv7 Cubical Address Engine
=======================================
Generates non-repeating, time-ordered UUIDv7 address codes where standard
hyphens are replaced by single-digit algebraic cubical configuration parameters:
- Separator 1 (Position 8):  Cube Dimension D in [5, 7, 9, 10, 12, 14, 16, 18, 20]
                             (Odd: 5->5, 7->7, 9->9; Even: 10->1, 12->2, 14->4, 16->6, 18->8, 20->0)
- Separator 2 (Position 13): Starting Face Index (0..7: 8 Hyper-Faces / Bounding Reference Faces)
- Separator 3 (Position 18): Winding Direction & Parity Orientation (0..3)
- Separator 4 (Position 23): Plane Permutation Sequence (0..5)

Encoded via non-obvious modular geometric transform polynomials.
"""

import time
import os
import random
from typing import Dict, Tuple, Any, Optional


class CubicalAddressEngine:
    """
    Encodes and decodes 3D Tesseract configuration metadata directly inside UUIDv7 strings.
    """

    # Unambiguous single-digit mapping:
    # Odds:  5->'5', 7->'7', 9->'9'
    # Evens: 10->'1', 12->'2', 14->'4', 16->'6', 18->'8', 20->'0'
    DIM_TO_CODE = {
        5: '5', 7: '7', 9: '9',
        10: '1', 12: '2', 14: '4', 16: '6', 18: '8', 20: '0'
    }
    CODE_TO_DIM = {
        '5': 5, '7': 7, '9': 9,
        '1': 10, '2': 12, '4': 14, '6': 16, '8': 18, '0': 20
    }

    PLANE_PERMUTATIONS = [
        ['X', 'Y', 'Z'], ['X', 'Z', 'Y'],
        ['Y', 'X', 'Z'], ['Y', 'Z', 'X'],
        ['Z', 'X', 'Y'], ['Z', 'Y', 'X']
    ]

    @staticmethod
    def _generate_raw_uuidv7() -> Tuple[str, str, str, str, str]:
        """Generates standard UUIDv7 5 hex components based on millisecond timestamp."""
        ms = int(time.time() * 1000)
        # 48-bit timestamp hex (12 hex chars)
        time_hex = f"{ms:012x}"
        p1 = time_hex[:8]
        p2 = time_hex[8:12]
        
        # 12-bit random + version 7
        ver_and_rand = f"7{random.randint(0, 0xfff):03x}"
        
        # 2-bit variant (10) + 14-bit random (variant 2)
        var_and_rand = f"{random.choice(['8', '9', 'a', 'b'])}{random.randint(0, 0xfff):03x}"
        
        # 48-bit random node
        p5 = f"{random.randint(0, 0xffffffffffff):012x}"
        
        return p1, p2, ver_and_rand, var_and_rand, p5

    @classmethod
    def generate_address(
        cls,
        cube_dim: int = 5,
        starting_face: int = 0,
        direction_mode: int = 1,
        plane_seq_idx: int = 0
    ) -> str:
        """
        Creates a single unbroken 36-character UUIDv7 string where hyphens
        are replaced by single-digit cubical transform codes.
        """
        p1, p2, p3, p4, p5 = cls._generate_raw_uuidv7()

        # Separator 1: Dimension Code
        sep1 = cls.DIM_TO_CODE.get(cube_dim, '5')
        
        # Separator 2: Starting Face Index (0..7)
        sep2 = str(starting_face % 8)
        
        # Separator 3: Direction & Parity Flag (0..3: 1=CW, 0=CCW, 2=Rev-CW, 3=Rev-CCW)
        sep3 = str(direction_mode % 4)
        
        # Separator 4: Plane Sequence Permutation Index (0..5)
        sep4 = str(plane_seq_idx % 6)

        # Formulate non-hyphenated 36-char cubical address
        address = f"{p1}{sep1}{p2}{sep2}{p3}{sep3}{p4}{sep4}{p5}"
        return address

    @classmethod
    def parse_address(cls, address: str) -> Dict[str, Any]:
        """
        Extracts mathematical parameters from the UUIDv7 Cubical Address code.
        Format: [8 chars] + [Sep1] + [4 chars] + [Sep2] + [4 chars] + [Sep3] + [4 chars] + [Sep4] + [12 chars]
        """
        clean = address.replace("-", "").strip()
        if len(clean) != 36:
            raise ValueError(f"Invalid cubical address length: {len(clean)} (expected 36 characters)")

        sep1 = clean[8]
        sep2 = clean[13]
        sep3 = clean[18]
        sep4 = clean[23]

        dim = cls.CODE_TO_DIM.get(sep1, 5)
        face_idx = int(sep2) if sep2.isdigit() else 0
        direction = int(sep3) if sep3.isdigit() else 1
        plane_idx = int(sep4) if (sep4.isdigit() and int(sep4) < 6) else 0

        clockwise = (direction in [1, 2])
        reverse_fill = (direction in [2, 3])
        plane_seq = cls.PLANE_PERMUTATIONS[plane_idx]

        return {
            "address": address,
            "dimension": dim,
            "total_voxels": dim ** 3,
            "starting_face": face_idx,
            "direction_mode": direction,
            "clockwise": clockwise,
            "reverse_fill": reverse_fill,
            "plane_sequence": plane_seq
        }

"""
gui/cubical_address.py
======================
Hyper-Spherical Systems — UUIDv7.4 Cubical Address & Sparse Quadrant Engine

Specifications:
- UUIDv7.4: 32-Hex unhyphenated UUIDv7 + 4-Dimensional Geometric Header (38 chars total).
- 4D Geometric Header:
    1. Dimension Code D in [5, 7, 9, 10, 12, 14, 16, 18, 19, 20]
    2. Quadrant Omission Bitmask (8 octants Q0..Q7: 1 = active, 0 = omitted/skipped)
    3. Junk / Filler Voxel Count (tracks padding to seal active cube volume)
    4. Chirality & Plane Permutation sequence (0..23)
- Sparse Quadrant 3D Winding:
    For cubes > 7x7x7 (D in [9, 10, 12, 14, 16, 18, 19, 20]), omits 1 to 2 empty octants
    when payload is compact, sliding the 3D center-out trajectory across active voxels only.
- Glyphication Ready: Direct integration with 5+1 homophonic scrambling at string ingress.
"""

import time
import random
from typing import Dict, Tuple, Any, List, Optional, Set


class UUIDv7_4_Engine:
    """
    UUIDv7.4: Unbroken 38-character Hyphenless Address Block with 4D Cubical Metadata.
    """

    DIMENSIONS = [5, 7, 9, 10, 12, 14, 16, 18, 19, 20]
    
    DIM_TO_CODE = {
        5: '5', 7: '7', 9: '9',
        10: 'A', 12: 'B', 14: 'C', 16: 'D', 18: 'E', 19: 'F', 20: 'G'
    }
    CODE_TO_DIM = {v: k for k, v in DIM_TO_CODE.items()}

    PLANE_PERMUTATIONS = [
        ['X', 'Y', 'Z'], ['X', 'Z', 'Y'],
        ['Y', 'X', 'Z'], ['Y', 'Z', 'X'],
        ['Z', 'X', 'Y'], ['Z', 'Y', 'X']
    ]

    @classmethod
    def generate_raw_uuidv7_unbroken(cls) -> str:
        """Generates a 32-character unhyphenated standard UUIDv7 string."""
        ms = int(time.time() * 1000)
        time_hex = f"{ms:012x}"
        p1 = time_hex[:8]
        p2 = time_hex[8:12]
        p3 = f"7{random.randint(0, 0xfff):03x}"
        p4 = f"{random.choice(['8', '9', 'a', 'b'])}{random.randint(0, 0xfff):03x}"
        p5 = f"{random.randint(0, 0xffffffffffff):012x}"
        return f"{p1}{p2}{p3}{p4}{p5}".upper()

    @classmethod
    def calculate_optimal_geometry(cls, payload_len: int) -> Dict[str, Any]:
        """
        Determines the optimal cube dimension, quadrant omission mask, and junk filler count.
        For cubes > 7x7x7, skips 1 or 2 octants if payload fits to minimize filler data.
        """
        for dim in cls.DIMENSIONS:
            total_voxels = dim ** 3
            octant_voxels = total_voxels // 8

            if dim <= 7:
                # 5x5x5 and 7x7x7 always use full cube (8 active octants, mask 0xFF)
                if total_voxels >= payload_len:
                    junk_filler = total_voxels - payload_len
                    return {
                        "dim": dim,
                        "quadrant_mask": 0xFF, # All 8 octants active
                        "active_voxels": total_voxels,
                        "junk_filler": junk_filler,
                        "omitted_quadrants": 0
                    }
            else:
                # D > 7: Test with 2 omitted octants (6 active), 1 omitted (7 active), or full (8 active)
                for active_octants, mask in [(6, 0xFC), (7, 0xFE), (8, 0xFF)]:
                    active_capacity = active_octants * octant_voxels
                    if active_capacity >= payload_len:
                        junk_filler = active_capacity - payload_len
                        return {
                            "dim": dim,
                            "quadrant_mask": mask,
                            "active_voxels": active_capacity,
                            "junk_filler": junk_filler,
                            "omitted_quadrants": 8 - active_octants
                        }

        # Fallback to max dimension
        max_dim = 20
        total_voxels = max_dim ** 3
        return {
            "dim": max_dim,
            "quadrant_mask": 0xFF,
            "active_voxels": total_voxels,
            "junk_filler": max(0, total_voxels - payload_len),
            "omitted_quadrants": 0
        }

    @classmethod
    def generate_address_v7_4(
        cls,
        payload_len: int,
        direction_mode: int = 1,
        plane_seq_idx: int = 0
    ) -> Dict[str, Any]:
        """
        Generates the complete 38-character UUIDv7.4 address block.
        Format: [32-Hex UUIDv7] + [1-Char DimCode] + [2-Hex OctantMask] + [2-Hex JunkVoxelRatio] + [1-Hex Chirality/Plane]
        """
        raw_uuid = cls.generate_raw_uuidv7_unbroken()
        geom = cls.calculate_optimal_geometry(payload_len)

        dim_code = cls.DIM_TO_CODE.get(geom["dim"], '5')
        mask_hex = f"{geom['quadrant_mask']:02X}"
        # Store junk filler ratio scaled 0..255 or raw filler clamped to FF
        filler_byte = min(255, geom["junk_filler"] % 256)
        filler_hex = f"{filler_byte:02X}"
        
        dir_plane_byte = ((direction_mode % 4) << 3) | (plane_seq_idx % 6)
        dir_plane_hex = f"{dir_plane_byte:01X}"

        address_block = f"{raw_uuid}{dim_code}{mask_hex}{filler_hex}{dir_plane_hex}"

        return {
            "address_v7_4": address_block,
            "raw_uuid": raw_uuid,
            "dim": geom["dim"],
            "quadrant_mask": geom["quadrant_mask"],
            "junk_filler": geom["junk_filler"],
            "active_voxels": geom["active_voxels"],
            "omitted_quadrants": geom["omitted_quadrants"],
            "direction_mode": direction_mode,
            "plane_seq": cls.PLANE_PERMUTATIONS[plane_seq_idx % 6]
        }

    @classmethod
    def parse_address_v7_4(cls, address_v7_4: str) -> Dict[str, Any]:
        """
        Parses the unbroken 38-character UUIDv7.4 address block and recovers
        the exact cube dimension, active octant mask, junk filler count, and winding parameters.
        """
        clean = address_v7_4.replace("-", "").strip().upper()
        if len(clean) != 38:
            raise ValueError(f"Invalid UUIDv7.4 length: {len(clean)} (expected 38 characters)")

        raw_uuid = clean[:32]
        dim_code = clean[32]
        mask_hex = clean[33:35]
        filler_hex = clean[35:37]
        dir_plane_hex = clean[37]

        dim = cls.CODE_TO_DIM.get(dim_code, 5)
        quadrant_mask = int(mask_hex, 16)
        filler_byte = int(filler_hex, 16)
        dir_plane_val = int(dir_plane_hex, 16)

        direction_mode = (dir_plane_val >> 3) & 0x03
        plane_idx = dir_plane_val & 0x07
        plane_seq = cls.PLANE_PERMUTATIONS[min(5, plane_idx)]

        # Calculate active voxels from octant mask
        octant_voxels = (dim ** 3) // 8
        active_octants_count = bin(quadrant_mask).count('1')
        active_voxels = (dim ** 3) if dim <= 7 else active_octants_count * octant_voxels

        return {
            "address_v7_4": clean,
            "raw_uuid": raw_uuid,
            "dim": dim,
            "total_cube_volume": dim ** 3,
            "quadrant_mask": quadrant_mask,
            "active_octants_count": active_octants_count,
            "active_voxels": active_voxels,
            "filler_byte": filler_byte,
            "direction_mode": direction_mode,
            "clockwise": (direction_mode in [1, 2]),
            "plane_sequence": plane_seq
        }


# ── Sparse Quadrant 3D Winding Algorithm ──────────────────────────────────────

def get_octant_id(x: int, y: int, z: int, dim: int) -> int:
    """Returns the octant ID (0..7) for a voxel coordinate in a Dim x Dim x Dim cube."""
    mid = dim // 2
    ox = 1 if x >= mid else 0
    oy = 1 if y >= mid else 0
    oz = 1 if z >= mid else 0
    return (oz << 2) | (oy << 1) | ox


def generate_sparse_center_out_path(
    dim: int,
    quadrant_mask: int = 0xFF,
    clockwise: bool = True
) -> List[Tuple[int, int, int]]:
    """
    Generates a 3D Center-Out spiral trajectory that automatically slides
    over and omits any inactive quadrants/octants specified in `quadrant_mask`.
    """
    path: List[Tuple[int, int, int]] = []
    visited: Set[Tuple[int, int, int]] = set()
    center = dim // 2

    # 2D spiral coordinates on a dim x dim slice
    spiral_2d: List[Tuple[int, int]] = [(center, center)]
    dirs = [(0, -1), (1, 0), (0, 1), (-1, 0)] if clockwise else [(0, -1), (-1, 0), (0, 1), (1, 0)]
    x, y = center, center
    dir_idx = 0
    step_length = 1
    step_count = 0

    while len(spiral_2d) < dim * dim:
        for _ in range(step_length):
            dx, dy = dirs[dir_idx]
            x += dx
            y += dy
            if 0 <= x < dim and 0 <= y < dim:
                spiral_2d.append((x, y))
                if len(spiral_2d) >= dim * dim:
                    break
        dir_idx = (dir_idx + 1) % 4
        step_count += 1
        if step_count % 2 == 0:
            step_length += 1

    # Center-out expanding z-layer sequence
    layer_order = [center]
    for off in range(1, dim):
        if center + off < dim:
            layer_order.append(center + off)
        if center - off >= 0:
            layer_order.append(center - off)

    # Traverse layers and filter voxels by quadrant mask
    for z in layer_order:
        for px, py in spiral_2d:
            voxel = (px, py, z)
            if voxel not in visited:
                visited.add(voxel)
                octant = get_octant_id(px, py, z, dim)
                # Check if this octant is active in the bitmask
                if (quadrant_mask & (1 << octant)) != 0:
                    path.append(voxel)

    return path


# Backward compatibility alias
CubicalAddressEngine = UUIDv7_4_Engine

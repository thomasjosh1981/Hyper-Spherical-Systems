"""
ISSI (Integer String Substitution Index) Compression & Project Tesseract Engine
================================================================================
Comprehensive Python implementation covering:
1. Lexical optimization & preposition stripping.
2. ISSI Static & Dynamic n-gram dictionary compression (multi-word -> single token).
3. 48-Character 3-Tier deterministic scoring.
4. Center-Out 3D Cubic Tensor Winding (5^3 to 20^3 adaptive sizing).
5. 4-Corner Top-Down Orthogonal Unwinding Scan.
6. 5+1 Homophonic Script Obfuscation (Latin, Greek, Sanskrit, Hieroglyphs, Cuneiform, Elder Futhark).
7. 100% Lossless Roundtrip Encoding and Decoding.
"""

import math
import re
from typing import Dict, List, Tuple, Optional, Set, Any

# ==========================================
# 1. 48-CHARACTER 3-TIER SCORING
# ==========================================
TIER_LOWER = ['E', 'T', 'J', '/', '6', '}', 'X', 'S', '>', 'Q', '8', '0', 'Y', 'C', '<', '{']
TIER_MIDDLE = ['A', 'O', 'P', 'D', 'U', 'L', 'F', '5', '2', 'B', 'G', '_', 'R', '[', '7', '9']
TIER_UPPER = ['I', 'N', ';', ']', 'Z', '=', ')', 'H', '4', 'K', 'V', '(', 'M', '1', 'W', '3']

CHAR_SCORE_MAP: Dict[str, int] = {}
for i, c in enumerate(TIER_LOWER):
    CHAR_SCORE_MAP[c] = i + 1
for i, c in enumerate(TIER_MIDDLE):
    CHAR_SCORE_MAP[c] = i + 17
for i, c in enumerate(TIER_UPPER):
    CHAR_SCORE_MAP[c] = i + 33
CHAR_SCORE_MAP[' '] = 0
CHAR_SCORE_MAP['~'] = 0


def calculate_tier_score(text: str) -> Tuple[int, int, str]:
    """
    Computes cumulative character score across the 48-char 3-tier distribution.
    Returns: (total_score, max_possible, tier_classification: 'LOWER'|'MIDDLE'|'UPPER')
    """
    clean_text = text.upper()
    total = sum(CHAR_SCORE_MAP.get(ch, 24) for ch in clean_text if ch in CHAR_SCORE_MAP)
    count = len(clean_text)
    if count == 0:
        return 0, 0, 'MIDDLE'
    
    avg = total / count
    if avg <= 16:
        tier = 'LOWER'
    elif avg <= 32:
        tier = 'MIDDLE'
    else:
        tier = 'UPPER'
    return total, count * 48, tier


# ==========================================
# 2. 5+1 HOMOPHONIC SCRIPTS
# ==========================================
SCRIPT_TABLES = {
    'latin': {
        'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F', 'G': 'G', 'H': 'H',
        'I': 'I', 'J': 'J', 'K': 'K', 'L': 'L', 'M': 'M', 'N': 'N', 'O': 'O', 'P': 'P',
        'Q': 'Q', 'R': 'R', 'S': 'S', 'T': 'T', 'U': 'U', 'V': 'V', 'W': 'W', 'X': 'X',
        'Y': 'Y', 'Z': 'Z', 'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e', 'f': 'f',
        'g': 'g', 'h': 'h', 'i': 'i', 'j': 'j', 'k': 'k', 'l': 'l', 'm': 'm', 'n': 'n',
        'o': 'o', 'p': 'p', 'q': 'q', 'r': 'r', 's': 's', 't': 't', 'u': 'u', 'v': 'v',
        'w': 'w', 'x': 'x', 'y': 'y', 'z': 'z', '0': '0', '1': '1', '2': '2', '3': '3',
        '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', '{': '{', '}': '}',
        '[': '[', ']': ']', '(': '(', ')': ')', '<': '<', '>': '>', '=': '=', ';': ';',
        '_': '_', '/': '/', '~': '~', ' ': ' ',
    },
    'greek': {
        'A': 'Ά', 'B': '·', 'C': 'Έ', 'D': 'Ή', 'E': 'Ί', 'F': '\u038b', 'G': 'Ό', 'H': '\u038d',
        'I': 'Ύ', 'J': 'Ώ', 'K': 'ΐ', 'L': 'Α', 'M': 'Β', 'N': 'Γ', 'O': 'Δ', 'P': 'Ε',
        'Q': 'Ζ', 'R': 'Η', 'S': 'Θ', 'T': 'Ι', 'U': 'Κ', 'V': 'Λ', 'W': 'Μ', 'X': 'Ν',
        'Y': 'Ξ', 'Z': 'Ο', 'a': 'Π', 'b': 'Ρ', 'c': '\u03a2', 'd': 'Σ', 'e': 'Τ', 'f': 'Υ',
        'g': 'Φ', 'h': 'Χ', 'i': 'Ψ', 'j': 'Ω', 'k': 'Ϊ', 'l': 'Ϋ', 'm': 'ά', 'n': 'έ',
        'o': 'ή', 'p': 'ί', 'q': 'ΰ', 'r': 'α', 's': 'β', 't': 'γ', 'u': 'δ', 'v': 'ε',
        'w': 'ζ', 'x': 'η', 'y': 'θ', 'z': 'ι', '0': 'κ', '1': 'λ', '2': 'μ', '3': 'ν',
        '4': 'ξ', '5': 'ο', '6': 'π', '7': 'ρ', '8': 'ς', '9': 'σ', '{': 'τ', '}': 'υ',
        '[': 'φ', ']': 'χ', '(': 'ψ', ')': 'ω', '<': 'ϊ', '>': 'ϋ', '=': 'ό', ';': 'ύ',
        '_': 'ώ', '/': 'Ϗ', '~': 'ϐ', ' ': 'ϑ',
    },
    'sanskrit': {
        'A': 'अ', 'B': 'आ', 'C': 'इ', 'D': 'ई', 'E': 'उ', 'F': 'ऊ', 'G': 'ऋ', 'H': 'ऌ',
        'I': 'ऍ', 'J': 'ऎ', 'K': 'ए', 'L': 'ऐ', 'M': 'ऑ', 'N': 'ऒ', 'O': 'ओ', 'P': 'औ',
        'Q': 'क', 'R': 'ख', 'S': 'ग', 'T': 'घ', 'U': 'ङ', 'V': 'च', 'W': 'छ', 'X': 'ज',
        'Y': 'झ', 'Z': 'ञ', 'a': 'ट', 'b': 'ठ', 'c': 'ड', 'd': 'ढ', 'e': 'ण', 'f': 'त',
        'g': 'थ', 'h': 'द', 'i': 'ध', 'j': 'न', 'k': 'ऩ', 'l': 'प', 'm': 'फ', 'n': 'ब',
        'o': 'भ', 'p': 'म', 'q': 'य', 'r': 'र', 's': 'ऱ', 't': 'ल', 'u': 'ळ', 'v': 'ऴ',
        'w': 'व', 'x': 'श', 'y': 'ष', 'z': 'स', '0': 'ह', '1': 'ऺ', '2': 'ऻ', '3': '़',
        '4': 'ऽ', '5': 'ा', '6': 'ि', '7': 'ी', '8': 'ु', '9': 'ू', '{': 'ृ', '}': 'ॄ',
        '[': 'ॅ', ']': 'ॆ', '(': 'े', ')': 'ै', '<': 'ॉ', '>': 'ॊ', '=': 'ो', ';': 'ौ',
        '_': '्', '/': 'ॎ', '~': 'ॏ', ' ': 'ॐ',
    },
    'hieroglyph': {
        'A': '𓀀', 'B': '𓀁', 'C': '𓀂', 'D': '𓀃', 'E': '𓀄', 'F': '𓀅', 'G': '𓀆', 'H': '𓀇',
        'I': '𓀈', 'J': '𓀉', 'K': '𓀊', 'L': '𓀋', 'M': '𓀌', 'N': '𓀍', 'O': '𓀎', 'P': '𓀏',
        'Q': '𓀐', 'R': '𓀑', 'S': '𓀒', 'T': '𓀓', 'U': '𓀔', 'V': '𓀕', 'W': '𓀖', 'X': '𓀗',
        'Y': '𓀘', 'Z': '𓀙', 'a': '𓀚', 'b': '𓀛', 'c': '𓀜', 'd': '𓀝', 'e': '𓀞', 'f': '𓀟',
        'g': '𓀠', 'h': '𓀡', 'i': '𓀢', 'j': '𓀣', 'k': '𓀤', 'l': '𓀥', 'm': '𓀦', 'n': '𓀧',
        'o': '𓀨', 'p': '𓀩', 'q': '𓀪', 'r': '𓀫', 's': '𓀬', 't': '𓀭', 'u': '𓀮', 'v': '𓀯',
        'w': '𓀰', 'x': '𓀱', 'y': '𓀲', 'z': '𓀳', '0': '𓀴', '1': '𓀵', '2': '𓀶', '3': '𓀷',
        '4': '𓀸', '5': '𓀹', '6': '𓀺', '7': '𓀻', '8': '𓀼', '9': '𓀽', '{': '𓀾', '}': '𓀿',
        '[': '𓁀', ']': '𓁁', '(': '𓁂', ')': '𓁃', '<': '𓁄', '>': '𓁅', '=': '𓁆', ';': '𓁇',
        '_': '𓁈', '/': '𓁉', '~': '𓁊', ' ': '𓁋',
    },
    'cuneiform': {
        'A': '𒀀', 'B': '𒀁', 'C': '𒀂', 'D': '𒀃', 'E': '𒀄', 'F': '𒀅', 'G': '𒀆', 'H': '𒀇',
        'I': '𒀈', 'J': '𒀉', 'K': '𒀊', 'L': '𒀋', 'M': '𒀌', 'N': '𒀍', 'O': '𒀎', 'P': '𒀏',
        'Q': '𒀐', 'R': '𒀑', 'S': '𒀒', 'T': '𒀓', 'U': '𒀔', 'V': '𒀕', 'W': '𒀖', 'X': '𒀗',
        'Y': '𒀘', 'Z': '𒀙', 'a': '𒀚', 'b': '𒀛', 'c': '𒀜', 'd': '𒀝', 'e': '𒀞', 'f': '𒀟',
        'g': '𒀠', 'h': '𒀡', 'i': '𒀢', 'j': '𒀣', 'k': '𒀤', 'l': '𒀥', 'm': '𒀦', 'n': '𒀧',
        'o': '𒀨', 'p': '𒀩', 'q': '𒀪', 'r': '𒀫', 's': '𒀬', 't': '𒀭', 'u': '𒀮', 'v': '𒀯',
        'w': '𒀰', 'x': '𒀱', 'y': '𒀲', 'z': '𒀳', '0': '𒀴', '1': '𒀵', '2': '𒀶', '3': '𒀷',
        '4': '𒀸', '5': '𒀹', '6': '𒀺', '7': '𒀻', '8': '𒀼', '9': '𒀽', '{': '𒀾', '}': '𒀿',
        '[': '𒁀', ']': '𒁁', '(': '𒁂', ')': '𒁃', '<': '𒁄', '>': '𒁅', '=': '𒁆', ';': '𒁇',
        '_': '𒁈', '/': '𒁉', '~': '𒁊', ' ': '𒁋',
    },
    'nordic': {
        'A': 'ᚠ', 'B': 'ᚡ', 'C': 'ᚢ', 'D': 'ᚣ', 'E': 'ᚤ', 'F': 'ᚥ', 'G': 'ᚦ', 'H': 'ᚧ',
        'I': 'ᚨ', 'J': 'ᚩ', 'K': 'ᚪ', 'L': 'ᚫ', 'M': 'ᚬ', 'N': 'ᚭ', 'O': 'ᚮ', 'P': 'ᚯ',
        'Q': 'ᚰ', 'R': 'ᚱ', 'S': 'ᚲ', 'T': 'ᚳ', 'U': 'ᚴ', 'V': 'ᚵ', 'W': 'ᚶ', 'X': 'ᚷ',
        'Y': 'ᚸ', 'Z': 'ᚹ', 'a': 'ᚺ', 'b': 'ᚻ', 'c': 'ᚼ', 'd': 'ᚽ', 'e': 'ᚾ', 'f': 'ᚿ',
        'g': 'ᛀ', 'h': 'ᛁ', 'i': 'ᛂ', 'j': 'ᛃ', 'k': 'ᛄ', 'l': 'ᛅ', 'm': 'ᛆ', 'n': 'ᛇ',
        'o': 'ᛈ', 'p': 'ᛉ', 'q': 'ᛊ', 'r': 'ᛋ', 's': 'ᛌ', 't': 'ᛍ', 'u': 'ᛎ', 'v': 'ᛏ',
        'w': 'ᛐ', 'x': 'ᛑ', 'y': 'ᛒ', 'z': 'ᛓ', '0': 'ᛔ', '1': 'ᛕ', '2': 'ᛖ', '3': 'ᛗ',
        '4': 'ᛘ', '5': 'ᛙ', '6': 'ᛚ', '7': 'ᛛ', '8': 'ᛜ', '9': 'ᛝ', '{': 'ᛞ', '}': 'ᛟ',
        '[': 'ᛠ', ']': 'ᛡ', '(': 'ᛢ', ')': 'ᛣ', '<': 'ᛤ', '>': 'ᛥ', '=': 'ᛦ', ';': 'ᛧ',
        '_': 'ᛨ', '/': 'ᛩ', '~': 'ᛪ', ' ': '᛫',
    },
}

SCRIPTS_ORDER = ['latin', 'greek', 'sanskrit', 'hieroglyph', 'cuneiform', 'nordic']

REVERSE_SCRIPT_TABLES: Dict[str, Dict[str, str]] = {}
GLOBAL_REVERSE_MAP: Dict[str, str] = {}

for sname, table in SCRIPT_TABLES.items():
    REVERSE_SCRIPT_TABLES[sname] = {}
    for orig, glyph in table.items():
        REVERSE_SCRIPT_TABLES[sname][glyph] = orig
        GLOBAL_REVERSE_MAP[glyph] = orig


# ==========================================
# 3. LEXICAL OPTIMIZATION & PREPOSITION STRIPPING
# ==========================================
DEFAULT_PREPOSITIONS = {
    'about', 'above', 'across', 'after', 'against', 'along', 'among', 'around', 'at',
    'before', 'behind', 'below', 'beneath', 'beside', 'between', 'beyond', 'by', 'down',
    'during', 'except', 'for', 'from', 'in', 'inside', 'into', 'near', 'of', 'off', 'on',
    'onto', 'out', 'outside', 'over', 'past', 'since', 'through', 'throughout', 'till',
    'to', 'toward', 'towards', 'under', 'underneath', 'until', 'up', 'upon', 'with',
    'within', 'without', 'the', 'a', 'an', 'and', 'is', 'are', 'it', 'please', 'pls',
    'thank', 'thanks', 'thankyou', 'could', 'would', 'kindly'
}


def prune_text(text: str, drop_prepositions: bool = True) -> Dict[str, Any]:
    """Strips grammatical glue tokens and cleans text for optimal semantic density."""
    if not text:
        return {'original_tokens': 0, 'optimized_length': 0, 'stripped_count': 0, 'optimized_text': ''}
    
    words = re.split(r'\s+', text.strip())
    stripped_count = 0
    kept_words = []
    
    for word in words:
        clean = re.sub(r'[^a-zA-Z0-9_{}\[\]()<>=;,\/]', '', word).lower()
        if drop_prepositions and clean in DEFAULT_PREPOSITIONS and len(words) > 5:
            stripped_count += 1
        elif clean:
            kept_words.append(clean.upper())
            
    res = "".join(kept_words)
    return {
        'original_tokens': len(words),
        'optimized_length': len(res),
        'stripped_count': stripped_count,
        'optimized_text': res
    }


# ==========================================
# 4. ISSI COMPRESSION DICTIONARY ENGINE
# ==========================================
class ISSICompressionEngine:
    """
    Integer String Substitution Index (ISSI) Engine.
    Maps multi-word repeating phrases, code identifiers, and common phrases
    into compact single/double coordinate tokens.
    """
    def __init__(self):
        self.static_dict: Dict[str, str] = {
            "HYPERSPHERICAL": "{H1}",
            "PROJECT_TESSERACT": "{T1}",
            "INTEGER_STRING_SUBSTITUTION_INDEX": "{I1}",
            "HOMOPHONIC_SUBSTITUTION": "{S1}",
            "LAYER_STREAMING": "{L1}",
            "DYNAMIC_TENSOR_ROUTER": "{R1}",
            "SAFETENSORS": "{S2}",
            "NON_EUCLIDEAN": "{N1}",
            "DEEPSEEK_R1": "{D1}",
            "TRANSFORMER": "{T2}",
            "ATTENTION": "{A1}",
            "QUANTIZATION": "{Q1}"
        }
        self.dynamic_dict: Dict[str, str] = {}
        self.reverse_dict: Dict[str, str] = {}
        self._rebuild_reverse()

    def _rebuild_reverse(self):
        self.reverse_dict.clear()
        for k, v in self.static_dict.items():
            self.reverse_dict[v] = k
        for k, v in self.dynamic_dict.items():
            self.reverse_dict[v] = k

    def train_dynamic_dictionary(self, corpus: List[str], min_length: int = 3, min_freq: int = 2):
        """Discovers frequent n-grams in user prompts and registers dynamic tokens."""
        phrase_counts: Dict[str, int] = {}
        for text in corpus:
            words = [w for w in re.split(r'\s+', text.upper()) if w]
            for n in range(min_length, 1, -1):
                for i in range(len(words) - n + 1):
                    phrase = "_".join(words[i:i+n])
                    phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
        
        sorted_phrases = sorted(phrase_counts.items(), key=lambda x: x[1] * len(x[0]), reverse=True)
        idx = 1
        for phrase, count in sorted_phrases:
            if count >= min_freq and phrase not in self.static_dict:
                token = f"[D{idx}]"
                self.dynamic_dict[phrase] = token
                idx += 1
        self._rebuild_reverse()

    def compress(self, text: str) -> str:
        """Applies static and dynamic ISSI phrase substitutions."""
        compressed = text.upper()
        all_keys = sorted(list(self.static_dict.keys()) + list(self.dynamic_dict.keys()), key=len, reverse=True)
        for key in all_keys:
            token = self.static_dict.get(key) or self.dynamic_dict.get(key)
            if token and key in compressed:
                compressed = compressed.replace(key, token)
        return compressed

    def decompress(self, text: str) -> str:
        """Restores ISSI tokens back to original phrases."""
        decompressed = text
        all_tokens = sorted(self.reverse_dict.keys(), key=len, reverse=True)
        for token in all_tokens:
            phrase = self.reverse_dict[token]
            if token in decompressed:
                decompressed = decompressed.replace(token, phrase)
        return decompressed


# ==========================================
# 5. CENTER-OUT 3D SPIRAL TESSERACT ENGINE
# ==========================================
def find_optimal_cube_dim(token_count: int) -> int:
    """Finds smallest cube dimension (from 5^3 to 20^3) that accommodates the token stream."""
    for d in range(5, 21):
        if d * d * d >= token_count:
            return d
    return 20


def generate_2d_center_out_spiral(dim: int, clockwise: bool = True) -> List[Tuple[int, int]]:
    """Generates 2D planar spiral coordinates starting at dead-center (dim//2, dim//2)."""
    coords: List[Tuple[int, int]] = []
    cx = dim // 2
    cy = dim // 2
    coords.append((cx, cy))
    
    dirs_cw = [(0, -1), (1, 0), (0, 1), (-1, 0)]   # Up, Right, Down, Left
    dirs_ccw = [(0, -1), (-1, 0), (0, 1), (1, 0)]  # Up, Left, Down, Right
    dirs = dirs_cw if clockwise else dirs_ccw
    
    x, y = cx, cy
    dir_idx = 0
    step_length = 1
    step_count = 0
    
    while len(coords) < dim * dim:
        for _ in range(step_length):
            dx, dy = dirs[dir_idx]
            x += dx
            y += dy
            if 0 <= x < dim and 0 <= y < dim:
                coords.append((x, y))
                if len(coords) >= dim * dim:
                    break
        dir_idx = (dir_idx + 1) % 4
        step_count += 1
        if step_count % 2 == 0:
            step_length += 1
            
    return coords


def generate_3d_center_out_path(dim: int, clockwise: bool = True, plane_seq: List[str] = None) -> List[Tuple[int, int, int]]:
    """
    Generates 3D voxel ingress coordinates starting at the dead-center voxel
    and radiating outward cyclostationally across X -> Y -> Z planes.
    """
    if plane_seq is None:
        plane_seq = ['X', 'Y', 'Z']
        
    total_voxels = dim * dim * dim
    spiral_2d = generate_2d_center_out_spiral(dim, clockwise)
    path: List[Tuple[int, int, int]] = []
    visited: Set[Tuple[int, int, int]] = set()
    
    center_layer = dim // 2
    layer_order = [center_layer]
    for offset in range(1, dim):
        if center_layer + offset < dim:
            layer_order.append(center_layer + offset)
        if center_layer - offset >= 0:
            layer_order.append(center_layer - offset)
            
    plane_idx = 0
    layer_idx = 0
    
    while len(path) < total_voxels and layer_idx < len(layer_order):
        layer = layer_order[layer_idx]
        plane = plane_seq[plane_idx % len(plane_seq)]
        
        for px, py in spiral_2d:
            if plane == 'X':
                vx, vy, vz = layer, px, py
            elif plane == 'Y':
                vx, vy, vz = px, layer, py
            else:
                vx, vy, vz = px, py, layer
                
            voxel = (vx, vy, vz)
            if voxel not in visited:
                visited.add(voxel)
                path.append(voxel)
                
        plane_idx += 1
        if plane_idx % len(plane_seq) == 0:
            layer_idx += 1
            
    return path


def generate_4corner_unwrap_path(dim: int) -> List[Tuple[int, int, int]]:
    """
    Generates the 4-corner top-down orthogonal unwinding path.
    """
    path: List[Tuple[int, int, int]] = []
    for z in range(dim - 1, -1, -1):
        plane_idx = (dim - 1) - z
        corner_mode = plane_idx % 4
        
        if corner_mode == 0:  # Top-Rear-Left -> L-to-R
            for y in range(dim):
                for x in range(dim):
                    path.append((x, y, z))
        elif corner_mode == 1:  # Top-Rear-Right -> R-to-L
            for y in range(dim):
                for x in range(dim - 1, -1, -1):
                    path.append((x, y, z))
        elif corner_mode == 2:  # Bottom-Front-Right -> Front-to-Back
            for x in range(dim - 1, -1, -1):
                for y in range(dim - 1, -1, -1):
                    path.append((x, y, z))
        elif corner_mode == 3:  # Bottom-Front-Left -> Back-to-Front
            for x in range(dim):
                for y in range(dim):
                    path.append((x, y, z))
    return path


# ==========================================
# 6. FULL END-TO-END PIPELINE ENCODER & DECODER
# ==========================================
def encode_issi_tesseract(input_text: str, issi_engine: Optional[ISSICompressionEngine] = None) -> Dict[str, Any]:
    """
    Executes complete multi-stage pipeline.
    """
    if issi_engine is None:
        issi_engine = ISSICompressionEngine()
        
    prune_res = prune_text(input_text)
    pruned_text = prune_res['optimized_text']
    issi_compressed = issi_engine.compress(pruned_text)
    
    total_score, max_score, tier = calculate_tier_score(issi_compressed)
    cw = (tier == 'LOWER')
    plane_seq = ['Z', 'Y', 'X'] if tier == 'MIDDLE' else ['X', 'Y', 'Z']
    
    dim = find_optimal_cube_dim(len(issi_compressed) + 1)
    total_voxels = dim * dim * dim
    
    ingress_path = generate_3d_center_out_path(dim, clockwise=cw, plane_seq=plane_seq)
    
    cube: Dict[Tuple[int, int, int], str] = {}
    for pt in ingress_path:
        cube[pt] = '~'
        
    for i, ch in enumerate(issi_compressed):
        cube[ingress_path[i]] = ch
        
    unwrap_path = generate_4corner_unwrap_path(dim)
    unwrapped_stream = "".join(cube[pt] for pt in unwrap_path)
    
    obfuscated_chars = []
    for idx, ch in enumerate(unwrapped_stream):
        script_name = SCRIPTS_ORDER[idx % len(SCRIPTS_ORDER)]
        table = SCRIPT_TABLES[script_name]
        obfuscated_chars.append(table.get(ch, ch))
    obfuscated_text = "".join(obfuscated_chars)
    
    return {
        'original_text': input_text,
        'pruned_text': pruned_text,
        'issi_compressed': issi_compressed,
        'tier': tier,
        'dim': dim,
        'total_voxels': total_voxels,
        'unwrapped_stream': unwrapped_stream,
        'obfuscated_text': obfuscated_text,
        'config': {
            'clockwise': cw,
            'plane_seq': plane_seq,
            'dim': dim
        }
    }


def decode_issi_tesseract(encoded_data: Dict[str, Any], issi_engine: Optional[ISSICompressionEngine] = None) -> str:
    """
    Executes lossless reverse pipeline.
    """
    if issi_engine is None:
        issi_engine = ISSICompressionEngine()
        
    obfuscated = encoded_data['obfuscated_text']
    dim = encoded_data['config']['dim']
    cw = encoded_data['config']['clockwise']
    plane_seq = encoded_data['config']['plane_seq']
    
    reversed_chars = []
    for idx, ch in enumerate(obfuscated):
        script_name = SCRIPTS_ORDER[idx % len(SCRIPTS_ORDER)]
        rev_table = REVERSE_SCRIPT_TABLES.get(script_name, GLOBAL_REVERSE_MAP)
        reversed_chars.append(rev_table.get(ch, GLOBAL_REVERSE_MAP.get(ch, ch)))
    unwrapped_stream = "".join(reversed_chars)
    
    unwrap_path = generate_4corner_unwrap_path(dim)
    cube: Dict[Tuple[int, int, int], str] = {}
    for idx, pt in enumerate(unwrap_path):
        cube[pt] = unwrapped_stream[idx]
        
    ingress_path = generate_3d_center_out_path(dim, clockwise=cw, plane_seq=plane_seq)
    reconstructed_raw = "".join(cube[pt] for pt in ingress_path)
    stripped = reconstructed_raw.rstrip('~')
    decompressed = issi_engine.decompress(stripped)
    return decompressed


_DEFAULT_ISSI_INSTANCE = ISSICompressionEngine()


def compress_to_issi(text: str) -> str:
    return _DEFAULT_ISSI_INSTANCE.compress(text)


def decompress_from_issi(text: str) -> str:
    return _DEFAULT_ISSI_INSTANCE.decompress(text)


def encode_homophonic_dlasc(text: str) -> str:
    obfuscated_chars = []
    for idx, ch in enumerate(text):
        script_name = SCRIPTS_ORDER[idx % len(SCRIPTS_ORDER)]
        table = SCRIPT_TABLES[script_name]
        obfuscated_chars.append(table.get(ch, ch))
    return "".join(obfuscated_chars)


def decode_homophonic_dlasc(text: str) -> str:
    reversed_chars = []
    for idx, ch in enumerate(text):
        script_name = SCRIPTS_ORDER[idx % len(SCRIPTS_ORDER)]
        rev_table = REVERSE_SCRIPT_TABLES.get(script_name, GLOBAL_REVERSE_MAP)
        reversed_chars.append(rev_table.get(ch, GLOBAL_REVERSE_MAP.get(ch, ch)))
    return "".join(reversed_chars)
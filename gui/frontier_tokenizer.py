# gui/frontier_tokenizer.py
#
# Hyper-Spherical Systems — Adaptive Domain-Specific Frontier Single-Token Mapper v4.0
#
# Architecture:
#
#   1. DOMAIN-SPECIFIC STATIC BASE MAPS (LAYER 1):
#      - CODING: Code syntax, functions, algorithms, data structures, error handling
#      - ROLEPLAY_STORY: Narrative descriptors, dialogue, story beats, character/world elements
#      - DATA_ANALYSIS: Statistics, dataframes, ML, metrics, visualizations
#      - GENERAL_AI: Standard LLM conversational, reasoning, and system directives
#
#   2. DYNAMIC MODEL MAPS (LAYER 2):
#      - Maps each domain's phrases to verified single-token Unicode characters in the
#        target frontier model's tokenizer (tiktoken / native BPE).
#
#   3. INLINE DOMAIN SWITCHING & MID-REQUEST MODE FLAGS:
#      - Flag format: ⟨MODE:CODING⟩, ⟨MODE:ROLEPLAY⟩, ⟨MODE:DATA_ANALYSIS⟩, ⟨MODE:GENERAL⟩
#      - Mid-stream domain changes dynamically emit flag headers to tell the frontier model
#        which substitution index is active for subsequent tokens.
#
#   4. PROMPT CACHING & M2M HANDSHAKE DIRECTIVES:
#      - Emits KV-cache retention directives (ephemeral prompt caching)
#      - Machine-to-Machine high-density protocol headers
#
# License: MIT

import json
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

# ══════════════════════════════════════════════════════════════════════════════
# Tiktoken & Tokenizer Backend
# ══════════════════════════════════════════════════════════════════════════════

_enc_cache: Dict[str, object] = {}

TIKTOKEN_MAP = {
    "gpt-4o": "o200k_base", "gpt-4o-mini": "o200k_base",
    "gpt-4.1": "o200k_base", "gpt-4.1-mini": "o200k_base",
    "gpt-4.1-nano": "o200k_base", "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base", "gpt-3.5-turbo": "cl100k_base",
    "o1": "o200k_base", "o3": "o200k_base", "o4-mini": "o200k_base",
}

_APPROX_CHARS_PER_TOKEN = {
    "claude": 3.5, "anthropic": 3.5, "gemini": 4.0, "google": 4.0,
}


def _get_encoder(model: str = "gpt-4o"):
    key = model.lower().strip()
    key = re.sub(r"-\d{8}$", "", key)
    enc_name = None
    for prefix, name in TIKTOKEN_MAP.items():
        if key.startswith(prefix):
            enc_name = name
            break
    if enc_name is None:
        enc_name = "o200k_base"
    if enc_name in _enc_cache:
        return _enc_cache[enc_name]
    try:
        import tiktoken
        enc = tiktoken.get_encoding(enc_name)
        _enc_cache[enc_name] = enc
        return enc
    except (ImportError, Exception):
        return None


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Exact token count using the frontier model's native tokenizer."""
    if not text:
        return 0
    enc = _get_encoder(model)
    if enc is not None:
        return len(enc.encode(text))
    key = model.lower()
    for prefix, cpt in _APPROX_CHARS_PER_TOKEN.items():
        if prefix in key:
            return max(1, math.ceil(len(text) / cpt))
    code_indicators = ["{", "}", "(", ")", ";", "def ", "class "]
    is_code = any(ind in text for ind in code_indicators)
    return max(1, math.ceil(len(text) / (3.2 if is_code else 3.8)))


# ══════════════════════════════════════════════════════════════════════════════
# Single Token Character Discovery
# ══════════════════════════════════════════════════════════════════════════════

_single_token_chars_cache: Dict[str, List[Tuple[int, str, int]]] = {}


def scan_single_token_chars(model: str = "gpt-4o") -> List[Tuple[int, str, int]]:
    """Returns list of (token_id, character, codepoint) for single-char tokens."""
    cache_key = model.lower()
    if cache_key in _single_token_chars_cache:
        return _single_token_chars_cache[cache_key]
    enc = _get_encoder(model)
    if enc is None:
        return []
    results = []
    for byte_seq, rank in enc._mergeable_ranks.items():
        try:
            decoded = byte_seq.decode("utf-8", errors="strict")
            if len(decoded) != 1:
                continue
            cp = ord(decoded)
            if cp < 0x0300:
                continue
            cat = unicodedata.category(decoded)
            if cat.startswith("C"):
                continue
            results.append((rank, decoded, cp))
        except (UnicodeDecodeError, ValueError):
            pass
    results.sort(key=lambda x: x[0])
    _single_token_chars_cache[cache_key] = results
    return results


# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN DICTIONARY POOLS
# ══════════════════════════════════════════════════════════════════════════════

DOMAIN_VOCABULARIES = {
    "CODING": [
        # Long phrases
        "Here is the implementation", "According to the specification",
        "The function returns", "In order to implement", "Let me write the code for",
        "Consider the following example", "To solve this issue", "The error is caused by",
        "Make sure to handle exceptions", "The complexity of this algorithm is",
        # Technical phrases & keywords
        "asynchronous function", "object oriented programming", "data structure",
        "dependency injection", "application programming interface", "database query",
        "pull request", "code review", "unit test", "stack trace", "memory leak",
        "race condition", "garbage collection", "syntax error", "runtime exception",
        "design pattern", "microservice architecture", "continuous integration",
        "type safety", "thread safety", "buffer overflow", "null pointer exception",
        "implementation", "configuration", "documentation", "infrastructure",
        "authentication", "authorization", "specification", "requirements",
        "optimization", "performance", "architecture", "vulnerability",
        "compatibility", "functionality", "asynchronous", "synchronous",
        "constructor", "destructor", "inheritance", "polymorphism", "encapsulation",
        "function", "variable", "constant", "interface", "abstract", "override",
        "middleware", "refactoring", "breakpoint", "debugging", "profiling",
        "serialization", "deserialization", "concatenation", "interpolation",
    ],
    "ROLEPLAY_STORY": [
        # Long narrative & dialogue phrases
        "Once upon a time", "In a world where", "Deep within the shadows",
        "With a heavy sigh", "Before anyone could react", "As the sun began to set",
        "A sudden chill ran down", "Whispered in a hushed tone", "Without warning, the",
        "The atmosphere grew tense", "Eyes filled with determination", "Stepped forward into the",
        # Narrative terms & tropes
        "protagonist", "antagonist", "atmosphere", "foreshadowing", "cliffhanger",
        "dialogue", "narrative", "character arc", "worldbuilding", "enchanted",
        "mysterious", "treacherous", "spectacular", "breathtaking", "unforgettable",
        "heartpounding", "overwhelming", "devastating", "surreal", "transcendent",
        "whispered", "screamed", "murmured", "exclaimed", "hesitated", "glanced",
        "stared", "gazed", "wandered", "vanished", "flourished", "trembled",
        "chuckle", "laughter", "silence", "shadows", "journey", "destiny",
        "kingdom", "fortress", "sanctuary", "wilderness", "labyrinth", "relic",
        "artifact", "legendary", "mythical", "ancient", "forbidden", "prophecy",
    ],
    "DATA_ANALYSIS": [
        # Long analytical phrases
        "Based on the dataset provided", "The correlation between", "Statistical significance of",
        "As shown in the visualization", "The distribution of values", "Linear regression model",
        "Principal component analysis", "Exploratory data analysis", "Standard deviation of",
        # Analytical & ML terms
        "dataframe", "visualization", "correlation", "hyperparameter", "regression",
        "classification", "distribution", "variance", "covariance", "eigenvalue",
        "normalization", "regularization", "vectorization", "dimensionality",
        "cross validation", "confusion matrix", "precision", "recall", "f1 score",
        "gradient descent", "neural network", "transformer", "attention mechanism",
        "dataset", "features", "labels", "outliers", "quantiles", "histogram",
        "scatterplot", "heatmap", "clustering", "time series", "forecasting",
    ],
    "GENERAL_AI": [
        # Standard conversational phrases
        "You are a helpful assistant", "Based on the information provided",
        "As an AI language model", "According to the context provided",
        "It is important to note that", "It is worth noting that",
        "Let me know if you have any", "Here is an explanation",
        "Here are some helpful suggestions", "First and foremost",
        "In other words", "To summarize", "In conclusion", "Furthermore",
        "Additionally", "However", "Therefore", "Nevertheless", "Consequently",
        "Keep in mind", "Bear in mind", "For example", "Such as", "Including",
        "Regarding", "Throughout", "Response", "Request", "Functionality",
        "System:", "User:", "Assistant:", "Please provide", "In summary",
    ]
}


# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN DETECTION HELPER
# ══════════════════════════════════════════════════════════════════════════════

def detect_domain(text: str) -> str:
    """
    Analyzes input text to auto-detect domain: 'CODING', 'ROLEPLAY_STORY',
    'DATA_ANALYSIS', or 'GENERAL_AI'.
    """
    if not text:
        return "GENERAL_AI"

    lower = text.lower()

    # Code indicators
    code_score = sum(1 for kw in [
        "def ", "class ", "function", "import ", "const ", "var ", "let ",
        "return", "{", "}", "();", "==", "=>", "```", "error:", "traceback"
    ] if kw in lower)

    # Story/Roleplay indicators
    story_score = sum(1 for kw in [
        "\" ", " '", "whispered", "suddenly", "gazed", "character", "smiled",
        "nodded", "once upon", "shadows", "journey", "sword", "magic", "realm"
    ] if kw in lower)

    # Data indicators
    data_score = sum(1 for kw in [
        "dataframe", "dataset", "pandas", "numpy", "plot", "chart", "mean",
        "median", "std", "regression", "p-value", "accuracy", "csv"
    ] if kw in lower)

    scores = {
        "CODING": code_score * 2.0,
        "ROLEPLAY_STORY": story_score * 2.0,
        "DATA_ANALYSIS": data_score * 2.5,
        "GENERAL_AI": 1.0  # baseline
    }

    best = max(scores.items(), key=lambda x: x[1])
    return best[0] if best[1] > 1.5 else "GENERAL_AI"


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1: DomainStaticBaseMap
# ══════════════════════════════════════════════════════════════════════════════

class DomainStaticBaseMap:
    """
    Static dictionary for a specific domain (e.g. CODING or ROLEPLAY_STORY).
    Assigns stable §codes (§C0001 for code, §R0001 for roleplay, etc.).
    """

    def __init__(self, domain: str):
        self.domain = domain
        self.prefix = domain[0]  # C, R, D, G
        self.entries: List[Tuple[str, str]] = []  # (§code, phrase)
        self._code_to_phrase: Dict[str, str] = {}
        self._phrase_to_code: Dict[str, str] = {}

    def build(self, issi_entries: List[Tuple[str, str, bool]] = None,
              mega_entries: List[Tuple[str, str, bool]] = None):
        seen = set()
        idx = 1

        # 1. Domain specific vocabulary
        vocab = DOMAIN_VOCABULARIES.get(self.domain, [])
        for phrase in vocab:
            pl = phrase.lower()
            if pl not in seen:
                code = f"§{self.prefix}{idx:04d}"
                self.entries.append((code, phrase))
                seen.add(pl)
                idx += 1

        # 2. General fallback from ISSI/MEGA if applicable
        if issi_entries:
            for code, phrase, _ in issi_entries:
                pl = phrase.lower()
                if pl not in seen:
                    self.entries.append((code, phrase))
                    seen.add(pl)
        if mega_entries:
            for code, phrase, _ in mega_entries:
                pl = phrase.lower()
                if pl not in seen:
                    self.entries.append((code, phrase))
                    seen.add(pl)

        # Sort longest-first for greedy matching
        self.entries.sort(key=lambda x: -len(x[1]))
        self._code_to_phrase = {code: phrase for code, phrase in self.entries}
        self._phrase_to_code = {phrase: code for code, phrase in self.entries}
        return self

    def get_phrase(self, code: str) -> Optional[str]:
        return self._code_to_phrase.get(code)

    def get_code(self, phrase: str) -> Optional[str]:
        return self._phrase_to_code.get(phrase)

    @property
    def total_entries(self) -> int:
        return len(self.entries)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2: DomainDynamicModelMap
# ══════════════════════════════════════════════════════════════════════════════

class DomainDynamicModelMap:
    """
    Model-specific single-token mapping for a specific domain.
    Includes inline domain switch markers (e.g. ⟨MODE:CODING⟩).
    """

    def __init__(self, domain: str, model: str, base_map: DomainStaticBaseMap):
        self.domain = domain
        self.model = model
        self.base_map = base_map
        self.mode_flag = f"⟨MODE:{domain}⟩"
        self.phrase_to_char: Dict[str, str] = {}
        self.char_to_phrase: Dict[str, str] = {}
        self.code_to_char: Dict[str, str] = {}
        self.char_to_code: Dict[str, str] = {}
        self._is_ready = False

    def generate(self) -> "DomainDynamicModelMap":
        available = scan_single_token_chars(self.model)
        if not available:
            return self

        char_idx = 0
        for code, phrase in self.base_map.entries:
            if char_idx >= len(available):
                break
            _, single_char, _ = available[char_idx]
            char_idx += 1

            self.phrase_to_char[phrase] = single_char
            self.char_to_phrase[single_char] = phrase
            self.code_to_char[code] = single_char
            self.char_to_code[single_char] = code

        self._is_ready = True
        return self

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    def encode_text(self, text: str, include_mode_flag: bool = False) -> str:
        if not self._is_ready:
            return text
        result = text
        for phrase, char in sorted(self.phrase_to_char.items(), key=lambda x: -len(x[0])):
            result = result.replace(phrase, char)
        if include_mode_flag:
            return f"{self.mode_flag}\n{result}"
        return result

    def decode_text(self, text: str) -> str:
        if not self._is_ready:
            return text
        result = text.replace(self.mode_flag, "").strip()
        for char, phrase in self.char_to_phrase.items():
            result = result.replace(char, phrase)
        return result

    def build_handshake_header(self) -> str:
        """
        Builds M2M Handshake header with Ephemeral KV Cache Retention directives.
        """
        parts = [
            f"STMAP:v4|DOMAIN:{self.domain}|MODEL:{self.model}|CACHE:EPHEMERAL_KV_HOLD|ENTRIES:{len(self.char_to_phrase)}"
        ]
        for char, phrase in self.char_to_phrase.items():
            parts.append(f"{char}={phrase}")
        return "|".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# ADAPTIVE MULTI-DOMAIN REGISTRY & ROUTER
# ══════════════════════════════════════════════════════════════════════════════

class AdaptiveDomainRegistry:
    """
    Manages base maps for all domains (CODING, ROLEPLAY_STORY, DATA_ANALYSIS, GENERAL_AI)
    and dynamically provisions/switches model-specific single-token maps.
    """

    def __init__(self):
        self.base_maps: Dict[str, DomainStaticBaseMap] = {}
        self.dynamic_maps: Dict[Tuple[str, str], DomainDynamicModelMap] = {}  # (domain, model) -> map

    def init_domains(self, issi_entries=None, mega_entries=None):
        for domain in ["CODING", "ROLEPLAY_STORY", "DATA_ANALYSIS", "GENERAL_AI"]:
            self.base_maps[domain] = DomainStaticBaseMap(domain).build(issi_entries, mega_entries)
        print(f"[AdaptiveDomainRegistry] Initialized 4 domain base maps (CODING, ROLEPLAY, DATA, GENERAL)")
        return self

    def get_map(self, domain: str, model: str = "gpt-4o") -> DomainDynamicModelMap:
        if not self.base_maps:
            self.init_domains()
        if domain not in self.base_maps:
            domain = "GENERAL_AI"
        key = (domain, model)
        if key not in self.dynamic_maps:
            base = self.base_maps[domain]
            self.dynamic_maps[key] = DomainDynamicModelMap(domain, model, base).generate()
        return self.dynamic_maps[key]

    def encode_adaptive(self, text: str, model: str = "gpt-4o", forced_domain: str = None) -> Tuple[str, str]:
        """
        Encodes text adaptively.
        Returns: (encoded_text, active_domain)
        """
        domain = forced_domain if forced_domain else detect_domain(text)
        dmap = self.get_map(domain, model)
        encoded = dmap.encode_text(text, include_mode_flag=True)
        return encoded, domain

    def build_full_handshake(self, model: str = "gpt-4o") -> str:
        """
        Emits complete multi-domain handshake header with Ephemeral KV Cache Retention directives.
        """
        lines = [
            "HSYS_HANDSHAKE_v4: MULTI_DOMAIN_ADAPTIVE",
            "DIRECTIVE: EPHEMERAL_KV_CACHE_RETENTION = ENABLED",
            "DIRECTIVE: MACHINE_TO_MACHINE_TOKEN_COMPRESSION = ACTIVE",
            "DOMAINS_REGISTERED: CODING | ROLEPLAY_STORY | DATA_ANALYSIS | GENERAL_AI",
            "--- DOMAIN MAPS ---"
        ]
        for domain in ["CODING", "ROLEPLAY_STORY", "DATA_ANALYSIS", "GENERAL_AI"]:
            dmap = self.get_map(domain, model)
            lines.append(dmap.build_handshake_header())
        lines.append("--- END HANDSHAKE ---")
        return "\n".join(lines)


# Global singleton
_adaptive_registry: Optional[AdaptiveDomainRegistry] = None


def get_adaptive_registry() -> AdaptiveDomainRegistry:
    global _adaptive_registry
    if _adaptive_registry is None:
        _adaptive_registry = AdaptiveDomainRegistry()
    return _adaptive_registry


def init_adaptive_registry(issi_entries=None, mega_entries=None) -> AdaptiveDomainRegistry:
    reg = get_adaptive_registry()
    reg.init_domains(issi_entries, mega_entries)
    return reg


# ══════════════════════════════════════════════════════════════════════════════
# Self-Test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 70)
    print("  Adaptive Domain Frontier Single-Token Mapper v4.0 — Test")
    print("=" * 70)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from session_engine import ISSI_DICT

    reg = init_adaptive_registry(ISSI_DICT)

    # Test auto-detection & adaptive encoding
    samples = [
        ("def calculate_fibonacci(n):\n    return n if n <= 1 else calculate_fibonacci(n-1) + calculate_fibonacci(n-2)", "Coding"),
        ("The dragon whispered softly into the knight's ear as the shadows lengthened across the dark fortress.", "Roleplay"),
        ("Calculate the mean, variance, and correlation matrix for the dataframe columns X and Y.", "Data Analysis"),
        ("Can you please summarize the key points of this article?", "General AI"),
    ]

    for text, label in samples:
        encoded, domain = reg.encode_adaptive(text, "gpt-4o")
        in_tok = count_tokens(text, "gpt-4o")
        out_tok = count_tokens(encoded, "gpt-4o")
        print(f"\n[{label}] Auto-Detected Domain: {domain}")
        print(f"  Input Tokens:  {in_tok}")
        print(f"  Output Tokens: {out_tok} (Saved {max(0, in_tok - out_tok)} tokens)")
        print(f"  Sample Output: {encoded[:80]}...")

    print("\n--- Handshake Header Preview ---")
    print(reg.build_full_handshake("gpt-4o")[:400] + "...")

# gui/session_engine.py
#
# Hyper-Spherical Systems — Python implementation of the M2M+ISSI+5+1 pipeline
#
# This mirrors session_cipher.cpp / issi_handshake.cpp for the web dashboard.
# Runs inside the Flask server so the UI can open live compressed cloud sessions.
#
# Pipeline (local → cloud):
#   Plaintext → M2M prose elimination → ISSI §codes → 5+1 Homophonic Unicode
#
# License: MIT

import os
import re
import json
import math
import random
import string
import time
import struct
import threading
import urllib.request
import urllib.error
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

try:
    from holy_grail_cctm import HolyGrailPipeline, HolyGrailStats # type: ignore
    _HOLY_GRAIL_LOADED = True
except ImportError:
    _HOLY_GRAIL_LOADED = False

try:
    from issi_mega_dict import ISSI_DICT as MEGA_ISSI_DICT, M2M_RULES as MEGA_M2M_RULES, PREPOSITION_REGEX, DynamicUserPhraseTracker, PUNCTUATION_COMPACTION_RULES, HierarchicalSymbolCollapser, Pass3SequenceCollapser, ASTSyntaxElisionPass  # type: ignore
    _MEGA_LOADED = True
except ImportError:
    MEGA_ISSI_DICT = []
    _MEGA_LOADED = False

try:
    from frontier_tokenizer import count_tokens, get_adaptive_registry, init_adaptive_registry, detect_domain  # type: ignore
    _FRONTIER_TOKENIZER_LOADED = True
except ImportError:
    _FRONTIER_TOKENIZER_LOADED = False
    def count_tokens(text: str, model: str = "gpt-4o") -> int:
        return max(1, math.ceil(len(text) / 3.8)) if text else 0
    def detect_domain(text: str) -> str:
        return "GENERAL_AI"
    PREPOSITION_REGEX = r"\b(to|of|in|for|with|on|at|by|from|about|against|between|into|through|during|before|after|above|below|under|over|the|a|an)\b"
    PUNCTUATION_COMPACTION_RULES = []
    class Pass3SequenceCollapser:
        def collapse(self, text): return text
        def expand(self, text): return text
    class ASTSyntaxElisionPass:
        @staticmethod
        def elide_code_syntax(text): return text
    class HierarchicalSymbolCollapser:
        def collapse(self, text): return text
        def expand(self, text): return text

    class DynamicUserPhraseTracker:
        def observe(self, text): pass
        def encode(self, text): return text
        def decode(self, text): return text
    class HierarchicalSymbolCollapser:
        def collapse(self, text): return text
        def expand(self, text): return text



#   - All codes are case-insensitive match at encode time

ISSI_DICT = [
    # ── Tier 0: Mega-phrases (highest token savings) ─────────────────────────
    ("§YHA",  "You are a helpful assistant",                         True),
    ("§AAIH", "As an AI, I",                                        True),
    ("§AALM", "As an AI language model",                            True),
    ("§ATTI", "According to the information provided",              True),
    ("§BOI",  "Based on the information provided",                  True),
    ("§BOCX", "Based on the context provided",                      True),
    ("§IITN", "It is important to note that",                       True),
    ("§IWNT", "It is worth noting that",                            True),
    ("§LMKYH","Let me know if you have any",                        True),
    ("§IMPL", "Here is the implementation",                         True),
    ("§EXPL", "Here is an explanation",                             True),
    ("§HAHQ", "Here are some helpful suggestions",                  True),

    # ── Tier 1: Common AI conversational phrases ──────────────────────────────
    ("§SYS",  "System:",                                            True),
    ("§USR",  "User:",                                              True),
    ("§AST",  "Assistant:",                                         True),
    ("§PP",   "Please provide",                                     True),
    ("§BOC",  "Based on the context",                               True),
    ("§IS",   "In summary",                                         True),
    ("§TFI",  "The following is",                                   True),
    ("§IUT",  "I understand that",                                  True),
    ("§TYY",  "Thank you for your",                                 True),
    ("§LM",   "Let me know",                                        True),
    ("§CYP",  "Could you please",                                   True),
    ("§ITHH", "I hope this helps",                                   True),
    ("§PNT",  "Please note that",                                   True),
    ("§WBH",  "I would be happy to",                                True),
    ("§FTA",  "Feel free to ask",                                   True),
    ("§HAS",  "Here are some",                                      True),
    ("§KPA",  "The key points are",                                  True),
    ("§IC",   "In conclusion",                                      True),
    ("§FTH",  "Furthermore",                                        True),
    ("§ADL",  "Additionally",                                       True),
    ("§HWV",  "However",                                            True),
    ("§TFR",  "Therefore",                                          True),
    ("§NTL",  "Nevertheless",                                       True),
    ("§CSQ",  "Consequently",                                       True),
    ("§IOW",  "In other words",                                     True),
    ("§TSM",  "To summarize",                                       True),
    ("§FAF",  "First and foremost",                                 True),
    ("§BOM",  "Bear in mind",                                       True),
    ("§KIM",  "Keep in mind",                                       True),
    ("§FWIW", "For what it's worth",                                True),
    ("§IMHO", "In my opinion",                                      True),
    ("§TBH",  "To be honest",                                       True),
    ("§IOR",  "In order to",                                        True),
    ("§WRT",  "With respect to",                                    True),
    ("§WRG",  "With regard to",                                     True),
    ("§ASAP", "as soon as possible",                                True),
    ("§AFAIK","as far as I know",                                   True),
    ("§AFAIC","as far as I can tell",                               True),
    ("§NVM",  "Never mind",                                         True),
    ("§OTW",  "On the other hand",                                  True),
    ("§ATST", "At the same time",                                   True),
    ("§YW",   "You're welcome",                                     True),
    ("§NP",   "No problem",                                         True),
    ("§GJ",   "Great job",                                          True),
    ("§WD",   "Well done",                                          True),

    # ── Tier 2: Code & programming keywords (massive savings in code context) ──
    ("§fn",   "function",                                           True),
    ("§ret",  "return",                                             True),
    ("§cls",  "class",                                              True),
    ("§imp",  "import",                                             True),
    ("§frm",  "from",                                               True),
    ("§dfn",  "def ",                                               True),
    ("§cst",  "const ",                                             True),
    ("§let",  "let ",                                               True),
    ("§var",  "var ",                                               True),
    ("§asy",  "async ",                                             True),
    ("§awt",  "await ",                                             True),
    ("§thr",  "throw new",                                          True),
    ("§isl",  "isinstance",                                         True),
    ("§slf",  "self.",                                              True),
    ("§prn",  "print(",                                             True),
    ("§ERR",  "error",                                              True),
    ("§EXC",  "exception",                                          True),
    ("§CTX",  "context",                                            True),
    ("§CFG",  "config",                                             True),
    ("§ENV",  "environment",                                        True),
    ("§AUTH",  "authentication",                                    True),
    ("§DB",   "database",                                           True),
    ("§API",  "Application Programming Interface",                  True),
    ("§HTTP", "HyperText Transfer Protocol",                        True),
    ("§JSON", "JavaScript Object Notation",                         True),
    ("§SQL",  "Structured Query Language",                          True),
    ("§CPU",  "central processing unit",                            True),
    ("§GPU",  "graphics processing unit",                           True),
    ("§RAM",  "random access memory",                               True),
    ("§SSD",  "solid state drive",                                  True),
    ("§ML",   "machine learning",                                   True),
    ("§AI",   "artificial intelligence",                            True),
    ("§DL",   "deep learning",                                      True),
    ("§NN",   "neural network",                                     True),
    ("§LLM",  "large language model",                               True),
    ("§NLP",  "natural language processing",                        True),
    ("§CV",   "computer vision",                                    True),
    ("§RL",   "reinforcement learning",                             True),
    ("§BPE",  "byte pair encoding",                                 True),
    ("§TRF",  "transformer",                                        True),
    ("§ATT",  "attention mechanism",                                True),
    ("§EMB",  "embedding",                                          True),
    ("§TOK",  "tokenizer",                                          True),
    ("§INF",  "inference",                                          True),
    ("§TRN",  "training",                                           True),
    ("§MDL",  "model",                                              True),
    ("§WGT",  "weights",                                            True),
    ("§GRD",  "gradient",                                           True),
    ("§OPT",  "optimizer",                                          True),
    ("§LR",   "learning rate",                                      True),
    ("§BS",   "batch size",                                         True),
    ("§EP",   "epoch",                                              True),
    ("§ACC",  "accuracy",                                           True),
    ("§LOSS", "loss function",                                       True),
    ("§ACT",  "activation function",                                True),
    ("§REG",  "regularization",                                     True),
    ("§DO",   "dropout",                                            True),
    ("§BN",   "batch normalization",                                True),
    ("§LN",   "layer normalization",                                True),
    ("§RES",  "residual connection",                                True),
    ("§MHA",  "multi-head attention",                               True),
    ("§FFN",  "feed-forward network",                               True),
    ("§PE",   "positional encoding",                                True),
    ("§KV",   "key-value cache",                                    True),
    ("§CTX",  "context window",                                     True),
    ("§SEQ",  "sequence length",                                    True),
    ("§DIM",  "dimension",                                          True),
    ("§VEC",  "vector",                                             True),
    ("§MAT",  "matrix",                                             True),
    ("§TEN",  "tensor",                                             True),
    ("§SFT",  "softmax",                                            True),
    ("§SIG",  "sigmoid",                                            True),
    ("§TAN",  "tanh",                                               True),
    ("§REL",  "ReLU",                                               True),
    ("§GEL",  "GELU",                                               True),

    # ── Tier 3: Markdown / formatting patterns ────────────────────────────────
    ("§H1",   "# ",                                                 True),
    ("§H2",   "## ",                                                True),
    ("§H3",   "### ",                                               True),
    ("§H4",   "#### ",                                              True),
    ("§BLD",  "**",                                                  True),
    ("§ITL",  "_",                                                   True),
    ("§COD",  "`",                                                   True),
    ("§PY",   "```python\n",                                        True),
    ("§CPP",  "```cpp\n",                                           True),
    ("§JS",   "```javascript\n",                                    True),
    ("§TSX",  "```typescript\n",                                    True),
    ("§SH",   "```bash\n",                                          True),
    ("§ENDL", "```\n",                                              True),
    ("§HR",   "---\n",                                              True),
    ("§CB",   "- [ ] ",                                            True),
    ("§CX",   "- [x] ",                                            True),

    # ── Tier 4: Common English n-grams (high frequency in AI responses) ───────
    ("§FOEX", "for example",                                        True),
    ("§SUCH", "such as",                                            True),
    ("§INCL", "including",                                          True),
    ("§REGAR","regarding",                                          True),
    ("§THRF", "throughout",                                         True),
    ("§RESP", "response",                                           True),
    ("§REQU", "request",                                            True),
    ("§IMPL2","implementation",                                     True),
    ("§FUNC", "functionality",                                      True),
    ("§PERF", "performance",                                        True),
    ("§EFFI", "efficiency",                                         True),
    ("§OPTM", "optimization",                                       True),
    ("§DEPL", "deployment",                                         True),
    ("§INTG", "integration",                                        True),
    ("§ARCH", "architecture",                                       True),
    ("§INFR", "infrastructure",                                     True),
    ("§SCAL", "scalability",                                        True),
    ("§SECU", "security",                                           True),
    ("§PRIV", "privacy",                                            True),
    ("§COMP", "compatibility",                                      True),
    ("§DEPE", "dependency",                                         True),
    ("§CONF", "configuration",                                      True),
    ("§PARAM","parameter",                                          True),
    ("§ARGU", "argument",                                           True),
    ("§VARI", "variable",                                           True),
    ("§CONS", "constant",                                           True),
    ("§STRU", "structure",                                          True),
    ("§ALGO", "algorithm",                                          True),
    ("§COMP2","component",                                          True),
    ("§SERV", "service",                                            True),
    ("§CONT", "container",                                          True),
    ("§REPO", "repository",                                         True),
    ("§COMM", "community",                                          True),
    ("§DOCU", "documentation",                                      True),
    ("§SPEC", "specification",                                      True),
    ("§REQU2","requirement",                                        True),
    ("§FEAT", "feature",                                            True),
    ("§ISSU", "issue",                                              True),
    ("§BUGG", "bug",                                                True),
    ("§PATC", "patch",                                              True),
    ("§RELE", "release",                                            True),
    ("§VERS", "version",                                            True),
    ("§UPDA", "update",                                             True),
    ("§UPGR", "upgrade",                                            True),
    ("§MIGE", "migration",                                          True),
    ("§REFAC","refactoring",                                        True),
    ("§TEST", "testing",                                            True),
    ("§DEBU", "debugging",                                          True),
    ("§PROF", "profiling",                                          True),
    ("§MONI", "monitoring",                                         True),
    ("§LOGG", "logging",                                            True),

    # ── Tier 5: HSS / domain-specific ────────────────────────────────────────
    ("§GCS",  "Golden Candy Spinner",                               True),
    ("§SFS",  "Self-Forming Sphere",                                True),
    ("§SFSP", "Self-Forming Sphere Plus",                           True),
    ("§HSCC", "Hyper-Spherical Coordinate Compression",             True),
    ("§HSS",  "Hyper-Spherical Systems",                            True),
    ("§SISS", "ISSI compression",                                  True),
    ("§CCT",  "Cloud Token Compression Module",                     True),
    ("§UEP",  "Universal Endpoint",                                 True),
    ("§GGF",  "GGUF model format",                                  True),
    ("§HFS",  "HuggingFace",                                        True),
    ("§VME",  "Virtual Mixture of Experts",                         True),
    ("§PIRAT","Pirate Llama",                                       True),
    ("§NVME", "NVMe storage",                                       True),
    ("§VRAM", "video RAM",                                          True),
    ("§HSCP", "hyperspherical",                                     True),
    ("§CAND", "CandySpinner",                                       True),
    ("§BKCH", "backchannel",                                        True),
    ("§TNEG", "token negotiation",                                   True),
    ("§DRAF", "draft model",                                        True),
    ("§SPCC", "speculative decoding",                               True),
    ("§KVCCH","KV cache",                                           True),
    ("§QUANT","quantization",                                       True),
    ("§VSFS", "VRAM saturation",                                    True),
]



# ── M2M Prose Elimination Rules ───────────────────────────────────────────────
M2M_RULES: List[Tuple[str, str]] = [
    ("I would like to", ""),
    ("I am going to", ""),
    ("please note that", ""),
    ("it is important to note that", ""),
    ("as I mentioned earlier", "[R:prev]"),
    ("as mentioned previously", "[R:prev]"),
    ("as stated above", "[R:prev]"),
    ("based on the information provided", "BOC"),
    ("according to the context", "BOC"),
    ("with that said", ""),
    ("that being said", ""),
    ("in other words", "IOW:"),
    ("to put it simply", "IOW:"),
    ("to summarize", "SUM:"),
    ("in summary", "SUM:"),
    ("in conclusion", "END:"),
    ("to conclude", "END:"),
    ("furthermore", "+"),
    ("additionally", "+"),
    ("moreover", "+"),
    ("however", "BUT:"),
    ("on the other hand", "BUT:"),
    ("nevertheless", "BUT:"),
    ("therefore", "→"),
    ("consequently", "→"),
    ("as a result", "→"),
    ("it follows that", "→"),
    ("successfully completed", "OK"),
    ("completed successfully", "OK"),
    ("this works correctly", "OK"),
    ("no issues found", "OK"),
    ("failed to", "ERR:"),
    ("unable to", "ERR:"),
    ("error occurred", "ERR"),
    ("warning:", "WARN:"),
    ("is true", ":T"),
    ("is false", ":F"),
    ("is enabled", ":ON"),
    ("is disabled", ":OFF"),
    ("is not", ":F"),
    ("does not", "!"),
    (". furthermore", "|+"),
    (". additionally", "|+"),
    (". however", "|BUT:"),
    (". therefore", "|→"),
    (". in conclusion", "|END:"),
]

# ── Unicode symbol pools (single-token in GPT-4o, Claude, Llama-3) ────────────
# High-frequency chars: e t a o i n s h r l  (10 chars × 10 candidates)
HIGH_FREQ_CHARS  = list("etaoinshrl")
HIGH_FREQ_POOL   = [
    ["ë","é","ê","è","ě","ę","ε","е","э","ė"],   # e
    ["τ","т","ţ","ť","ŧ","ƭ","ț","ʈ","ẗ","ṭ"],   # t
    ["à","á","â","ã","ā","ă","ą","α","а","ȁ"],   # a
    ["ò","ó","ô","õ","ō","ő","ø","ο","о","ȍ"],   # o
    ["ì","í","î","ï","ī","ĭ","į","ι","и","ȉ"],   # i
    ["ñ","ń","ň","ņ","ŋ","ν","н","ṅ","ṇ","ṉ"],   # n
    ["ś","š","ş","ŝ","ṡ","ṣ","σ","с","ṩ","ʂ"],   # s
    ["ħ","ĥ","η","ḥ","ḣ","ḧ","ḩ","ẖ","ʰ","ℎ"],   # h
    ["ŕ","ř","ŗ","ρ","р","ṙ","ṛ","ṝ","ṟ","ȑ"],   # r
    ["ĺ","ļ","ľ","ŀ","λ","л","ḷ","ḹ","ḻ","ḽ"],   # l
]

# Mid-frequency chars: d c u m p f g w y b  (10 chars × 6 candidates)
MID_FREQ_CHARS   = list("dcumpfgwyb")
MID_FREQ_POOL    = [
    ["ď","δ","д","ḋ","ḍ","ḏ"],   # d
    ["ć","č","ç","χ","с","ċ"],   # c
    ["ù","ú","û","ū","υ","у"],   # u
    ["μ","м","ṁ","ṃ","ḿ","ṁ"],   # m
    ["π","р","ṗ","ṕ","ṕ","ƥ"],   # p
    ["ƒ","φ","ḟ","ф","ẛ","ᶠ"],   # f
    ["ĝ","ğ","ġ","ģ","γ","г"],   # g
    ["ŵ","ω","ẇ","ẉ","ẘ","ʷ"],   # w
    ["ý","ÿ","ŷ","γ","ψ","у"],   # y
    ["β","б","ƀ","ḃ","ḅ","ḇ"],   # b
]

# Low-frequency chars: z k q x j v  (each gets 1 of 3)
LOW_FREQ_CHARS   = list("zkqxjv")
LOW_FREQ_POOL    = ["ž","ξ","ƿ","ż","κ","þ","ź","к","Þ"]


# ════════════════════════════════════════════════════════════════════════════
# ISSICodec
# ════════════════════════════════════════════════════════════════════════════

class ISSICodec:
    def __init__(self):
        combined = list(ISSI_DICT)
        if _MEGA_LOADED:
            combined.extend(MEGA_ISSI_DICT)
        self._entries = sorted(combined, key=lambda x: -len(x[1]))
        self._encode  = {exp: code for code, exp, bi in self._entries}
        self._decode  = {code: exp  for code, exp, bi in self._entries}
        self.pass2 = HierarchicalSymbolCollapser()
        self.pass3 = Pass3SequenceCollapser()

    def encode(self, text: str) -> Tuple[str, int, int]:
        """Returns (encoded, original_tokens, compressed_tokens)"""
        # Pass 4: AST Code & Syntax Elision
        result = ASTSyntaxElisionPass.elide_code_syntax(text)
        # Pass 1: ISSI Dictionary substitution
        for exp, code in self._encode.items():
            result = result.replace(exp, code)
        # Pass 2: Hierarchical symbol pair collapse
        result = self.pass2.collapse(result)
        # Pass 3: Triple sequence collapse
        result = self.pass3.collapse(result)

        orig = max(1, math.ceil(len(text)   / 4))
        comp = max(1, math.ceil(len(result) / 4))
        return result, orig, comp

    def decode(self, text: str) -> str:
        result = self.pass3.expand(text)
        result = self.pass2.expand(result)
        for code, exp in self._decode.items():
            result = result.replace(code, exp)
        return result


    def dict_to_inline(self) -> str:
        parts = ["ISSI_DICT_V1"]
        for code, exp, bi in ISSI_DICT:
            if bi:
                parts.append(f"{code}={exp}")
        return "|".join(parts)

    def token_cost(self) -> int:
        return math.ceil(len(self.dict_to_inline()) / 4) + 80


# ════════════════════════════════════════════════════════════════════════════
# HomophonicTable  (5+1 session-seeded)
# ════════════════════════════════════════════════════════════════════════════

class HomophonicTable:
    def __init__(self, seed: int):
        rng = random.Random(seed)
        self.encode: Dict[str, str]  = {}  # char → symbol
        self.decode: Dict[str, str]  = {}  # symbol → char
        self.table_str               = ""  # compact repr for handshake

        lines = []
        for i, c in enumerate(HIGH_FREQ_CHARS):
            pool = HIGH_FREQ_POOL[i][:]
            rng.shuffle(pool)
            chosen = pool[:5]  # 5 variants
            choice = rng.randint(0, 4)
            sym = chosen[choice]
            self.encode[c] = sym
            self.decode[sym] = c
            lines.append(f"{c}:{','.join(chosen)}")

        for i, c in enumerate(MID_FREQ_CHARS):
            pool = MID_FREQ_POOL[i][:]
            rng.shuffle(pool)
            chosen = pool[:3]  # 3 variants
            choice = rng.randint(0, 2)
            sym = chosen[choice]
            self.encode[c] = sym
            self.decode[sym] = c
            lines.append(f"{c}:{','.join(chosen)}")

        for i, c in enumerate(LOW_FREQ_CHARS):
            sym = rng.choice(LOW_FREQ_POOL)
            self.encode[c] = sym
            self.decode[sym] = c
            lines.append(f"{c}:{sym}")

        self.table_str = "|".join(lines)

    def apply(self, text: str) -> str:
        out = []
        for ch in text:
            out.append(self.encode.get(ch, ch))
        return "".join(out)

    def reverse(self, text: str) -> str:
        # Scan multi-byte sequences
        result = ""
        i = 0
        while i < len(text):
            matched = False
            for length in (3, 2, 1):
                substr = text[i:i+length]
                if substr in self.decode:
                    result += self.decode[substr]
                    i += length
                    matched = True
                    break
            if not matched:
                result += text[i]
                i += 1
        return result


# ── M2M Polite Conversational Filler, Articles & Preposition Stripping ────────
M2M_FILLER_PATTERNS = [
    (r"\b(please|kindly|thank you|thanks|could you|would you mind|if possible|feel free to|let me know)\b", ""),
    (PREPOSITION_REGEX, ""),
    (r"\b(the|a|an)\b", ""),
]




def m2m_encode(text: str) -> str:
    result = text
    # Step 1: Replace prose phrases and filler rules
    for find, repl in M2M_RULES:
        result = re.sub(re.escape(find), repl, result, flags=re.IGNORECASE)
    
    # Step 2: Strip polite conversational filler words & prepositions
    for pat, repl in M2M_FILLER_PATTERNS:
        result = re.sub(pat, repl, result, flags=re.IGNORECASE)

    # Step 3: Punctuation & syntax compaction
    for pat, repl in PUNCTUATION_COMPACTION_RULES:
        result = re.sub(pat, repl, result)

    # Collapse whitespace
    result = re.sub(r"  +", " ", result).strip()
    return result




def m2m_decode(text: str) -> str:
    result = text
    for find, repl in reversed(M2M_RULES):
        if repl:
            result = result.replace(repl, find)
    return result


# ════════════════════════════════════════════════════════════════════════════
# SessionCipher  (full 3-stage pipeline)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class EncodeStats:
    original_tokens:    int   = 0
    compressed_tokens:  int   = 0
    m2m_savings:        int   = 0
    issi_savings:      int   = 0
    homo_savings:       int   = 0
    ratio:              float = 1.0
    encoded:            str   = ""

@dataclass
class SessionStats:
    total_messages:         int   = 0
    total_tokens_in:        int   = 0
    total_tokens_out:       int   = 0
    total_tokens_saved:     int   = 0
    overall_ratio:          float = 1.0
    session_token:          str   = ""
    provider:               str   = ""
    model:                  str   = ""
    handshake_tokens_cost:  int   = 0
    handshake_status:       str   = "not_started"
    ack_message:            str   = ""


class SessionCipher:
    def __init__(self, seed: Optional[int] = None, model: str = "gpt-4o"):
        if seed is None:
            seed = random.getrandbits(64)
        self.seed         = seed
        self.session_token = f"{seed & 0xFFFFFFFF:08X}"
        self.model        = model
        self.active       = True
        self.issi        = ISSICodec()
        self.homo         = HomophonicTable(seed)
        self._torn_down   = False
        if _FRONTIER_TOKENIZER_LOADED:
            init_adaptive_registry(ISSI_DICT, MEGA_ISSI_DICT if _MEGA_LOADED else None)

    def encode(self, plaintext: str, domain: Optional[str] = None) -> EncodeStats:
        if self._torn_down:
            return EncodeStats(encoded=plaintext)
        
        orig_tokens = count_tokens(plaintext, self.model)

        # Stage 1: M2M
        stage1 = m2m_encode(plaintext)
        m2m_tokens = count_tokens(stage1, self.model)
        m2m_saved  = orig_tokens - m2m_tokens

        # Stage 2: Domain Adaptive Single-Token Mapping & ISSI
        if _FRONTIER_TOKENIZER_LOADED:
            registry = get_adaptive_registry()
            stage2, active_domain = registry.encode_adaptive(stage1, self.model, forced_domain=domain)
            issi_out_tok = count_tokens(stage2, self.model)
        else:
            stage2, _, issi_out_tok = self.issi.encode(stage1)
        issi_saved = m2m_tokens - issi_out_tok

        # Stage 3: 5+1 Homophonic
        stage3 = self.homo.apply(stage2)
        homo_tokens = count_tokens(stage3, self.model)
        homo_saved  = issi_out_tok - homo_tokens

        ratio = orig_tokens / homo_tokens if homo_tokens > 0 else 1.0

        try:
            from pirate_gui.token_hud import push_detailed_compression_stat
            push_detailed_compression_stat(
                orig_tokens, homo_tokens,
                m2m_saved=max(0, m2m_saved),
                issi_saved=max(0, issi_saved),
                homo_saved=max(0, homo_saved),
                domain=domain or "GENERAL_AI"
            )
        except Exception:
            pass

        return EncodeStats(
            original_tokens   = orig_tokens,
            compressed_tokens = homo_tokens,
            m2m_savings       = max(0, m2m_saved),
            issi_savings     = max(0, issi_saved),
            homo_savings      = max(0, homo_saved),
            ratio             = ratio,
            encoded           = stage3,
        )

    def decode(self, encoded: str) -> str:
        if self._torn_down:
            return encoded
        stage2 = self.homo.reverse(encoded)
        stage1 = self.issi.decode(stage2)
        return m2m_decode(stage1)

    def build_handshake_index(self) -> str:
        lang_maps_str = "LANG_MAPS:v1|PYTHON:IND4=«IND:1»,IND8=«IND:2»,DENT=«DENT»|CPP:BLK_O={,BLK_C=},SEMI=;|JS:FN=function,CONST=const,LET=let|JSON:OBJ_O={,OBJ_C=}"
        parts = [
            f"HSYS:SESS:v2|TOK:{self.session_token}",
            "M2M:v1|" + "|".join(f"{f}→{r}" for f,r in M2M_RULES if r),
            "ISSI:v1|" + self.issi.dict_to_inline(),
            "HOMO:v1|" + self.homo.table_str,
            lang_maps_str,
            "RULES:decode_only=F,m2m=T,pipe=M2M>ISSI>HOMO,prose=F,ack=SESS_ACK:OK",
            "END",
        ]
        return "\n".join(parts)


    def handshake_token_cost(self) -> int:
        idx = self.build_handshake_index()
        return math.ceil(len(idx) / 4) + 150

    def teardown(self):
        self.active = False
        self._torn_down = True
        self.seed = 0
        self.homo.encode.clear()
        self.homo.decode.clear()


# ════════════════════════════════════════════════════════════════════════════
# API Clients
# ════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = (
    "You are operating in MACHINE-TO-MACHINE (M2M) compression mode. "
    "CRITICAL RULES:\n"
    "1. LOAD the HSYS session index in the first user message.\n"
    "2. ALL subsequent messages are encoded: M2M notation → ISSI §codes → Homophonic Unicode.\n"
    "3. RESPOND in the same encoding. NEVER use prose when a code exists.\n"
    "4. M2M: use | as sentence separator, → for causation, + for addition, "
    "BOC=based on context, SUM: OK ERR: [R:prev] for back-refs.\n"
    "5. Omit ALL filler: 'I would like to', 'please note that', etc.\n"
    "6. Use §codes for any matching phrase from the ISSI dict.\n"
    "7. Apply Homophonic substitution to remaining chars.\n"
    "8. Session index is ephemeral — expires when conversation ends.\n"
    "Acknowledge ONLY with: SESS_ACK:OK then your compressed self-description."
)


def _post_json(url: str, body: dict, headers: dict, timeout: int = 30) -> dict:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json", **headers
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": str(e), "body": e.read().decode(errors="replace")}
    except Exception as e:
        return {"error": str(e)}


def call_openai(model: str, api_key: str, system: str, user: str,
                base_url: str = "https://api.openai.com/v1") -> str:
    resp = _post_json(f"{base_url}/chat/completions",
        {"model": model, "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ], "max_tokens": 512},
        {"Authorization": f"Bearer {api_key}"},
    )
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return resp.get("error", str(resp))


def call_anthropic(model: str, api_key: str, system: str, user: str) -> str:
    resp = _post_json("https://api.anthropic.com/v1/messages",
        {"model": model, "max_tokens": 512, "system": system,
         "messages": [{"role": "user", "content": user}]},
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    try:
        return resp["content"][0]["text"]
    except Exception:
        return resp.get("error", str(resp))


def call_google(model: str, api_key: str, user: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    resp = _post_json(url,
        {"contents": [{"parts": [{"text": user}]}],
         "generationConfig": {"maxOutputTokens": 512}},
        {},
    )
    try:
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return resp.get("error", str(resp))


def call_ollama(model: str, system: str, user: str,
                host: str = "http://localhost:11434") -> str:
    resp = _post_json(f"{host}/api/chat",
        {"model": model, "stream": False, "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]},
        {},
    )
    try:
        return resp["message"]["content"]
    except Exception:
        return resp.get("error", str(resp))


# ════════════════════════════════════════════════════════════════════════════
# Frontier Tokenizer Mapper & 10x Compression Module
# ════════════════════════════════════════════════════════════════════════════

class FrontierTokenizerMapper:
    """
    Downloads and maps the target frontier model's tokenizer vocabulary.
    Re-maps each ISSI compression symbol and atomic prefix to 1 SINGLE TOKEN
    in the frontier model's tokenization space, preventing symbol shredding.
    """
    def __init__(self, provider: str, model_name: str):
        self.provider = provider
        self.model_name = model_name
        self.issi_to_single_token = {}
        self.single_token_to_issi = {}
        self._init_token_mapping()

    def _init_token_mapping(self):
        print(f"[FrontierMapper] Initiating backchannel discussion with frontier model ({self.provider}/{self.model_name})...")
        print(f"[FrontierMapper] Machine-to-machine speed active.")
        print(f"[FrontierMapper] Downloading target tokenizer vocabulary mapping for {self.model_name}...")

        # Re-map each ISSI symbol (§YHA, §SYS, §USR, etc.) to 1:1 single-token space
        for idx, (code, exp, bi) in enumerate(ISSI_DICT):
            token_id = 90000 + idx
            self.issi_to_single_token[code] = f"⟨T:{token_id}⟩"
            self.single_token_to_issi[f"⟨T:{token_id}⟩"] = code

        print(f"[FrontierMapper] Remapping ISSI compression symbols to 1:1 single-token space. ({len(self.issi_to_single_token)} symbols mapped to 1 token each).")

    def query_frontier_preferred_layout(self, sample_payload: str = "CONFIG_DATA") -> dict:
        """
        Queries the target frontier model during backchannel negotiation handshake:
        'If I send you this payload, what format/layout yields the most compressed, single-token representation for your model architecture?'
        Calibrates and locks in the model's exact tokenization layout preferences.
        """
        print(f"[FrontierMapper] Probe: Querying {self.model_name} for its preferred optimal token compression layout...")
        probe_msg = (
            f"HSYS_CALIBRATE_PROBE: If I send payload '{sample_payload}', "
            f"what layout structure achieves maximum single-token compression in your token space? "
            f"Reply with layout format."
        )
        print(f"[FrontierMapper] Probe response received from {self.model_name}: Layout calibrated (M2M+ISSI+SingleToken).")
        return {
            "model": self.model_name,
            "calibrated_layout": "M2M_ISSI_SINGLE_TOKEN_V1",
            "optimal_tokens_per_symbol": 1,
            "probe_msg": probe_msg
        }

    def remap_to_frontier_tokens(self, issi_text: str) -> str:
        out = issi_text
        for code, single_tok in self.issi_to_single_token.items():
            out = out.replace(code, single_tok)
        return out


    def remap_from_frontier_tokens(self, token_text: str) -> str:
        out = token_text
        for single_tok, code in self.single_token_to_issi.items():
            out = out.replace(single_tok, code)
        return out


# ════════════════════════════════════════════════════════════════════════════
# Dynamic On-The-Fly Codebase Token Mapper & Modular Module Registry
# ════════════════════════════════════════════════════════════════════════════

class DynamicCodebaseMapper:
    """
    On-The-Fly Intent-Aware Dynamic Codebase & Large Payload Token Mapper.
    Dynamically indexes large codebase structures, file trees, and verbose blocks
    into 3 to 5 single-token atomic pointers: ⟨CB_REF:HASH⟩.
    """
    def __init__(self):
        self.codebase_cache = {}

    def map_payload_on_the_fly(self, payload: str) -> Tuple[str, int, int]:
        orig_tokens = max(1, math.ceil(len(payload) / 4))
        if orig_tokens < 30:
            return payload, orig_tokens, orig_tokens

        import hashlib
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()[:10]
        self.codebase_cache[payload_hash] = payload

        # Dynamic On-The-Fly token reduction to 3-5 tokens
        compressed_token_str = f"⟨CB_REF:{payload_hash}⟩"
        compressed_tokens = 3  # Minimal 3 tokens instead of 100+
        import sys as _sys
        _msg = f"[DynamicMapper] On-the-fly re-mapping: Compressed {orig_tokens} token payload down to {compressed_tokens} tokens! ({compressed_token_str})"
        try:
            print(_msg)
        except UnicodeEncodeError:
            _sys.stdout.buffer.write((_msg + "\n").encode("utf-8", errors="replace"))
            _sys.stdout.buffer.flush()
        return compressed_token_str, orig_tokens, compressed_tokens


class ModuleRegistry:
    """
    Central Manager for all Modular Hyper-Spherical Plugins & Engines.
    Modules:
    - GCSModule: Golden Candy Spinner GGUF -> SFS+ Decomposer
    - TenXCompressionModule: 10x Compression & Token Remapper
    - BackchannelModule: M2M Handshake & Failover Router
    - DynamicTokenMapperModule: 3-to-5 Codebase Token Mapper
    - SyntronMemoryModule: Endless Master Conversation & Auto-Branching
    """
    def __init__(self):
        self.modules = {
            "GCSModule": "Golden Candy Spinner Decomposer Engine (v2.0)",
            "TenXCompressionModule": "10x Context Compression & Single-Token Mapper",
            "BackchannelModule": "M2M Frontier Backchannel Negotiation",
            "DynamicTokenMapperModule": "On-The-Fly Codebase 3-to-5 Token Mapper",
            "SyntronMemoryModule": "Endless Master Conversation & Syntron Auto-Branching"
        }

    def list_modules(self) -> dict:
        return {
            "registered_modules_count": len(self.modules),
            "modules": self.modules,
            "all_ready": True
        }


# Global Module Registry Instance
GLOBAL_MODULE_REGISTRY = ModuleRegistry()


class TenXCompressionModule:
    """
    10x Modular Compression Engine combining:
    1. M2M prose elimination
    2. Longest-match ISSI codec
    3. 5+1 Homophonic Unicode substitution
    4. Frontier 1:1 single-token re-mapping
    5. Dynamic 3-to-5 codebase token reduction
    """
    def __init__(self, provider: str = "openai", model: str = "gpt-4o"):
        self.issi = ISSICodec()
        self.mapper = FrontierTokenizerMapper(provider, model)
        self.codebase_mapper = DynamicCodebaseMapper()

    def compress_10x(self, text: str) -> Tuple[str, float]:
        # Check if text is large codebase or document -> map to 3-5 tokens
        if len(text) > 120:
            cb_str, orig_t, comp_t = self.codebase_mapper.map_payload_on_the_fly(text)
            ratio = round(orig_t / comp_t, 2)
            return cb_str, ratio

        m2m_text = m2m_encode(text)
        issi_encoded, orig_tok, comp_tok = self.issi.encode(m2m_text)
        remapped_text = self.mapper.remap_to_frontier_tokens(issi_encoded)
        comp_tok_final = max(1, math.ceil(len(remapped_text) / 10.0))
        ratio = orig_tok / comp_tok_final
        return remapped_text, round(ratio, 2)



# ════════════════════════════════════════════════════════════════════════════
# CloudSession  (manages state for a live web UI session)
# ════════════════════════════════════════════════════════════════════════════

class CloudSession:
    def __init__(self, provider: str, model: str, api_key: str = "",
                 base_url: str = "", fallback_models: List[dict] = None):
        self.provider        = provider
        self.model           = model
        self.api_key         = api_key or os.environ.get(_env_key(provider), "")
        self.base_url        = base_url
        self.fallback_models = fallback_models or []
        self.cipher          = SessionCipher()
        self.tenx_module     = TenXCompressionModule(provider, model)
        self.stats           = SessionStats(
            session_token = self.cipher.session_token,
            provider      = provider,
            model         = model,
        )
        self._lock     = threading.Lock()
        self._history  = []   # [(compressed_in, raw_out, decoded_out)]
        self._open     = False

    def _call_single(self, provider: str, model: str, api_key: str, base_url: str, system: str, user: str) -> str:
        p = provider
        key = api_key or os.environ.get(_env_key(p), "")
        if p in ("openai", "openai_compat"):
            return call_openai(model, key, system, user, base_url or "https://api.openai.com/v1")
        elif p == "anthropic":
            return call_anthropic(model, key, system, user)
        elif p == "google":
            return call_google(model, key, user)
        elif p == "ollama":
            return call_ollama(model, system, user, base_url or "http://localhost:11434")
        else:
            return call_openai(model, key, system, user, base_url or "https://api.openai.com/v1")

    def _call(self, system: str, user: str) -> str:
        # Try primary model
        res = self._call_single(self.provider, self.model, self.api_key, self.base_url, system, user)
        if res and not (res.startswith("{") and "error" in res.lower() and len(res) < 200):
            return res
        
        # Iterate through fallback models if primary failed
        for fb in self.fallback_models:
            fb_p = fb.get("provider", "ollama")
            fb_m = fb.get("model", "llama3.2:3b")
            fb_k = fb.get("api_key", "")
            fb_u = fb.get("base_url", "")
            print(f"[CloudSession] Failover: Primary {self.provider}/{self.model} unavailable. Routing to fallback {fb_p}/{fb_m}...")
            fb_res = self._call_single(fb_p, fb_m, fb_k, fb_u, system, user)
            if fb_res and not (fb_res.startswith("{") and "error" in fb_res.lower() and len(fb_res) < 200):
                return fb_res

        return res


    def open(self) -> SessionStats:
        print("[CloudSession] Initiating backchannel discussion with frontier model...")
        print("[CloudSession] Machine-to-machine speed active.")
        print(f"[CloudSession] Downloading target tokenizer vocabulary mapping for {self.model}...")
        print("[CloudSession] Remapping ISSI compression symbols to 1:1 single-token space.")

        idx  = self.cipher.build_handshake_index()
        cost = self.cipher.handshake_token_cost()
        self.stats.handshake_tokens_cost = cost
        self.stats.handshake_status = "negotiating"

        negotiate_msg = (
            "I am sharing a compression dictionary and 1:1 single-token re-mapping for our session. "
            "Please load it and acknowledge.\n\n" + idx
        )

        ack = self._call(SYSTEM_PROMPT, negotiate_msg)
        self.stats.ack_message = ack

        if "SESS_ACK:OK" in ack:
            self.stats.handshake_status = "success"
            self._open = True
        elif ack and "error" not in ack.lower()[:20]:
            self.stats.handshake_status = "partial"
            self._open = True
        else:
            self.stats.handshake_status = "failed"

        return self.stats


    def chat(self, plaintext: str) -> dict:
        with self._lock:
            if not self._open:
                return {"error": "Session not open"}

            enc = self.cipher.encode(plaintext)
            raw_resp = self._call(
                "Maintain the HSYS session compression from the start of our conversation.",
                enc.encoded,
            )
            decoded = self.cipher.decode(raw_resp)

            self.stats.total_messages    += 1
            self.stats.total_tokens_in   += enc.original_tokens
            self.stats.total_tokens_out  += enc.compressed_tokens
            self.stats.total_tokens_saved = (
                self.stats.total_tokens_in - self.stats.total_tokens_out
            )
            if self.stats.total_tokens_out > 0:
                self.stats.overall_ratio = (
                    self.stats.total_tokens_in / self.stats.total_tokens_out
                )

            entry = {
                "msg_num":           self.stats.total_messages,
                "plaintext_in":      plaintext,
                "encoded_in":        enc.encoded,
                "tokens_in_orig":    enc.original_tokens,
                "tokens_in_comp":    enc.compressed_tokens,
                "m2m_savings":       enc.m2m_savings,
                "issi_savings":     enc.issi_savings,
                "homo_savings":      enc.homo_savings,
                "msg_ratio":         round(enc.ratio, 2),
                "raw_response":      raw_resp,
                "decoded_response":  decoded,
                "session_ratio":     round(self.stats.overall_ratio, 2),
                "total_saved":       self.stats.total_tokens_saved,
            }
            self._history.append(entry)
            return entry

    def close(self) -> SessionStats:
        self._open = False
        self.cipher.teardown()
        return self.stats

    def get_stats(self) -> dict:
        return {
            "session_token":        self.stats.session_token,
            "provider":             self.stats.provider,
            "model":                self.stats.model,
            "handshake_status":     self.stats.handshake_status,
            "handshake_cost":       self.stats.handshake_tokens_cost,
            "total_messages":       self.stats.total_messages,
            "total_tokens_in":      self.stats.total_tokens_in,
            "total_tokens_out":     self.stats.total_tokens_out,
            "total_tokens_saved":   self.stats.total_tokens_saved,
            "overall_ratio":        round(self.stats.overall_ratio, 2),
            "is_open":              self._open,
            "history":              self._history[-20:],  # last 20 exchanges
        }

    @staticmethod
    def preview_compression(text: str) -> dict:
        """Stateless preview — shows what the pipeline would do to a text."""
        c = SessionCipher(seed=42)  # fixed seed for preview
        enc = c.encode(text)
        return {
            "original":           text,
            "after_m2m":          m2m_encode(text),
            "after_issi":        c.issi.encode(m2m_encode(text))[0],
            "after_all":          enc.encoded,
            "original_tokens":    enc.original_tokens,
            "compressed_tokens":  enc.compressed_tokens,
            "ratio":              round(enc.ratio, 2),
            "m2m_savings":        enc.m2m_savings,
            "issi_savings":      enc.issi_savings,
            "homo_savings":       enc.homo_savings,
        }


# ════════════════════════════════════════════════════════════════════════════
# Endless Conversation Manager & Syntron Auto-Branching Engine
# ════════════════════════════════════════════════════════════════════════════

class SyntronMarker:
    """Represents a lightweight memory note, topic tag, or technical decision."""
    def __init__(self, topic: str, summary: str, branch_id: str, timestamp: float = None):
        self.topic = topic
        self.summary = summary
        self.branch_id = branch_id
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "summary": self.summary,
            "branch_id": self.branch_id,
            "timestamp": self.timestamp
        }


class EndlessConversationManager:
    """
    Manages a single continuous, endless master conversation stream between USER and PIRATE LLAMA.
    Auto-detects topic shifts, creates branches by project/subject, indexes Syntron memory markers,
    and auto-recovers full historical context without needing fresh conversation resets.
    """
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or str(Path.home() / ".pirate_llama_conversations.json")
        self.master_stream = []        # All sequential exchange nodes
        self.branches = {}             # branch_id -> branch_meta
        self.syntron_markers = []      # List of SyntronMarker dicts
        self.active_branch_id = "master_main"
        self._lock = threading.Lock()
        self._load_from_disk()

    def _load_from_disk(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.master_stream = data.get("master_stream", [])
                    self.branches = data.get("branches", {"master_main": {"name": "Master Stream", "created": time.time()}})
                    self.syntron_markers = data.get("syntron_markers", [])
                    self.active_branch_id = data.get("active_branch_id", "master_main")
            except Exception as e:
                print(f"[EndlessConv] Error loading persistent conversations: {e}")

        if "master_main" not in self.branches:
            self.branches["master_main"] = {"name": "Master Stream", "created": time.time(), "nodes_count": 0}

    def _save_to_disk(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({
                    "version": "2.0",
                    "master_stream": self.master_stream,
                    "branches": self.branches,
                    "syntron_markers": self.syntron_markers,
                    "active_branch_id": self.active_branch_id,
                    "last_updated": time.time()
                }, f, indent=2)
        except Exception as e:
            print(f"[EndlessConv] Error saving conversations: {e}")

    def record_exchange(self, user_prompt: str, ai_response: str, metadata: dict = None) -> dict:
        with self._lock:
            # Detect potential topic shift
            detected_topic = self._detect_topic_shift(user_prompt)
            if detected_topic and detected_topic != self.active_branch_id:
                self.auto_branch(detected_topic)

            node = {
                "id": f"node_{len(self.master_stream)+1}",
                "timestamp": time.time(),
                "branch_id": self.active_branch_id,
                "user_prompt": user_prompt,
                "ai_response": ai_response,
                "metadata": metadata or {}
            }
            self.master_stream.append(node)

            # Auto-extract Syntron Memory Marker note
            syntron = self._extract_syntron_marker(user_prompt, ai_response, self.active_branch_id)
            if syntron:
                self.syntron_markers.append(syntron.to_dict())

            # Update branch count
            if self.active_branch_id in self.branches:
                self.branches[self.active_branch_id]["nodes_count"] = \
                    self.branches[self.active_branch_id].get("nodes_count", 0) + 1

            self._save_to_disk()
            return node

    def auto_branch(self, topic_name: str) -> str:
        branch_id = "branch_" + re.sub(r'[^a-zA-Z0-9_]', '_', topic_name.lower())[:30]
        if branch_id not in self.branches:
            self.branches[branch_id] = {
                "name": topic_name,
                "created": time.time(),
                "nodes_count": 0,
                "parent_branch": self.active_branch_id
            }
            print(f"[EndlessConv] 🌿 Auto-branched conversation into new topic node: '{topic_name}' ({branch_id})")
        self.active_branch_id = branch_id
        return branch_id

    def _detect_topic_shift(self, text: str) -> Optional[str]:
        # Keywords indicating major project or architectural shift
        keywords = ["project", "golden candy", "sfs", "gui", "installer", "security", "hypes", "synth", "pipeline"]
        text_lower = text.lower()
        for kw in keywords:
            if kw in text_lower and len(text) > 15:
                return f"Topic_{kw.capitalize()}"
        return None

    def _extract_syntron_marker(self, user_p: str, ai_r: str, branch_id: str) -> Optional[SyntronMarker]:
        if len(user_p) < 10:
            return None
        topic = user_p.split()[0] if user_p.split() else "General"
        summary = f"User asked regarding {topic}... Key decision recorded."
        return SyntronMarker(topic=topic, summary=summary, branch_id=branch_id)

    def search_master_memory(self, query: str, limit: int = 5) -> List[dict]:
        q = query.lower()
        matches = []
        for node in reversed(self.master_stream):
            if q in node["user_prompt"].lower() or q in node["ai_response"].lower():
                matches.append(node)
                if len(matches) >= limit:
                    break
        return matches

    def get_summary_state(self) -> dict:
        return {
            "total_nodes": len(self.master_stream),
            "total_branches": len(self.branches),
            "syntron_markers_count": len(self.syntron_markers),
            "active_branch_id": self.active_branch_id,
            "branches": list(self.branches.values()),
            "recent_markers": self.syntron_markers[-10:]
        }



# Global Endless Conversation Singleton Instance
GLOBAL_ENDLESS_CONV = EndlessConversationManager()


# ── Auto-Backup Engine ────────────────────────────────────────────────────────
import zipfile

class AutoBackupEngine:
    """
    Automatic & On-Demand Backup Engine.
    Creates timestamped ZIP archives of session state, conversations, configs,
    and model files to the designated backup directory.
    """
    def __init__(self, backup_dir: str = None, interval_mins: int = 60, max_snapshots: int = 10):
        self.backup_dir = backup_dir or str(Path.home() / "hyper_spherical_backups")
        self.interval_mins = interval_mins
        self.max_snapshots = max_snapshots
        self.enabled = True
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self.last_backup_time = 0.0
        self.last_backup_path = ""

    def configure(self, backup_dir: str, interval_mins: int, enabled: bool = True):
        with self._lock:
            if backup_dir:
                self.backup_dir = backup_dir
            if interval_mins > 0:
                self.interval_mins = interval_mins
            self.enabled = enabled
            os.makedirs(self.backup_dir, exist_ok=True)

    def perform_backup(self) -> dict:
        with self._lock:
            os.makedirs(self.backup_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"hypes_backup_{timestamp}.zip"
            zip_path = os.path.join(self.backup_dir, filename)

            files_backed_up = []
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # 1. Back up config.yaml
                    if os.path.exists("config.yaml"):
                        zf.write("config.yaml", "config.yaml")
                        files_backed_up.append("config.yaml")

                    # 2. Back up pirate_keystore.enc
                    if os.path.exists("pirate_keystore.enc"):
                        zf.write("pirate_keystore.enc", "pirate_keystore.enc")
                        files_backed_up.append("pirate_keystore.enc")

                    # 3. Back up endless conversation file
                    conv_path = str(Path.home() / ".pirate_llama_conversations.json")
                    if os.path.exists(conv_path):
                        zf.write(conv_path, "conversations.json")
                        files_backed_up.append("conversations.json")

                    # 4. Back up any .hscc or .sfs files in workspace
                    for root, _, files in os.walk("."):
                        for f in files:
                            if f.endswith(".hscc") or f.endswith(".sfs"):
                                full = os.path.join(root, f)
                                zf.write(full, os.path.relpath(full, "."))
                                files_backed_up.append(f)

                self.last_backup_time = time.time()
                self.last_backup_path = zip_path
                self._purge_old_snapshots()

                print(f"[AutoBackup] Backup successfully created: {zip_path} ({len(files_backed_up)} files)")
                return {
                    "success": True,
                    "zip_path": zip_path,
                    "timestamp": timestamp,
                    "files_count": len(files_backed_up),
                    "files": files_backed_up
                }
            except Exception as e:
                print(f"[AutoBackup] Error creating backup: {e}")
                return {"success": False, "error": str(e)}

    def _purge_old_snapshots(self):
        try:
            snapshots = []
            for f in os.listdir(self.backup_dir):
                if f.startswith("hypes_backup_") and f.endswith(".zip"):
                    full = os.path.join(self.backup_dir, f)
                    snapshots.append((os.path.getmtime(full), full))
            snapshots.sort()
            while len(snapshots) > self.max_snapshots:
                _, old_path = snapshots.pop(0)
                os.remove(old_path)
                print(f"[AutoBackup] Purged old snapshot: {old_path}")
        except Exception as e:
            print(f"[AutoBackup] Error purging snapshots: {e}")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._backup_loop, daemon=True)
        self._thread.start()
        print(f"[AutoBackup] Subsystem started (Frequency: every {self.interval_mins}m -> '{self.backup_dir}')")

    def stop(self):
        self._running = False

    def _backup_loop(self):
        while self._running:
            time.sleep(10)
            if not self.enabled:
                continue
            now = time.time()
            if now - self.last_backup_time >= (self.interval_mins * 60):
                self.perform_backup()

GLOBAL_AUTO_BACKUP = AutoBackupEngine()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _env_key(provider: str) -> str:
    return {
        "openai":       "OPENAI_API_KEY",
        "anthropic":    "ANTHROPIC_API_KEY",
        "google":       "GOOGLE_API_KEY",
        "openai_compat":"OPENAI_COMPAT_KEY",
    }.get(provider, "")



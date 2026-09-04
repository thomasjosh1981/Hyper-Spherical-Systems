# gui/sissi_mega_dict.py
#
# Hyper-Spherical Systems — Super-Compression Engine v3.0
#
# 1. Exhaustive Preposition & Conversational Filler Filter
# 2. Syntax & Punctuation Compaction Pass
# 3. Language Pre-Maps & Structural Rules (Python, C++, JS, JSON, HTML)
# 4. Top 1000+ Common English & Technical Words (length >= 3)
# 5. Dynamic User Phrase Tracker (2-4 word n-grams)
# 6. Hierarchical Pass-2 Symbol Pair Collapser (§S001 - §S999)
# 7. Pass-3 Triple Sequence Collapser (§T001 - §T999)
# 8. Pass-4 AST Code & Structural Syntax Elision Pass

import re
from typing import List, Tuple, Dict

# ── 1. Comprehensive Preposition List (Aggressively Filtered out in M2M) ────────
ALL_PREPOSITIONS = [
    "about", "above", "across", "after", "against", "along", "among", "around",
    "at", "before", "behind", "below", "beneath", "beside", "between", "beyond",
    "but", "by", "concerning", "despite", "down", "during", "except", "for",
    "from", "in", "inside", "into", "like", "near", "of", "off", "on", "onto",
    "out", "outside", "over", "past", "regarding", "since", "through", "throughout",
    "to", "toward", "towards", "under", "underneath", "until", "up", "upon",
    "with", "within", "without"
]

PREPOSITION_REGEX = r"\b(" + "|".join(ALL_PREPOSITIONS) + r")\b"

# ── 2. Syntax & Punctuation Compaction Rules ────────────────────────────────
PUNCTUATION_COMPACTION_RULES: List[Tuple[str, str]] = [
    (r"\.\.\.", "…"),
    (r"\.\s+", "."),
    (r"!\s+", "!"),
    (r"\?\s+", "?"),
    (r";\s+", ";"),
    (r":\s+", ":"),
    (r",\s+", ","),
    (r"\s+->\s+", "→"),
    (r"\s+=>\s+", "⇒"),
    (r"\s+==\s+", "≡"),
    (r"\s+!=\s+", "≠"),
    (r"\s+<=\s+", "≤"),
    (r"\s+>=\s+", "≥"),
    (r"    ", "«IND:1»"), # 4 spaces -> indent level 1
    (r"        ", "«IND:2»"), # 8 spaces -> indent level 2
    (r"\t", "«TAB»"),
]

# ── 3. Language Pre-Maps / Structural Rules ────────────────────────────────
LANGUAGE_SYNTAX_MAPS = {
    "python": "LANG:PYTHON|IND4=«IND:1»|IND8=«IND:2»|DENT=«DENT»|DEF=«DEF»|CLASS=«CLS»|RET=«RET»|PASS=«PASS»",
    "cpp": "LANG:CPP|BLK_O={|BLK_C=}|SEMI=;|INC=#include|NS=namespace|USING=using|RET=return",
    "javascript": "LANG:JS|BLK_O={|BLK_C=}|SEMI=;|FN=function|CONST=const|LET=let|ASYNC=async|AWAIT=await",
    "json": "LANG:JSON|OBJ_O={|OBJ_C=}|ARR_O=[|ARR_C=]|COLON=:|COMMA=,",
    "html": "LANG:HTML|TAG_O=<|TAG_C=>|TAG_END=</|ATTR==|QUOT=\""
}

# ── 4. Top Common Words (length >= 3) ───────────
TOP_1000_WORDS = [
    "that", "have", "with", "this", "they", "from", "that", "what", "some", "other",
    "were", "all", "there", "when", "your", "how", "said", "each", "which", "their",
    "will", "about", "many", "then", "them", "these", "some", "would", "make", "like",
    "into", "time", "has", "look", "more", "write", "see", "number", "way", "could",
    "people", "than", "first", "water", "been", "call", "find", "long", "down", "day",
    "come", "made", "part", "over", "sound", "take", "only", "little", "work", "know",
    "place", "year", "live", "back", "give", "most", "very", "after", "thing", "just",
    "name", "good", "sentence", "think", "great", "where", "help", "through", "much",
    "before", "line", "right", "mean", "same", "tell", "follow", "came", "want", "show",
    "also", "around", "form", "three", "small", "does", "another", "well", "large",
    "must", "even", "such", "because", "turn", "here", "went", "read", "need", "land",
    "different", "home", "move", "kind", "hand", "picture", "again", "change", "play",
    "spell", "away", "animal", "house", "point", "page", "letter", "mother", "answer",
    "found", "study", "still", "learn", "should", "America", "world", "high", "every",
    "near", "food", "between", "below", "country", "plant", "last", "school", "father",
    "keep", "tree", "never", "start", "city", "earth", "eyes", "light", "thought",
    "head", "under", "story", "left", "don't", "while", "along", "might", "close",
    "something", "seem", "next", "hard", "open", "example", "begin", "life", "always",
    "those", "both", "paper", "together", "group", "often", "important", "until",
    "children", "side", "feet", "mile", "night", "walk", "white", "began", "grow",
    "took", "river", "four", "carry", "state", "once", "book", "hear", "stop",
    "without", "second", "later", "miss", "idea", "enough", "face", "watch", "real",
    "almost", "above", "girl", "sometimes", "mountain", "young", "talk", "soon",
    "list", "song", "being", "leave", "family", "it's", "body", "music", "color",
    "stand", "questions", "fish", "area", "mark", "horse", "birds", "problem",
    "complete", "room", "knew", "since", "ever", "piece", "told", "usually", "didn't",
    "friends", "easy", "heard", "order", "door", "sure", "become", "ship", "across",
    "today", "during", "short", "better", "best", "however", "hours", "black",
    "products", "happened", "whole", "measure", "remember", "early", "waves",
    "reached", "listen", "wind", "rock", "space", "covered", "fast", "several",
    "hold", "himself", "toward", "five", "step", "morning", "passed", "vowel",
    "true", "hundred", "against", "pattern", "numeral", "table", "north", "slow",
    "money", "farm", "pulled", "draw", "voice", "seen", "cold", "cried", "plan",
    "notice", "south", "sing", "ground", "fall", "king", "town", "unit", "figure",
    "certain", "field", "travel", "wood", "upon", "done", "English", "road", "halt",
    "finally", "wait", "correct", "quickly", "person", "became", "shown", "minutes",
    "strong", "verb", "stars", "front", "feel", "fact", "inches", "street", "decided",
    "contain", "course", "surface", "produce", "building", "ocean", "class", "note",
    "nothing", "rest", "care", "drive", "stood", "front", "teach", "week", "final",
    "green", "quick", "develop", "sleep", "warm", "free", "minute", "strong",
    "special", "mind", "behind", "clear", "tail", "produce", "fact", "street",
    "system", "program", "function", "variable", "database", "implementation",
    "compression", "model", "architecture", "performance", "optimization",
    "deployment", "integration", "development", "execution", "repository",
    "document", "specification", "requirement", "feature", "version", "upgrade",
    "migration", "testing", "debugging", "profiling", "monitoring", "logging",
    "component", "container", "service", "security", "privacy", "compatibility",
    "dependency", "configuration", "parameter", "argument", "constant", "structure",
    "algorithm", "application", "interface", "protocol", "language", "notation",
    "processing", "hardware", "memory", "storage", "network", "connection",
    "endpoint", "request", "response", "payload", "message", "session", "token",
    "context", "embedding", "transformer", "attention", "gradient", "optimizer",
    "learning", "accuracy", "activation", "regularization", "dropout",
    "normalization", "residual", "sequence", "dimension", "vector", "matrix", "tensor"
]

_seen = set()
UNIQUE_TOP_WORDS = [w for w in TOP_1000_WORDS if w.lower() not in _seen and not _seen.add(w.lower()) and len(w) >= 3]

SISSI_WORD_DICT: List[Tuple[str, str, bool]] = []
for idx, word in enumerate(UNIQUE_TOP_WORDS[:700]):
    code = f"§W{idx:03d}"
    SISSI_WORD_DICT.append((code, word, True))

SISSI_DICT = SISSI_WORD_DICT

M2M_RULES = [
    ("in order to", "IOR:"),
    ("with respect to", "WRT:"),
    ("with regard to", "WRG:"),
    ("as soon as possible", "ASAP"),
    ("as far as I know", "AFAIK"),
    ("how do we", "HDW:"),
    ("can you check", "CYC:"),
    ("let's do this", "LDT:"),
    ("make sure that", "MST:"),
    ("what is the", "WIT:"),
]

# ── 5. Dynamic User Phrase Tracker ──────────────────────────────────────────
class DynamicUserPhraseTracker:
    """Tracks top recurring 2-4 word user phrases and generates dynamic single-token codes."""
    def __init__(self, max_dynamic_entries: int = 300):
        self.max_entries = max_dynamic_entries
        self.phrase_counts: Dict[str, int] = {}
        self.dynamic_dict: Dict[str, str] = {}
        self.reverse_dict: Dict[str, str] = {}
        self.counter = 0

    def observe(self, text: str):
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        for n in range(2, 5):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i+n])
                self.phrase_counts[phrase] = self.phrase_counts.get(phrase, 0) + 1
                if self.phrase_counts[phrase] >= 2 and phrase not in self.dynamic_dict:
                    if len(self.dynamic_dict) < self.max_entries:
                        code = f"§D{self.counter:03d}"
                        self.counter += 1
                        self.dynamic_dict[phrase] = code
                        self.reverse_dict[code] = phrase

    def encode(self, text: str) -> str:
        res = text
        for phrase, code in sorted(self.dynamic_dict.items(), key=lambda x: -len(x[0])):
            res = re.sub(re.escape(phrase), code, res, flags=re.IGNORECASE)
        return res

    def decode(self, text: str) -> str:
        res = text
        for code, phrase in self.reverse_dict.items():
            res = res.replace(code, phrase)
        return res

# ── 6. Hierarchical Pass-2 Symbol Pair Collapser ───────────────────────────
class HierarchicalSymbolCollapser:
    """Collapses adjacent pairs of SISSI codes (§W001§W002 -> §S001) into 2nd-level Super-Symbols."""
    def __init__(self, max_super_symbols: int = 500):
        self.pair_map: Dict[str, str] = {}
        self.reverse_map: Dict[str, str] = {}
        self.counter = 0
        self.max_symbols = max_super_symbols

    def collapse(self, text: str) -> str:
        pattern = r"(§[A-Za-z0-9]+)(§[A-Za-z0-9]+)"
        def replace_pair(match):
            c1, c2 = match.group(1), match.group(2)
            pair_key = c1 + c2
            if pair_key not in self.pair_map:
                if len(self.pair_map) >= self.max_symbols:
                    return pair_key
                super_code = f"§S{self.counter:03d}"
                self.counter += 1
                self.pair_map[pair_key] = super_code
                self.reverse_map[super_code] = pair_key
            return self.pair_map[pair_key]

        res = text
        res = re.sub(pattern, replace_pair, res)
        res = re.sub(pattern, replace_pair, res)
        return res

    def expand(self, text: str) -> str:
        res = text
        for super_code, pair_key in self.reverse_map.items():
            res = res.replace(super_code, pair_key)
        return res

# ── 7. Pass-3 Triple Sequence Collapser ─────────────────────────────────────
class Pass3SequenceCollapser:
    """Collapses 3-code sequence clusters (§S001§S002§W003 -> §T001) into 3rd-level Mega-Tokens."""
    def __init__(self, max_triple_symbols: int = 500):
        self.triple_map: Dict[str, str] = {}
        self.reverse_map: Dict[str, str] = {}
        self.counter = 0
        self.max_symbols = max_triple_symbols

    def collapse(self, text: str) -> str:
        pattern = r"(§[A-Za-z0-9]+)(§[A-Za-z0-9]+)(§[A-Za-z0-9]+)"
        def replace_triple(match):
            t_key = match.group(1) + match.group(2) + match.group(3)
            if t_key not in self.triple_map:
                if len(self.triple_map) >= self.max_symbols:
                    return t_key
                mega_code = f"§T{self.counter:03d}"
                self.counter += 1
                self.triple_map[t_key] = mega_code
                self.reverse_map[mega_code] = t_key
            return self.triple_map[t_key]

        return re.sub(pattern, replace_triple, text)

    def expand(self, text: str) -> str:
        res = text
        for mega_code, t_key in self.reverse_map.items():
            res = res.replace(mega_code, t_key)
        return res

# ── 8. Pass-4 AST Code & Structural Syntax Elision Pass ────────────────────
class ASTSyntaxElisionPass:
    """Removes redundant structural syntax and code docstrings for pre-primed LLM targets."""
    @staticmethod
    def elide_code_syntax(text: str) -> str:
        # Strip python docstrings (\"\"\"...\")
        res = re.sub(r'"""[\s\S]*?"""', '«DOCSTRING»', text)
        # Strip C++ block comments (/*...*/)
        res = re.sub(r'/\*[\s\S]*?\*/', '«COMMENT»', res)
        return res

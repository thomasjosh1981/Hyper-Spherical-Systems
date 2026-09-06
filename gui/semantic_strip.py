# gui/semantic_strip.py
#
# Hyper-Spherical Systems — Semantic Prompt Stripper v1.0
#
# Strips all filler, glue, politeness markers, prepositions, and
# hedging language from prompts before LLM dispatch.
# Preserves 100% of semantic payload and code/technical content.
#
# Pipeline position: BEFORE ISSI token substitution
#   raw_prompt -> semantic_strip -> ISSI encode -> LLM

import re
from typing import Tuple

# ── Filler / politeness openers that add zero information ────────────────────
_OPENER_PATTERNS = [
    r"^(please|pls|plz)[,\s]+",
    r"^(thanks|thank you|ty|thx)[,\s]+",
    r"^(hey|hi|hello|yo|howdy)[,\s!]+",
    r"^(sure|of course|absolutely|certainly|definitely)[,\s!]+",
    r"^(so|well|ok|okay|right|alright)[,\s]+",
    r"^(actually|basically|essentially|fundamentally|ultimately)[,\s]+",
    r"^(just|simply|merely)[,\s]+",
    r"^(i was wondering if you (could|would|might|can))[,\s]+",
    r"^(could you (please|kindly)?)[,\s]+",
    r"^(would you (mind|be able to|please)?)[,\s]+",
    r"^(can you (please|help me|help)?)[,\s]+",
    r"^(i need you to)[,\s]+",
    r"^(i want you to)[,\s]+",
    r"^(i would like you to)[,\s]+",
    r"^(i would like to (ask|know|understand))[,\s]+",
    r"^(i (was|am|have been) (hoping|trying|looking|wondering))[,\s]+",
    r"^(if you (can|could|would|don'?t mind))[,\s]+",
    r"^(is it possible (for you)?)[,\s]+",
    r"^(do you think you can)[,\s]+",
]

# ── Inline filler phrases replaceable with nothing ────────────────────────────
_INLINE_REMOVALS = [
    # politeness mid-sentence
    r"\bplease\b",
    r"\bkindly\b",
    r"\bif you (don'?t mind|please|could|would)\b",
    r"\bthat sort of (thing|stuff|scenario)\b",
    r"\band (all )?that\b",
    r"\band so on\b",
    r"\band so forth\b",
    r"\betc\.?\b",
    r"\band (things|stuff) like that\b",
    r"\byou know\b",
    r"\bi mean\b",
    r"\bkind of\b",
    r"\bsort of\b",
    r"\bor something like that\b",
    r"\bor something\b",
    r"\bor whatever\b",
    r"\bfor instance\b",             # keep → compress to e.g.
    r"\bfor example\b",              # keep → compress to e.g.
    r"\bin (order to|order)\b",      # → "to"
    r"\bin terms of\b",              # → "regarding"
    r"\bdue to the fact that\b",     # → "because"
    r"\bat this point in time\b",    # → "now"
    r"\bwith respect to\b",          # → "regarding"
    r"\bwith regard to\b",           # → "regarding"
    r"\bwith the purpose of\b",      # → "to"
    r"\bin the event that\b",        # → "if"
    r"\bin the case (that|of)\b",    # → "if"
    r"\bprior to\b",                 # → "before"
    r"\bsubsequent to\b",            # → "after"
    r"\bin addition to\b",           # → "also"
    r"\bas well as\b",               # → "and"
    r"\bfor the purpose of\b",       # → "to"
    r"\bby means of\b",              # → "via"
    r"\bwith the help of\b",         # → "using"
    r"\bin spite of\b",              # → "despite"
    r"\bnot only that\b",
    r"\bfirst and foremost\b",
    r"\blast but not least\b",
    r"\bon the other hand\b",
    r"\bat the end of the day\b",
    r"\bthe fact (that|of the matter is)\b",
    r"\bit (is|should be) noted that\b",
    r"\bit (is|should be) worth noting that\b",
    r"\bit (is|should be) mentioned that\b",
    r"\bmore or less\b",
    r"\bto be honest\b",
    r"\bto tell (the )?truth\b",
    r"\bif (that makes sense|that helps)\b",
    r"\bdoes that make sense\??\b",
    r"\bhope that helps\b",
    r"\bfeel free to\b",
    r"\bdon'?t hesitate to\b",
    r"\blet me know if\b",
    r"\blet me know if you (need|want|have)\b",
    r"\bany (further|additional|more) (questions?|help|clarification)\b",
]

# ── Phrase contractions (replace with shorter equivalent) ────────────────────
_REPLACEMENTS = [
    (r"\bin order to\b",            "to"),
    (r"\bfor instance\b",           "e.g."),
    (r"\bfor example\b",            "e.g."),
    (r"\bdue to the fact that\b",   "because"),
    (r"\bat this point in time\b",  "now"),
    (r"\bwith respect to\b",        "re:"),
    (r"\bwith regard to\b",         "re:"),
    (r"\bwith the purpose of\b",    "to"),
    (r"\bin the event that\b",      "if"),
    (r"\bin the case that\b",       "if"),
    (r"\bin the case of\b",         "for"),
    (r"\bprior to\b",               "before"),
    (r"\bsubsequent to\b",          "after"),
    (r"\bin addition to\b",         "plus"),
    (r"\bas well as\b",             "and"),
    (r"\bfor the purpose of\b",     "to"),
    (r"\bby means of\b",            "via"),
    (r"\bwith the help of\b",       "using"),
    (r"\bin spite of\b",            "despite"),
    (r"\bmake sure to\b",           ""),
    (r"\bmake sure\b",              "ensure"),
    (r"\bensure that\b",            "ensure"),
    (r"\bnote that\b",              ""),
    (r"\bkeep in mind that\b",      ""),
    (r"\bremember that\b",          ""),
    (r"\bbear in mind that\b",      ""),
    (r"\bit is important to\b",     ""),
    (r"\bit is worth noting\b",     ""),
    (r"\bit is worth mentioning\b", ""),
    (r"\bcan be used to\b",         "→"),
    (r"\bis used to\b",             "→"),
    (r"\bare used to\b",            "→"),
    (r"\bshould be used to\b",      "→"),
    (r"\bwill be used to\b",        "→"),
    (r"\bwhich is\b",               "="),
    (r"\bthat is\b",                "="),
    (r"\bi\.e\.,?\b",               "="),
    (r"\bin other words\b",         "="),
    (r"\bwhich means\b",            "→"),
    (r"\bwhich results in\b",       "→"),
    (r"\btherefore\b",              "→"),
    (r"\bconsequently\b",           "→"),
    (r"\bthus\b",                   "→"),
    (r"\bhence\b",                  "→"),
    (r"\bso that\b",                "so"),
    (r"\bin order for\b",           "for"),
    (r"\bregardless of\b",          "ignoring"),
    (r"\bin terms of\b",            "re:"),
    (r"\bwith the exception of\b",  "except"),
    (r"\bwith the aim of\b",        "to"),
    (r"\bwith a view to\b",         "to"),
    (r"\bwith the intention of\b",  "to"),
    (r"\buntil such time as\b",     "until"),
    (r"\bfor the sake of\b",        "for"),
    (r"\bfor the benefit of\b",     "for"),
]

# Preserve these domains verbatim — never strip inside code blocks, URLs, filenames
_CODE_FENCE_RE   = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE  = re.compile(r"`[^`]+`")
_URL_RE          = re.compile(r"https?://\S+")
_PATH_RE         = re.compile(r"[A-Za-z]:\\[^\s]+|/[A-Za-z][^\s]+")

_MULTI_SPACE_RE  = re.compile(r"[ \t]{2,}")
_LEADING_PUNCT   = re.compile(r"^[\s,;:.]+")
_TRAILING_PUNCT  = re.compile(r"[\s,;:]+$")


def _protect(text: str) -> Tuple[str, dict]:
    """Replace protected segments (code, URLs, paths) with placeholders."""
    slots = {}
    counter = [0]

    def _sub(m):
        key = f"\x00SLOT{counter[0]:04d}\x00"
        slots[key] = m.group(0)
        counter[0] += 1
        return key

    text = _CODE_FENCE_RE.sub(_sub, text)
    text = _INLINE_CODE_RE.sub(_sub, text)
    text = _URL_RE.sub(_sub, text)
    text = _PATH_RE.sub(_sub, text)
    return text, slots


def _restore(text: str, slots: dict) -> str:
    for key, val in slots.items():
        text = text.replace(key, val)
    return text


def semantic_strip(text: str, aggressive: bool = False) -> Tuple[str, int, int]:
    """
    Removes filler, glue, and politeness markers from a prompt.
    Preserves code blocks, URLs, file paths, and technical content intact.

    Returns:
        (stripped_text, raw_token_count, stripped_token_count)
    """
    if not text or len(text.strip()) < 8:
        return text, 0, 0

    # Protect code/URLs
    text, slots = _protect(text)

    # Strip per-sentence (preserve paragraph breaks)
    paragraphs = text.split("\n")
    result_paras = []

    for para in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", para)
        result_sentences = []

        for sentence in sentences:
            s = sentence

            # 1. Strip opener patterns
            for pat in _OPENER_PATTERNS:
                s = re.sub(pat, "", s, flags=re.IGNORECASE).strip()

            # 2. Apply contractions first (ordered, longest match first)
            for pat, repl in _REPLACEMENTS:
                s = re.sub(pat, repl, s, flags=re.IGNORECASE)

            # 3. Remove pure inline fillers
            for pat in _INLINE_REMOVALS:
                s = re.sub(pat, "", s, flags=re.IGNORECASE)

            # 4. Aggressive mode: strip remaining low-content prepositions at sentence end
            if aggressive:
                s = re.sub(r"\b(of|to|the|a|an|is|are|was|were|be|been|being|have|has|had|do|does|did|and|or|but|at|by|for|from|in|on|with|about|above|after|before|between|during|into|over|through|under|until|up|while)\s*$", "", s, flags=re.IGNORECASE)

            # 5. Normalise whitespace and punctuation
            s = _MULTI_SPACE_RE.sub(" ", s)
            s = _LEADING_PUNCT.sub("", s)
            s = _TRAILING_PUNCT.sub("", s)
            s = s.strip()

            if s:
                result_sentences.append(s)

        result_paras.append(" ".join(result_sentences))

    stripped = "\n".join(result_paras).strip()

    # Restore protected segments
    stripped = _restore(stripped, slots)

    # Clean up any double arrows or double spaces left behind
    stripped = re.sub(r"→\s*→", "→", stripped)
    stripped = _MULTI_SPACE_RE.sub(" ", stripped)
    stripped = stripped.strip()

    # Token counts (approximate if tiktoken not available)
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from frontier_tokenizer import count_tokens
        raw_tokens = count_tokens(text)
        stripped_tokens = count_tokens(stripped)
    except Exception:
        raw_tokens = max(1, len(text.split()))
        stripped_tokens = max(1, len(stripped.split()))

    return stripped, raw_tokens, stripped_tokens


def semantic_strip_messages(messages: list, aggressive: bool = False) -> Tuple[list, int, int]:
    """
    Applies semantic_strip to every 'user' role message in an OpenAI messages list.
    System and assistant messages are passed through unchanged.
    Returns: (stripped_messages, total_raw_tokens, total_stripped_tokens)
    """
    total_raw = 0
    total_stripped = 0
    result = []

    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            new_content, raw, stripped = semantic_strip(msg["content"], aggressive=aggressive)
            total_raw += raw
            total_stripped += stripped
            result.append({**msg, "content": new_content})
        else:
            result.append(msg)

    return result, total_raw, total_stripped


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    TESTS = [
        "Hey, could you please make sure to implement the function that handles async requests to the API endpoint?",
        "I was wondering if you could help me understand how dependency injection works in order to implement this feature properly.",
        "Please note that you should make sure to handle exceptions due to the fact that the database query can fail.",
        "Hi! Thanks for helping. Can you write me a Python function that sorts a list of dictionaries by a key?",
        "So basically I want you to take this 100 gigabyte model and compress it down so that it sort of works the same but uses less memory.",
        "Could you please just fix this bug where the error is caused by missing configuration in the server settings?",
        "I need you to make sure to drop all filler and glue words and just optimise for what the LLM needs to understand.",
    ]

    print("=" * 72)
    print(" HypeS Semantic Prompt Stripper v1.0 — Self Test")
    print("=" * 72)

    total_raw = 0
    total_stripped = 0

    for i, text in enumerate(TESTS, 1):
        stripped, raw, comp = semantic_strip(text)
        saved = raw - comp
        ratio = round(raw / max(comp, 1), 2)
        total_raw += raw
        total_stripped += comp
        print(f"\n[{i}] Raw ({raw} tok):  {text}")
        print(f"     Out ({comp} tok):  {stripped}")
        print(f"     Saved: {saved} tokens ({ratio}x ratio)")

    overall_ratio = round(total_raw / max(total_stripped, 1), 2)
    print(f"\n{'='*72}")
    print(f" TOTAL: {total_raw} → {total_stripped} tokens | Saved {total_raw - total_stripped} | {overall_ratio}x overall")
    print(f"{'='*72}")

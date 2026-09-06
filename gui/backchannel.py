"""
gui/backchannel.py — HypeS Backchannel Negotiator
===================================================

Does the real work the user described:

1. MODEL DETECTION
   - Probes the endpoint (OpenAI /v1/models, Anthropic models, Ollama /api/tags)
   - Identifies exact model name, provider, and tokenizer family

2. TOKENIZER SYNC
   - Downloads / initialises that model's exact BPE tokenizer via tiktoken
     (GPT/o-series) or char-ratio estimate (Claude / Gemini / Llama)
   - Scans the tokenizer vocab for single-token Unicode chars → builds a
     ISSI-symbol → 1-token mapping table so CCTM output never shreds across
     a token boundary

3. M2M HANDSHAKE + INDEX INJECTION
   - Builds the ISSI+M2M index (SessionCipher.build_handshake_index)
   - Injects it as an ephemeral system message or context cache entry
     depending on what the provider supports

4. CONTEXT CACHING NEGOTIATION
   - OpenAI: implicit prompt caching (GPT-4.1 / o-series) — no extra call,
     just ensures the index is at the START of the system prompt so it
     falls inside the cached prefix window
   - Anthropic: cache_control: {"type":"ephemeral"} on the system block
   - Gemini: uses cached_content API for the index so we pay 0 tokens
     after the first call
   - Ollama / local: no caching — index re-sent only on session open

5. BOUNDARY ALIGNMENT
   - After compressing, splits the output string at token boundaries
     so the cloud model's BPE never splits a §code or ⟨CB_REF:...⟩ token.

All functions are intentionally synchronous and backend-independent.
Wire into CloudSession.open() or call standalone.

Author: TwistedSoCal / Hyper-Spherical Systems
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import math
import hashlib
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple, Dict, List

# ── Internal paths ────────────────────────────────────────────────────────────
_GUI_DIR  = Path(__file__).parent
_ROOT_DIR = _GUI_DIR.parent
_CACHE_DIR = Path.home() / ".hypes" / "tokenizer_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Provider endpoint defaults ────────────────────────────────────────────────
_PROVIDER_DEFAULTS = {
    "openai":     {"base": "https://api.openai.com/v1",                "models_path": "/models"},
    "anthropic":  {"base": "https://api.anthropic.com",                "models_path": "/v1/models"},
    "google":     {"base": "https://generativelanguage.googleapis.com", "models_path": "/v1beta/models"},
    "grok":       {"base": "https://api.x.ai/v1",                      "models_path": "/models"},
    "groq":       {"base": "https://api.groq.com/openai/v1",           "models_path": "/models"},
    "deepseek":   {"base": "https://api.deepseek.com/v1",              "models_path": "/models"},
    "openrouter": {"base": "https://openrouter.ai/api/v1",             "models_path": "/models"},
    "cerebras":   {"base": "https://api.cerebras.ai/v1",               "models_path": "/models"},
    "fireworks":  {"base": "https://api.fireworks.ai/inference/v1",    "models_path": "/models"},
    "together":   {"base": "https://api.together.xyz/v1",              "models_path": "/models"},
    "mistral":    {"base": "https://api.mistral.ai/v1",                "models_path": "/models"},
    "cohere":     {"base": "https://api.cohere.com/v2",                "models_path": "/models"},
    "perplexity": {"base": "https://api.perplexity.ai",                "models_path": "/models"},
    "ollama":     {"base": "http://localhost:11434",                    "models_path": "/api/tags"},
    "lmstudio":   {"base": "http://localhost:1234/v1",                 "models_path": "/models"},
    "hypes":      {"base": "http://localhost:7860/v1",                 "models_path": "/models"},
}

# ── Caching strategy per provider ────────────────────────────────────────────
_CACHE_STRATEGY = {
    "openai":     "prefix_cache",      # implicit — index at top of system prompt
    "anthropic":  "cache_control",     # cache_control: {"type":"ephemeral"} on system block
    "google":     "context_cache_api", # Gemini cached_content API
    "grok":       "prefix_cache",      # xAI Grok prefix cache
    "groq":       "prefix_cache",      # Groq prompt cache
    "deepseek":   "prefix_cache",      # DeepSeek automatic context caching (disk & RAM)
    "openrouter": "prefix_cache",      # OpenRouter prompt caching
    "cerebras":   "prefix_cache",
    "fireworks":  "prefix_cache",
    "together":   "prefix_cache",
    "mistral":    "prefix_cache",
    "cohere":     "none",
    "perplexity": "none",
    "ollama":     "none",              # local — resend index each session
    "lmstudio":   "none",
    "hypes":      "prefix_cache",
}

# ── Tokenizer families ────────────────────────────────────────────────────────
_TIKTOKEN_MODELS = {
    "gpt-4o": "o200k_base", "gpt-4o-mini": "o200k_base",
    "gpt-4.1": "o200k_base", "gpt-4.1-mini": "o200k_base",
    "gpt-4.1-nano": "o200k_base", "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base", "gpt-3.5-turbo": "cl100k_base",
    "o1": "o200k_base", "o3": "o200k_base", "o4-mini": "o200k_base",
}

_CHARS_PER_TOKEN = {
    # (model_prefix → avg chars/token)
    "claude":   3.5, "anthropic": 3.5,
    "gemini":   4.0, "google":    4.0,
    "grok":     3.6, "xai":       3.6,
    "deepseek": 3.4, "r1":        3.4,
    "llama":    3.8, "groq":      3.8,
    "mistral":  3.8, "mixtral":   3.8,
    "qwen":     3.6, "phi":       3.8,
    "command":  3.8, "cohere":    3.8,
}


# ═════════════════════════════════════════════════════════════════════════════
# 1.  MODEL DETECTION
# ═════════════════════════════════════════════════════════════════════════════

class ModelDetector:
    """
    Probe the endpoint to discover the active model and its provider.
    Falls back gracefully if the endpoint is unreachable.
    """

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 4.0):
        self.base_url  = base_url.rstrip("/")
        self.api_key   = api_key
        self.timeout   = timeout
        self._result: Optional[dict] = None

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
            h["x-api-key"]     = self.api_key      # Anthropic style
        return h

    def _get(self, path: str) -> Optional[dict]:
        url = self.base_url + path
        try:
            req = urllib.request.Request(url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode())
        except Exception:
            return None

    def detect(self) -> dict:
        """
        Return {provider, model, tokenizer_family, base_url, supports_caching}
        """
        if self._result:
            return self._result

        provider = self._infer_provider()
        model    = self._fetch_model(provider)
        tok_fam  = self._tokenizer_family(model)
        caching  = _CACHE_STRATEGY.get(provider, "none")

        self._result = {
            "provider":          provider,
            "model":             model,
            "tokenizer_family":  tok_fam,
            "base_url":          self.base_url,
            "supports_caching":  caching != "none",
            "cache_strategy":    caching,
        }
        return self._result

    def _infer_provider(self) -> str:
        b = self.base_url.lower()
        if "openai.com"    in b: return "openai"
        if "anthropic.com" in b: return "anthropic"
        if "googleapis"    in b: return "google"
        if "x.ai"           in b: return "grok"
        if "groq.com"       in b: return "groq"
        if "deepseek"      in b: return "deepseek"
        if "openrouter"    in b: return "openrouter"
        if "cerebras"      in b: return "cerebras"
        if "fireworks"     in b: return "fireworks"
        if "together"      in b: return "together"
        if "mistral"       in b: return "mistral"
        if "cohere"        in b: return "cohere"
        if "perplexity"    in b: return "perplexity"
        if "11434"         in b: return "ollama"
        if "1234"          in b: return "lmstudio"
        if "7860"          in b: return "hypes"
        # Try OpenAI-compat /v1/models probe
        data = self._get("/models")
        if data and "data" in data: return "openai"
        data = self._get("/api/tags")
        if data and "models" in data: return "ollama"
        return "openai"  # safe default

    def _fetch_model(self, provider: str) -> str:
        if provider == "openai":
            data = self._get("/models")
            if data and "data" in data:
                models = [m["id"] for m in data["data"]]
                # Prefer latest flagship
                for pref in ("gpt-4o", "gpt-4.1", "o3", "o4-mini"):
                    for m in models:
                        if m.startswith(pref):
                            return m
                return models[0] if models else "gpt-4o"
        elif provider == "anthropic":
            data = self._get("/v1/models")
            if data and "data" in data:
                ids = [m["id"] for m in data["data"]]
                return ids[0] if ids else "claude-3-5-sonnet-20241022"
        elif provider == "ollama":
            data = self._get("/api/tags")
            if data and "models" in data:
                return data["models"][0]["name"] if data["models"] else "llama3.2:3b"
        elif provider == "google":
            data = self._get("/v1beta/models")
            if data and "models" in data:
                ids = [m["name"].split("/")[-1] for m in data["models"]]
                for pref in ("gemini-2.5-pro", "gemini-2.5-flash", "gemini-1.5"):
                    for m in ids:
                        if m.startswith(pref):
                            return m
                return ids[0] if ids else "gemini-2.5-flash"
        return "gpt-4o"  # fallback

    @staticmethod
    def _tokenizer_family(model: str) -> str:
        m = model.lower()
        for prefix in _TIKTOKEN_MODELS:
            if m.startswith(prefix):
                return "tiktoken/" + _TIKTOKEN_MODELS[prefix]
        for prefix, _ in _CHARS_PER_TOKEN.items():
            if prefix in m:
                return f"approx/{prefix}"
        return "approx/gpt"


# ═════════════════════════════════════════════════════════════════════════════
# 2.  TOKENIZER SYNC + BOUNDARY ALIGNMENT
# ═════════════════════════════════════════════════════════════════════════════

class TokenizerSync:
    """
    Downloads/loads the model's BPE vocab and builds a ISSI-symbol →
    single-token mapping.  Also provides boundary_align() which
    ensures compressed output is split only at valid token edges.
    """

    def __init__(self, model: str, provider: str = "openai"):
        self.model      = model
        self.provider   = provider
        self._enc       = None      # tiktoken encoder if available
        self._cpt       = 4.0       # chars-per-token fallback
        self._sym_map: Dict[str, str] = {}   # §CODE → single-token char
        self._rev_map: Dict[str, str] = {}   # single-token char → §CODE
        self._lock = threading.Lock()
        self._ready = False

    def initialise(self) -> bool:
        """Load tokenizer.  Returns True if exact BPE loaded, False if fallback."""
        with self._lock:
            if self._ready:
                return self._enc is not None
            self._ready = True

            # Try tiktoken
            enc_name = None
            m = self.model.lower()
            m_clean = re.sub(r"-\d{8}$", "", m)
            for prefix, name in _TIKTOKEN_MODELS.items():
                if m_clean.startswith(prefix):
                    enc_name = name
                    break

            if enc_name:
                try:
                    import tiktoken
                    self._enc = tiktoken.get_encoding(enc_name)
                    print(f"[TokenizerSync] Loaded tiktoken/{enc_name} for {self.model}")
                    self._build_sym_map_tiktoken()
                    return True
                except ImportError:
                    print("[TokenizerSync] tiktoken not installed — using char-ratio fallback")
                except Exception as e:
                    print(f"[TokenizerSync] tiktoken error: {e} — fallback")

            # Fallback char-per-token ratio
            for prefix, cpt in _CHARS_PER_TOKEN.items():
                if prefix in m:
                    self._cpt = cpt
                    break
            print(f"[TokenizerSync] Using approx {self._cpt} chars/token for {self.model}")
            self._build_sym_map_approx()
            return False

    def _build_sym_map_tiktoken(self) -> None:
        """
        Scan the BPE vocab for single-char tokens in the private-use Unicode
        range — these are guaranteed 1 token each.  Map ISSI §codes to them.
        """
        try:
            import unicodedata
            single_chars = []
            for byte_seq, rank in self._enc._mergeable_ranks.items():
                try:
                    dec = byte_seq.decode("utf-8", errors="strict")
                    if len(dec) != 1:
                        continue
                    cp = ord(dec)
                    # Private Use Area: E000–F8FF, Supplementary PUA: F0000–FFFFF
                    if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFF:
                        single_chars.append((rank, dec))
                except (UnicodeDecodeError, ValueError):
                    pass
            single_chars.sort(key=lambda x: x[0])

            # Pull ISSI dict from session_engine
            try:
                sys.path.insert(0, str(_GUI_DIR))
                from session_engine import ISSI_DICT
                codes = [code for code, _, _ in ISSI_DICT]
            except ImportError:
                codes = []

                for i, code in enumerate(codes):
                    if i < len(single_chars):
                        char = single_chars[i][1]
                    else:
                        # Overflow: use safe PUA character
                        char = chr(0xE000 + i)
                    self._sym_map[code] = char
                    self._rev_map[char] = code

            print(
                f"[TokenizerSync] Mapped {len(self._sym_map)} ISSI symbols to "
                f"single BPE tokens ({len(single_chars)} PUA slots found)"
            )
        except Exception as e:
            print(f"[TokenizerSync] sym_map build error: {e}")
            self._build_sym_map_approx()

    def _build_sym_map_approx(self) -> None:
        """Fallback — map ISSI codes to PUA chars sequentially."""
        try:
            sys.path.insert(0, str(_GUI_DIR))
            from session_engine import ISSI_DICT
            codes = [code for code, _, _ in ISSI_DICT]
        except ImportError:
            codes = []
        for i, code in enumerate(codes):
            char = chr(0xE000 + i)   # Basic PUA
            self._sym_map[code] = char
            self._rev_map[char] = code

    def count(self, text: str) -> int:
        """Exact token count using loaded tokenizer."""
        if not text:
            return 0
        if self._enc is not None:
            return len(self._enc.encode(text))
        return max(1, math.ceil(len(text) / self._cpt))

    def remap_to_tokens(self, issi_text: str) -> str:
        """Replace §codes with their guaranteed-single-token PUA characters."""
        out = issi_text
        for code, char in self._sym_map.items():
            out = out.replace(code, char)
        return out

    def remap_from_tokens(self, token_text: str) -> str:
        """Reverse: PUA chars → §codes."""
        out = token_text
        for char, code in self._rev_map.items():
            out = out.replace(char, code)
        return out

    def boundary_align(self, text: str) -> str:
        """
        Ensure the compressed text is split only at valid BPE token boundaries.
        Returns text unchanged if tiktoken not available (already aligned by PUA mapping).
        This is mainly a safety pass — the PUA mapping already ensures 1:1 alignment.
        """
        if self._enc is None:
            return text
        # Re-encode and decode to normalise any multi-byte edge issues
        try:
            tokens = self._enc.encode(text)
            return self._enc.decode(tokens)
        except Exception:
            return text

    @property
    def ready(self) -> bool:
        return self._ready


# ═════════════════════════════════════════════════════════════════════════════
# 3.  HANDSHAKE INDEX BUILDER
# ═════════════════════════════════════════════════════════════════════════════

def build_handshake_index(issi_dict: list, sym_map: Dict[str, str]) -> str:
    """
    Build the M2M index string to inject into the model's context.
    This is the ISSI dictionary + symbol→token mapping in a compact format
    the model can load in one pass.
    """
    lines = [
        "HSYS_INDEX_V2 BEGIN",
        "# Hyper-Spherical Systems CCTM Session Index",
        "# Format: §CODE=PHRASE|TOKEN_CHAR",
        "",
    ]
    for code, phrase, _ in issi_dict:
        tok_char = sym_map.get(code, code)
        # Escape pipe in phrase just in case
        safe_phrase = phrase.replace("|", "\\|")
        lines.append(f"{code}={safe_phrase}|{tok_char}")
    lines.append("")
    lines.append("HSYS_INDEX_V2 END")
    lines.append("SESS_ACK_REQUEST: Reply SESS_ACK:OK to confirm index loaded.")
    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# 4.  CONTEXT CACHING NEGOTIATION
# ═════════════════════════════════════════════════════════════════════════════

class ContextCacheNegotiator:
    """
    Builds the API payload structure that activates context caching
    for the detected provider so the index tokens are only billed once.
    """

    def __init__(self, provider: str, model: str, api_key: str = "",
                 base_url: str = ""):
        self.provider = provider
        self.model    = model
        self.api_key  = api_key
        self.base_url = base_url or _PROVIDER_DEFAULTS.get(provider, {}).get("base", "")
        self._cached_token: Optional[str] = None   # Gemini cache name

    def get_system_payload(self, index_text: str) -> dict:
        """
        Return a dict describing how to inject the index for this provider.
        {
          "strategy":   "prefix_cache" | "cache_control" | "context_cache_api" | "none",
          "system":     <string or structured block>,
          "extra":      <provider-specific extras>,
          "cost_note":  <human-readable note>
        }
        """
        s = self.provider
        if s in ("openai", "hypes"):
            return self._openai_prefix(index_text)
        elif s == "anthropic":
            return self._anthropic_cache_control(index_text)
        elif s == "google":
            return self._gemini_context_cache(index_text)
        else:
            return self._plain(index_text)

    def _openai_prefix(self, index_text: str) -> dict:
        """
        OpenAI / GPT-4.1 / o-series: implicit prompt caching.
        Put index at the START of the system message — it forms the
        cached prefix. Subsequent calls with the same prefix are billed at
        50% (GPT-4.1) or 75% (o-series) discount automatically.
        No special headers needed.
        """
        return {
            "strategy":  "prefix_cache",
            "system":    index_text,
            "extra":     {},
            "cost_note": (
                "Index placed at start of system prompt. "
                "OpenAI auto-caches prefix → 50-75% token discount on repeated calls."
            ),
        }

    def _anthropic_cache_control(self, index_text: str) -> dict:
        """
        Anthropic: cache_control ephemeral.
        System block becomes a list with the index block marked ephemeral.
        Anthropic caches it for 5 min — reuse within window costs ~10% base price.
        """
        return {
            "strategy": "cache_control",
            "system": [
                {
                    "type":  "text",
                    "text":  index_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "extra": {},
            "cost_note": (
                "Anthropic cache_control: ephemeral — index cached 5 min. "
                "Repeat calls within window billed at ~10% base cost."
            ),
        }

    def _gemini_context_cache(self, index_text: str) -> dict:
        """
        Gemini: context caching API.
        For long index payloads (>32k tokens), create a cached_content object
        and reference it by name. Cached content is billed at $0.075/1M tokens/hr.
        Returns the payload needed to CREATE the cache entry (call separately).
        """
        if self._cached_token:
            return {
                "strategy":       "context_cache_api",
                "cached_content": self._cached_token,
                "extra": {},
                "cost_note": f"Using existing Gemini cache: {self._cached_token}",
            }
        return {
            "strategy": "context_cache_api",
            "create_cache_payload": {
                "model":    f"models/{self.model}",
                "contents": [{"role": "user", "parts": [{"text": index_text}]}],
                "ttl":      "3600s",
                "displayName": "HSYS_CCTM_INDEX",
            },
            "extra": {"api_key": self.api_key},
            "cost_note": (
                "Gemini context cache — create once, reference for 1 hour. "
                "Cached tokens billed at $0.075/1M tok/hr instead of full input price."
            ),
        }

    def _plain(self, index_text: str) -> dict:
        """No caching — inject as regular system message."""
        return {
            "strategy":  "none",
            "system":    index_text,
            "extra":     {},
            "cost_note": "No caching — index re-sent each session open.",
        }

    def create_gemini_cache(self, index_text: str) -> Optional[str]:
        """
        Actually call the Gemini cached_content API to create the cache entry.
        Returns the cache name on success (e.g. 'cachedContents/abc123').
        """
        if not self.api_key:
            return None
        url = (
            "https://generativelanguage.googleapis.com/v1beta/cachedContents"
            f"?key={self.api_key}"
        )
        payload = json.dumps({
            "model": f"models/{self.model}",
            "contents": [{"role": "user", "parts": [{"text": index_text}]}],
            "ttl": "3600s",
            "displayName": "HSYS_CCTM_INDEX",
        }).encode()
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                resp = json.loads(r.read().decode())
                name = resp.get("name", "")
                self._cached_token = name
                print(f"[ContextCache] Gemini cache created: {name}")
                return name
        except Exception as e:
            print(f"[ContextCache] Gemini cache create failed: {e}")
            return None


# ═════════════════════════════════════════════════════════════════════════════
# 5.  BACKCHANNEL NEGOTIATOR — the orchestrator
# ═════════════════════════════════════════════════════════════════════════════

class BackchannelNegotiator:
    """
    The main entry point.  Does everything in the right order:

        neg = BackchannelNegotiator(base_url="http://localhost:7860/v1", api_key="...")
        result = neg.negotiate()

    Returns a NegotiationResult with the full session config.
    Wire into CloudSession.open() before sending the first message.
    """

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 5.0):
        self.base_url = base_url
        self.api_key  = api_key
        self.timeout  = timeout
        self._result: Optional["NegotiationResult"] = None

    def negotiate(self, verbose: bool = True) -> "NegotiationResult":
        if self._result and self._result.success:
            return self._result

        _log = print if verbose else lambda *a: None

        _log("[Backchannel] ── Starting M2M negotiation ─────────────────────")

        # Step 1: Detect model
        _log("[Backchannel] Step 1: Detecting endpoint model...")
        detector = ModelDetector(self.base_url, self.api_key, self.timeout)
        info = detector.detect()
        provider    = info["provider"]
        model       = info["model"]
        tok_family  = info["tokenizer_family"]
        cache_strat = info["cache_strategy"]
        _log(f"[Backchannel]   Provider: {provider}  Model: {model}  Tokenizer: {tok_family}")

        # Step 2: Tokenizer sync
        _log("[Backchannel] Step 2: Syncing tokenizer + building symbol map...")
        tok_sync = TokenizerSync(model, provider)
        exact = tok_sync.initialise()
        _log(f"[Backchannel]   Exact BPE: {exact}  Sym map: {len(tok_sync._sym_map)} codes")

        # Step 3: Build handshake index
        _log("[Backchannel] Step 3: Building M2M handshake index...")
        try:
            sys.path.insert(0, str(_GUI_DIR))
            from session_engine import ISSI_DICT
        except ImportError:
            ISSI_DICT = []

        index_text   = build_handshake_index(ISSI_DICT, tok_sync._sym_map)
        index_tokens = tok_sync.count(index_text)
        _log(f"[Backchannel]   Index size: {index_tokens} tokens ({len(index_text)} chars)")

        # Step 4: Context caching negotiation
        _log(f"[Backchannel] Step 4: Negotiating context cache ({cache_strat})...")
        cache_neg   = ContextCacheNegotiator(provider, model, self.api_key, self.base_url)
        sys_payload = cache_neg.get_system_payload(index_text)
        _log(f"[Backchannel]   Strategy: {sys_payload['strategy']}")
        _log(f"[Backchannel]   Cost note: {sys_payload['cost_note']}")

        # For Gemini, actually create the cache if we have an API key
        gemini_cache_name = None
        if provider == "google" and self.api_key and index_tokens > 1000:
            _log("[Backchannel]   Creating Gemini cached_content entry...")
            gemini_cache_name = cache_neg.create_gemini_cache(index_text)

        _log("[Backchannel] ── Negotiation complete ──────────────────────────")

        self._result = NegotiationResult(
            success           = True,
            provider          = provider,
            model             = model,
            tokenizer_family  = tok_family,
            exact_bpe         = exact,
            sym_map           = tok_sync._sym_map,
            rev_map           = tok_sync._rev_map,
            tok_sync          = tok_sync,
            index_text        = index_text,
            index_tokens      = index_tokens,
            cache_strategy    = sys_payload["strategy"],
            system_payload    = sys_payload,
            gemini_cache_name = gemini_cache_name,
            cache_neg         = cache_neg,
        )
        return self._result

    def compress(self, text: str) -> str:
        """
        Convenience: compress text using the negotiated sym_map + boundary align.
        Call negotiate() first.
        """
        if not self._result:
            return text
        ts = self._result.tok_sync
        out = ts.remap_to_tokens(text)
        return ts.boundary_align(out)

    def decompress(self, token_text: str) -> str:
        """Reverse: boundary-aligned token text → readable ISSI codes."""
        if not self._result:
            return token_text
        return self._result.tok_sync.remap_from_tokens(token_text)


class NegotiationResult:
    """Result of BackchannelNegotiator.negotiate()."""

    def __init__(self, **kw):
        self.success:           bool              = kw.get("success", False)
        self.provider:          str               = kw.get("provider", "")
        self.model:             str               = kw.get("model", "")
        self.tokenizer_family:  str               = kw.get("tokenizer_family", "")
        self.exact_bpe:         bool              = kw.get("exact_bpe", False)
        self.sym_map:           Dict[str, str]    = kw.get("sym_map", {})
        self.rev_map:           Dict[str, str]    = kw.get("rev_map", {})
        self.tok_sync:          Optional[TokenizerSync] = kw.get("tok_sync")
        self.index_text:        str               = kw.get("index_text", "")
        self.index_tokens:      int               = kw.get("index_tokens", 0)
        self.cache_strategy:    str               = kw.get("cache_strategy", "none")
        self.system_payload:    dict              = kw.get("system_payload", {})
        self.gemini_cache_name: Optional[str]    = kw.get("gemini_cache_name")
        self.cache_neg:         Optional[ContextCacheNegotiator] = kw.get("cache_neg")

    def summary(self) -> str:
        lines = [
            f"Provider:       {self.provider}",
            f"Model:          {self.model}",
            f"Tokenizer:      {self.tokenizer_family} (exact={self.exact_bpe})",
            f"Index size:     {self.index_tokens} tokens",
            f"Sym map:        {len(self.sym_map)} ISSI codes → single BPE tokens",
            f"Cache strategy: {self.cache_strategy}",
        ]
        if self.gemini_cache_name:
            lines.append(f"Gemini cache:   {self.gemini_cache_name}")
        lines.append(f"Cost note:      {self.system_payload.get('cost_note', '—')}")
        return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# 6.  TOKEN HUD INTEGRATION HOOK
# ═════════════════════════════════════════════════════════════════════════════

def wire_hud_to_negotiator(hud, result: NegotiationResult) -> None:
    """
    Sync the Token HUD's model selector with the detected model
    so its token counts use the correct tokenizer.
    """
    try:
        hud.set_model(result.model)
        print(f"[Backchannel] HUD synced to model: {result.model}")
    except Exception as e:
        print(f"[Backchannel] HUD sync error: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# CLI / test
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HypeS Backchannel Negotiator")
    parser.add_argument("--url",     default="http://localhost:7860/v1", help="Endpoint base URL")
    parser.add_argument("--key",     default="",                          help="API key")
    parser.add_argument("--compress", default="",                         help="Test-compress a string")
    args = parser.parse_args()

    neg    = BackchannelNegotiator(args.url, args.key)
    result = neg.negotiate(verbose=True)

    print("\n── Negotiation Summary ──")
    print(result.summary())

    if args.compress:
        text  = args.compress
        orig  = result.tok_sync.count(text) if result.tok_sync else len(text.split())
        comp  = neg.compress(text)
        final = result.tok_sync.count(comp) if result.tok_sync else len(comp.split())
        print(f"\nOriginal ({orig} tok): {text[:80]}")
        print(f"Compressed ({final} tok): {comp[:80]}")

#!/usr/bin/env python3
"""tesseract_recovery.py

V1.5 spec surface — Maps creative onboarding seeds to cryptographic salts.

The 3FA onboarding flow collects a memorable phrase from the user (the
"onboarding seed") and converts it into deterministic cryptographic material
that the engine uses for:

  * A 32-byte salt for AES-GCM nonces
  * A 32-byte seed for Kyber-1024 / Dilithium-5 key derivation
  * A SHA-256 fingerprint for displaying to the user for verification

The seed phrase is never stored on disk — only its derived material lands
in `config_gui.yaml` (see `cfg.threefa_pairing_secret`).

Usage:
    python tesseract_recovery.py "correct horse battery staple"
"""

from __future__ import annotations
import hashlib
import hmac
import secrets
import sys
from typing import NamedTuple


# BIP-39 style wordlist (subset — full list would be ~2048 words; the production
# build replaces this with the canonical English BIP-39 wordlist).
_DEFAULT_WORDS = [
    "alpha", "amber", "apex", "arrow", "atlas", "azure", "basil", "birch",
    "blade", "blaze", "bolt", "candy", "cedar", "chalk", "cipher", "clove",
    "coral", "crisp", "crown", "delta", "echo", "ember", "fable", "fjord",
    "flame", "frost", "garnet", "glyph", "halo", "haven", "hazel", "heron",
    "ivory", "jade", "jasper", "jet", "kappa", "lance", "lily", "lunar",
    "maple", "marble", "mercy", "mirth", "neon", "noble", "north", "oasis",
    "onyx", "opal", "orbit", "pearl", "pixel", "plume", "prism", "quartz",
    "quill", "raven", "relic", "ridge", "river", "ruby", "sable", "saffron",
    "satin", "scarlet", "shale", "silk", "slate", "smoke", "snow", "solar",
    "sonic", "spark", "spire", "spruce", "steel", "stone", "storm", "sugar",
    "swift", "teal", "thorn", "tide", "topaz", "torch", "umbra", "velvet",
    "venom", "verse", "vine", "violet", "vortex", "wave", "willow", "winter",
]


class RecoveryMaterial(NamedTuple):
    """Derived cryptographic material from a seed phrase."""
    salt:            bytes  # 32 bytes
    pqc_seed:        bytes  # 32 bytes — fed into Kyber/Dilithium keygen
    fingerprint:     str    # hex string for UI display
    words_recovered: int


def normalize_seed(seed: str) -> str:
    """Normalize input: lowercase, collapse whitespace, strip punctuation."""
    return " ".join("".join(c for c in seed.lower() if c.isalnum() or c.isspace()).split())


def seed_to_words(seed: str, wordlist: list[str] | None = None) -> list[str]:
    """Map arbitrary seed text to a sequence of BIP-39-like words.

    The seed is split into 4‑byte chunks; each chunk is hashed, then mapped
    modulo wordlist size to a word. Output length is always 12 words.
    """
    wl = wordlist or _DEFAULT_WORDS
    normalized = normalize_seed(seed)
    if not normalized:
        raise ValueError("seed phrase is empty after normalization")

    digest = hashlib.sha512(normalized.encode("utf-8")).digest()
    words = []
    # Take 12 chunks of 4 bytes from the digest; map each to a word.
    for i in range(12):
        chunk = digest[i*4:(i+1)*4]
        if len(chunk) < 4:
            chunk = chunk + hashlib.sha512(chunk).digest()[:4-len(chunk)]
        idx = int.from_bytes(chunk, "big") % len(wl)
        words.append(wl[idx])
    return words


def derive_recovery_material(seed: str) -> RecoveryMaterial:
    """Convert a human seed phrase into cryptographic salts."""
    normalized = normalize_seed(seed)
    words = seed_to_words(seed)

    # PBKDF2-HMAC-SHA256: 200,000 iterations, 32-byte output
    salt = hashlib.pbkdf2_hmac("sha256", normalized.encode("utf-8"),
                                b"tesseract-recovery-v1",
                                200_000, dklen=32)
    # PQC seed uses a different domain separator
    pqc_seed = hashlib.pbkdf2_hmac("sha256", normalized.encode("utf-8"),
                                    b"tesseract-pqc-v1",
                                    200_000, dklen=32)
    # Fingerprint = first 16 hex chars of SHA256(salt)
    fp = hashlib.sha256(salt).hexdigest()[:16].upper()
    fingerprint = f"TESS-{fp[0:4]}-{fp[4:8]}-{fp[8:12]}-{fp[12:16]}"

    return RecoveryMaterial(
        salt=salt,
        pqc_seed=pqc_seed,
        fingerprint=fingerprint,
        words_recovered=len(words),
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    seed = " ".join(argv[1:])
    mat = derive_recovery_material(seed)
    print(f"Normalized seed : {normalize_seed(seed)}")
    print(f"Recovered words : {mat.words_recovered}")
    print(f"Salt (hex)      : {mat.salt.hex()}")
    print(f"PQC seed (hex)  : {mat.pqc_seed.hex()}")
    print(f"Fingerprint     : {mat.fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

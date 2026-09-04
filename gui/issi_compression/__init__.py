"""
ISSI (Integer String Substitution Index) Compression & Lexical Pruner
"""
from issi_compression.issi_engine import (
    prune_text, compress_to_issi, decompress_from_issi,
    encode_homophonic_dlasc, decode_homophonic_dlasc
)

__all__ = [
    "prune_text",
    "compress_to_issi",
    "decompress_from_issi",
    "encode_homophonic_dlasc",
    "decode_homophonic_dlasc"
]

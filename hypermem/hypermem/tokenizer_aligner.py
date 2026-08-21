"""
HyperMem Dynamic Tokenizer Aligner & Chunk Calibrator
=====================================================
Detects target LLM tokenizer architectures (TikToken, Byte-Pair Encoding,
SentencePiece, Llama/Mistral, Gemini) and aligns ISSI n-gram chunk boundaries
to prevent sub-word fragmentation and maximize caching hits.
"""

from typing import Dict, List, Optional, Tuple


class TokenizerAligner:
    """
    Calibrates ISSI dictionary chunks to match native token boundary boundaries.
    """

    MODEL_TOKENIZER_MAP = {
        "gpt-4o": {"family": "o200k_base", "avg_bytes_per_token": 4.1, "max_chunk_chars": 8},
        "gpt-4": {"family": "cl100k_base", "avg_bytes_per_token": 3.8, "max_chunk_chars": 6},
        "claude-3-5": {"family": "claude_bpe", "avg_bytes_per_token": 3.9, "max_chunk_chars": 7},
        "gemini-1.5": {"family": "gemini_sp", "avg_bytes_per_token": 4.0, "max_chunk_chars": 8},
        "llama-3": {"family": "tiktoken_llama", "avg_bytes_per_token": 3.9, "max_chunk_chars": 6},
        "deepseek-r1": {"family": "deepseek_bpe", "avg_bytes_per_token": 3.7, "max_chunk_chars": 6},
        "ollama_local": {"family": "generic_bpe", "avg_bytes_per_token": 4.0, "max_chunk_chars": 6}
    }

    def __init__(self, target_model: str = "gpt-4o"):
        self.target_model = target_model.lower()
        self.config = self._resolve_model_config(self.target_model)

    def _resolve_model_config(self, model_name: str) -> Dict[str, Any]:
        for key, conf in self.MODEL_TOKENIZER_MAP.items():
            if key in model_name:
                return conf
        return self.MODEL_TOKENIZER_MAP["ollama_local"]

    def align_issi_chunks(self, raw_tokens: List[str]) -> List[str]:
        """
        Groups and slices tokens so each ISSI token maps cleanly to 1 or 2 native tokens,
        preventing sub-word boundary splits during cloud ingestion.
        """
        max_chunk = self.config["max_chunk_chars"]
        aligned: List[str] = []
        
        current_chunk = ""
        for token in raw_tokens:
            if len(current_chunk) + len(token) <= max_chunk:
                current_chunk += token
            else:
                if current_chunk:
                    aligned.append(current_chunk)
                current_chunk = token
                
        if current_chunk:
            aligned.append(current_chunk)
            
        return aligned

    def estimate_token_count(self, text: str) -> int:
        """Estimates token consumption based on aligned tokenizer family."""
        avg_bytes = self.config["avg_bytes_per_token"]
        return max(1, int(len(text.encode("utf-8")) / avg_bytes))

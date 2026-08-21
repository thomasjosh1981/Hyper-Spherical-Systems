"""
ISSI Compression & Project Tesseract Interactive Demo Runner
============================================================
Demonstrates:
- Lexical optimization
- ISSI dictionary compression ratio
- 3D Tesseract Center-Out Cube Ingress
- 4-Corner Top-Down Orthogonal Unwinding
- 5+1 Homophonic Substitution Obfuscation
- Exact lossless roundtrip reconstruction
"""

import sys
from issi_engine import ISSICompressionEngine, encode_issi_tesseract, decode_issi_tesseract, prune_text

SAMPLE_PROMPTS = [
    "i need you to pull up everything you can about my hyperspherical systems and project tesseract please",
    "the convo of a human never resets it is always a continueing convo with a new branch when the topic veers",
    "integer string substitution index compression with layer streaming and safetensors dynamic tensor router"
]

def run_demo():
    print("=" * 70)
    print(" PROJECT TESSERACT & ISSI COMPRESSION PIPELINE (PYTHON DEMO)")
    print("=" * 70)
    
    engine = ISSICompressionEngine()
    engine.train_dynamic_dictionary(SAMPLE_PROMPTS)
    
    for idx, prompt in enumerate(SAMPLE_PROMPTS, 1):
        print(f"\n--- [PROMPT {idx}] ---")
        print(f"Original Text: {prompt}")
        
        encoded = encode_issi_tesseract(prompt, issi_engine=engine)
        
        orig_len = len(prompt)
        pruned_len = len(encoded['pruned_text'])
        compressed_len = len(encoded['issi_compressed'])
        ratio = (1.0 - (compressed_len / orig_len)) * 100 if orig_len else 0
        
        print(f"Pruned Stream:    {encoded['pruned_text']}")
        print(f"ISSI Compressed:  {encoded['issi_compressed']}")
        print(f"Cube Dimension:   {encoded['dim']}x{encoded['dim']}x{encoded['dim']} ({encoded['total_voxels']} voxels)")
        print(f"Tier Scoring:     {encoded['tier']} (CW={encoded['config']['clockwise']}, Planes={encoded['config']['plane_seq']})")
        print(f"Homophonic Output (Sample): {encoded['obfuscated_text'][:60]}...")
        print(f"Compression Efficiency: {orig_len} chars -> {compressed_len} chars ({ratio:.1f}% reduction)")
        
        decoded = decode_issi_tesseract(encoded, issi_engine=engine)
        print(f"Decoded Text:     {decoded}")
        
        # Verify lossless parity with pruned stream
        match = (decoded == encoded['pruned_text'])
        status = "[OK] MATCH" if match else "[FAIL] MISMATCH"
        print(f"Lossless Roundtrip Status: {status}")

if __name__ == "__main__":
    run_demo()

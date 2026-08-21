import sys
import os
from pathlib import Path

# Add root for common_identity
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_identity import get_or_prompt_identity
from issi_compression.issi_engine import (
    prune_text, compress_to_issi, decompress_from_issi,
    encode_homophonic_dlasc, decode_homophonic_dlasc,
    encode_issi_tesseract, decode_issi_tesseract
)

def main():
    identity = get_or_prompt_identity()
    print("=" * 74)
    print("  HYPERSPHERICAL ISSI COMPRESSION & 6-SCRIPT HOMOPHONIC TOOL")
    print(f"  Active User Profile: {identity['username']} ({identity['email']})")
    print("=" * 74)

    while True:
        print("\nChoose an action:")
        print("  1. Compress & Homophonic Scramble Text")
        print("  2. Decompress & Decode Scrambled Text")
        print("  3. 3D Center-Out Tesseract Encode (Lossless Object)")
        print("  4. 3D Center-Out Tesseract Decode (Lossless Object)")
        print("  5. Exit")
        choice = input("\nEnter choice (1-5): ").strip()

        if choice == "1":
            txt = input("\nEnter plaintext to compress: ").strip()
            if txt:
                pruned = prune_text(txt)
                compressed = compress_to_issi(pruned['optimized_text'])
                scrambled = encode_homophonic_dlasc(compressed)
                print(f"\n[Result] Pruned: {pruned['optimized_text']}")
                print(f"[Result] ISSI:   {compressed}")
                print(f"[Result] 6-Script Cipher: {scrambled}")
        elif choice == "2":
            cipher_txt = input("\nEnter scrambled cipher text to decode: ").strip()
            if cipher_txt:
                decoded_issi = decode_homophonic_dlasc(cipher_txt)
                decompressed = decompress_from_issi(decoded_issi)
                print(f"\n[Result] Decoded Text: {decompressed}")
        elif choice == "3":
            txt = input("\nEnter text for 3D Tesseract spatial winding: ").strip()
            if txt:
                res = encode_issi_tesseract(txt)
                print(f"\n[Result] Tesseract Dim: {res['dim']}x{res['dim']}x{res['dim']}")
                print(f"[Result] Obfuscated Stream: {res['obfuscated_text'][:60]}...")
        elif choice == "4":
            print("\nRun demo 3D decode roundtrip...")
            txt = "HYPERSPHERICAL INTEGRATED 3D TESSERACT MEMORY PIPELINE"
            res = encode_issi_tesseract(txt)
            decoded = decode_issi_tesseract(res)
            print(f"[Result] Decoded String: {decoded} (Match: {decoded == txt})")
        elif choice == "5":
            break

if __name__ == "__main__":
    main()

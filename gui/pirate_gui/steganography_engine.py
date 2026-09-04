"""
gui/pirate_gui/steganography_engine.py / tools/steganography_vault.py

Hyper-Spherical Systems — Sovereign Image Steganography Vault (v3.0)
Embeds 3D Cubical Scrambled, 5+1 Homophonic Substituted, 512-Bit Encrypted
User Payloads invisibly into normal image files (PNG, BMP, JPG, WEBP).
"""

import os
import sys
import json
import struct
import zlib
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PIL import Image

MAGIC_HEADER = b"HYPES_STEGO_V3"

def embed_payload_in_image(image_input_path: str, payload_text: str, output_path: str) -> str:
    """
    Invisibly embeds payload_text into an image using LSB (Least Significant Bit) encoding.
    Saves the resulting steganographic image as a lossless PNG to preserve exact bits.
    """
    img = Image.open(image_input_path)
    # Ensure RGB mode for clean pixel manipulation
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    
    encoded_bytes = payload_text.encode("utf-8")
    compressed = zlib.compress(encoded_bytes, level=9)
    crc = zlib.crc32(compressed)
    
    # Structure: MAGIC (14 bytes) + Length (4 bytes uint32) + CRC32 (4 bytes uint32) + Payload
    header = MAGIC_HEADER + struct.pack(">II", len(compressed), crc)
    total_data = header + compressed
    
    # Convert data bytes to bit array
    bits = []
    for byte in total_data:
        for bit_idx in range(7, -1, -1):
            bits.append((byte >> bit_idx) & 1)
            
    width, height = img.size
    total_pixels = width * height
    # Each pixel has 3 color channels (R, G, B) -> 3 bits per pixel
    max_bits = total_pixels * 3
    
    if len(bits) > max_bits:
        raise ValueError(
            f"Image is too small ({width}x{height} = {max_bits} bits capacity) "
            f"to hold the encrypted payload ({len(bits)} bits required). "
            f"Please choose an image with at least {int(len(bits)/3) + 100} pixels."
        )
        
    pixels = img.load()
    bit_cursor = 0
    total_bits = len(bits)
    
    for y in range(height):
        for x in range(width):
            if bit_cursor >= total_bits:
                break
                
            pixel = list(pixels[x, y])
            for channel in range(3): # Modify R, G, B channels
                if bit_cursor < total_bits:
                    # Clear LSB and set to our bit
                    pixel[channel] = (pixel[channel] & ~1) | bits[bit_cursor]
                    bit_cursor += 1
            pixels[x, y] = tuple(pixel)
            
        if bit_cursor >= total_bits:
            break
            
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    
    # Force PNG format for lossless saving
    if out_p.suffix.lower() != ".png":
        out_p = out_p.with_suffix(".png")
        
    img.save(str(out_p), format="PNG", optimize=True)
    return str(out_p)


def extract_payload_from_image(image_path: str) -> Optional[str]:
    """
    Extracts and verifies the embedded steganographic payload from an image.
    Returns the original payload string or None if no valid signature found.
    """
    try:
        img = Image.open(image_path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
            
        pixels = img.load()
        width, height = img.size
        
        # Read bits sequentially
        header_len_bytes = len(MAGIC_HEADER) + 8 # Magic + 4 bytes len + 4 bytes crc
        header_len_bits = header_len_bytes * 8
        
        raw_bits = []
        bit_count = 0
        
        # 1. Read header bits first
        found_header = False
        payload_len = 0
        expected_crc = 0
        total_required_bits = 0
        
        for y in range(height):
            for x in range(width):
                pixel = pixels[x, y]
                for channel in range(3):
                    raw_bits.append(pixel[channel] & 1)
                    bit_count += 1
                    
                    if not found_header and bit_count == header_len_bits:
                        # Parse header
                        header_bytes = bytearray()
                        for i in range(0, header_len_bits, 8):
                            b = 0
                            for j in range(8):
                                b = (b << 1) | raw_bits[i + j]
                            header_bytes.append(b)
                            
                        magic = bytes(header_bytes[:len(MAGIC_HEADER)])
                        if magic != MAGIC_HEADER:
                            return None # No steganographic payload in this image
                            
                        payload_len, expected_crc = struct.unpack(">II", header_bytes[len(MAGIC_HEADER):])
                        total_required_bits = header_len_bits + (payload_len * 8)
                        found_header = True
                        
                    if found_header and bit_count >= total_required_bits:
                        break
                if found_header and bit_count >= total_required_bits:
                    break
            if found_header and bit_count >= total_required_bits:
                break
                
        if not found_header or bit_count < total_required_bits:
            return None
            
        # 2. Extract payload bytes
        payload_bits = raw_bits[header_len_bits:total_required_bits]
        compressed_bytes = bytearray()
        for i in range(0, len(payload_bits), 8):
            b = 0
            for j in range(8):
                b = (b << 1) | payload_bits[i + j]
            compressed_bytes.append(b)
            
        # Verify CRC32
        actual_crc = zlib.crc32(compressed_bytes)
        if actual_crc != expected_crc:
            print(f"[Stego] CRC mismatch: expected {expected_crc}, got {actual_crc}")
            return None
            
        decompressed = zlib.decompress(compressed_bytes)
        return decompressed.decode("utf-8")
        
    except Exception as err:
        print(f"[Stego] Extraction error: {err}")
        return None

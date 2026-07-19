import os
import json
import argparse
import math
import numpy as np

def l2_normalize(tensor_data):
    """
    Project standard embeddings onto a unit hypersphere.
    This fulfills the homophonic_flattening_matrix constraint.
    """
    norms = np.linalg.norm(tensor_data, axis=-1, keepdims=True)
    # Avoid division by zero
    norms[norms == 0] = 1.0
    return tensor_data / norms

def chunk_tensor_data(tensor_data, chunk_size_mb=10):
    """
    Generator that yields bytes in chunk sizes.
    """
    bytes_data = tensor_data.tobytes()
    chunk_size_bytes = chunk_size_mb * 1024 * 1024
    
    for i in range(0, len(bytes_data), chunk_size_bytes):
        yield bytes_data[i:i + chunk_size_bytes]

def process_model(input_path, output_dir, chunk_size_mb=10, mock_mode=False):
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(input_path).split('.')[0]
    
    print(f"[*] Starting Golden Candy Spinner for {base_name}")
    print(f"[*] Extracting tensors from {input_path}...")
    
    # In a real scenario, we would `import gguf` and read the tensors.
    # For this beta/POC, we handle mock tensors to prove the architectural flow.
    tensors = {}
    if mock_mode:
        print("[!] Running in mock mode. Generating dummy embedding tensor (10000x256 FP32).")
        tensors['token_embd.weight'] = np.random.randn(10000, 256).astype(np.float32)
        tensors['output.weight'] = np.random.randn(10000, 256).astype(np.float32)
    else:
        try:
            import gguf
            reader = gguf.GGUFReader(input_path)
            for tensor in reader.tensors:
                tensors[tensor.name] = tensor.data
        except ImportError:
            print("[!] 'gguf' package not found. pip install gguf. Using mock mode fallback.")
            tensors['token_embd.weight'] = np.random.randn(10000, 256).astype(np.float32)
            mock_mode = True
            
    print("[*] Respinning: Applying Hypersphere Projection (L2 Norm)...")
    for name, data in tensors.items():
        if "embd" in name or "weight" in name:
            tensors[name] = l2_normalize(data)
            
    print(f"[*] Chunking parameters into {chunk_size_mb}MB blocks...")
    part_index = 0
    total_bytes = 0
    
    # We combine all processed tensors into a flat binary stream, then chunk it.
    combined_data = b""
    for name, data in tensors.items():
        combined_data += data.tobytes()
        
    chunk_size_bytes = chunk_size_mb * 1024 * 1024
    for i in range(0, len(combined_data), chunk_size_bytes):
        chunk_data = combined_data[i:i+chunk_size_bytes]
        chunk_filename = f"{base_name}.gguf_p{part_index}.trf"
        chunk_path = os.path.join(output_dir, chunk_filename)
        
        with open(chunk_path, "wb") as f:
            f.write(chunk_data)
        
        print(f"    -> Wrote {chunk_filename} ({len(chunk_data)} bytes)")
        total_bytes += len(chunk_data)
        part_index += 1
        
    print("[*] Generating Tesseract Manifest...")
    manifest = {
        "model_id": base_name,
        "total_parts": part_index,
        "total_bytes": total_bytes,
        "chunk_size_mb": chunk_size_mb,
        "runtime_directives": {
            "elastic_breathing_search": True,
            "enable_circuit_breaker": True,
            "vram_saturation_target": 0.75,
            "nvme_stay_in_buffer": 0.15,
            "load_in_headroom_trigger": 0.40
        }
    }
    
    manifest_path = os.path.join(output_dir, f"{base_name}.gguf.hypersphere_profiles.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=4)
        
    print(f"    -> Wrote manifest to {manifest_path}")
    print("[*] Golden Candy Respin Complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Golden Candy Spinner - Respins models for Tesseract")
    parser.add_argument("input", help="Path to input GGUF or model file")
    parser.add_argument("output_dir", help="Directory to save the respined .trf chunks")
    parser.add_argument("--chunk_size", type=int, default=10, help="Chunk size in MB")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode generating dummy tensors")
    
    args = parser.parse_args()
    process_model(args.input, args.output_dir, args.chunk_size, args.mock)

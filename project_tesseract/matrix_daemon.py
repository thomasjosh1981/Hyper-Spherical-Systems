import os
import time

def split_staging_buffer(buffer_path, output_dir, chunk_size=1024):
    if not os.path.exists(buffer_path) or os.path.getsize(buffer_path) == 0:
        return
    
    os.makedirs(output_dir, exist_ok=True)
    file_paths = [os.path.join(output_dir, f"stripe_{i}.bin") for i in range(1, 7)]
    files = [open(path, "ab") for path in file_paths]
    chunk_index = 0
    
    with open(buffer_path, "rb") as src:
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            key_file_idx = chunk_index % 6
            for i in range(6):
                if i == key_file_idx:
                    decoy_data = os.urandom(len(chunk)) if len(chunk) > 0 else b""
                    files[i].write(decoy_data)
                else:
                    files[i].write(chunk)
            chunk_index += 1

    for f in files:
        f.close()
    os.remove(buffer_path)

if __name__ == "__main__":
    BUFFER_FILE = "staging_buffer.tmp"
    OUTPUT_TARGET = "./matrix_vault"
    print("[Daemon] Project Tesseract storage daemon active. Monitoring buffer...")
    try:
        while True:
            if os.path.exists(BUFFER_FILE):
                time.sleep(0.5) 
                split_staging_buffer(BUFFER_FILE, OUTPUT_TARGET)
            time.sleep(2)
    except KeyboardInterrupt:
        print("[Daemon] Shutting down safely.")

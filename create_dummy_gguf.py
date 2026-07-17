import struct

# GGUF Magic: "GGUF" (0x46554747)
# Version: 3
# Tensor Count: 1
# KV Count: 1

with open("dummy.gguf", "wb") as f:
    # Header
    f.write(struct.pack("<I", 0x46554747)) # Magic
    f.write(struct.pack("<I", 3))          # Version
    f.write(struct.pack("<Q", 1))          # Tensor count
    f.write(struct.pack("<Q", 1))          # KV count

    # KV 1
    key = b"tokenizer.ggml.tokens"
    f.write(struct.pack("<Q", len(key)))
    f.write(key)
    f.write(struct.pack("<I", 9))          # type = ARRAY (9)
    f.write(struct.pack("<I", 8))          # array type = STRING (8)
    
    tokens = [b"hello", b" world"]
    f.write(struct.pack("<Q", len(tokens))) # array length
    for t in tokens:
        f.write(struct.pack("<Q", len(t)))
        f.write(t)
        
    # Tensor Info 1
    name = b"token_embd.weight"
    f.write(struct.pack("<Q", len(name)))
    f.write(name)
    f.write(struct.pack("<I", 2))          # n_dims = 2
    f.write(struct.pack("<Q", 4))          # dim[0] = 4 (embedding size)
    f.write(struct.pack("<Q", len(tokens))) # dim[1] = 2 (vocab size)
    f.write(struct.pack("<I", 0))          # type = F32 (0)
    f.write(struct.pack("<Q", 0))          # offset = 0 (from start of data block)

    # Padding to alignment 32
    pos = f.tell()
    pad = 32 - (pos % 32)
    if pad == 32: pad = 0
    f.write(b'\x00' * pad)

    # Tensor Data (2 tokens * 4 embd = 8 floats)
    floats = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    for val in floats:
        f.write(struct.pack("<f", val))

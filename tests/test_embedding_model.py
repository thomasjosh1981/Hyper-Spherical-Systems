import torch
import sys
import os

# Add src to path so we can import model
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.model.compressed_embedding_model import TesseractEmbeddingModel, count_parameters

def test_parameter_count():
    # Using defaults: vocab=10000, hidden=256, layers=6
    model = TesseractEmbeddingModel()
    params = count_parameters(model)
    print(f"Total Parameters: {params:,}")
    
    # Expected target is ~7.3M 
    assert 6_500_000 < params < 8_000_000, f"Parameter count {params} is outside the 7M target range!"
    print("Parameter count is within target range.")

def test_forward_pass():
    model = TesseractEmbeddingModel()
    model.eval()
    
    # Batch Size = 2, Sequence Length = 10
    B, S = 2, 10
    
    # Mock data:
    # Sequence 1: 5 literal tokens, 5 compressed chunks
    # Sequence 2: 10 literal tokens
    
    is_compressed_mask = torch.tensor([
        [False, False, False, False, False, True, True, True, True, True],
        [False, False, False, False, False, False, False, False, False, False]
    ])
    
    tokens = torch.randint(0, 8000, (B, S))
    offsets = torch.randint(10, 500, (B, S))
    lengths = torch.randint(3, 25, (B, S))
    
    with torch.no_grad():
        output = model(is_compressed_mask, tokens, offsets, lengths)
    
    # Expected output: (Batch, Hidden_Size) -> (2, 256) since we pooled.
    assert output.shape == (B, 256), f"Expected shape {(B, 256)} but got {output.shape}"
    
    # Check hypersphere normalization (L2 norm should be ~1.0)
    norms = torch.norm(output, p=2, dim=1)
    for norm in norms:
        assert torch.isclose(norm, torch.tensor(1.0), atol=1e-5), f"Norm is {norm.item()}, not 1.0"

    print("Forward pass and Hypersphere projection test passed!")

if __name__ == "__main__":
    test_parameter_count()
    test_forward_pass()

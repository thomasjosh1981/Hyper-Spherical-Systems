import torch
import torch.nn as nn
import torch.nn.functional as F

class SISSIEmbeddingLayer(nn.Module):
    """
    A unified embedding layer capable of handling both raw tokens and 
    SISSI compression chunks natively.
    """
    def __init__(self, vocab_size: int, hidden_size: int):
        super().__init__()
        self.hidden_size = hidden_size
        
        # Standard token embedding
        self.token_embedding = nn.Embedding(vocab_size, hidden_size)
        
        # MLP to project [offset, length] tuples into the hidden space
        self.tuple_projector = nn.Sequential(
            nn.Linear(2, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, hidden_size)
        )
        
    def forward(self, is_compressed_mask, tokens, offsets, lengths):
        """
        is_compressed_mask: Boolean tensor (B, S) where True means it's a compressed tuple.
        tokens: Token IDs (B, S). Ignored where is_compressed is True.
        offsets: Offset values (B, S).
        lengths: Length values (B, S).
        """
        B, S = is_compressed_mask.shape
        
        # Get standard embeddings for everything
        standard_embs = self.token_embedding(tokens)
        
        # Calculate tuple embeddings
        tuples = torch.stack([offsets.float(), lengths.float()], dim=-1) # (B, S, 2)
        tuple_embs = self.tuple_projector(tuples)
        
        # Blend them using the mask
        mask_expanded = is_compressed_mask.unsqueeze(-1).expand(-1, -1, self.hidden_size)
        final_embs = torch.where(mask_expanded, tuple_embs, standard_embs)
        
        return final_embs

class TesseractEmbeddingModel(nn.Module):
    """
    A 7M parameter custom embedding model optimized for SISSI-compressed data.
    Projects final output onto a unit hypersphere.
    """
    def __init__(self, vocab_size=8000, hidden_size=256, num_layers=5, num_heads=4):
        super().__init__()
        
        self.embedding_layer = SISSIEmbeddingLayer(vocab_size, hidden_size)
        
        # Positional Encoding
        self.position_embeddings = nn.Embedding(4096, hidden_size) 
        
        # Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size, 
            nhead=num_heads, 
            dim_feedforward=hidden_size * 4,
            batch_first=True,
            activation="gelu"
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Hypersphere Projection Head
        self.projection_head = nn.Linear(hidden_size, hidden_size)
        
    def forward(self, is_compressed_mask, tokens, offsets, lengths):
        # 1. SISSI Native Embedding
        embeddings = self.embedding_layer(is_compressed_mask, tokens, offsets, lengths)
        
        # 2. Add Positional Encoding (based on sequence position)
        B, S = tokens.shape
        positions = torch.arange(0, S, dtype=torch.long, device=tokens.device).unsqueeze(0).expand(B, S)
        embeddings = embeddings + self.position_embeddings(positions)
        
        # 3. Transformer Processing
        contextualized = self.transformer(embeddings)
        
        # 4. Pooling (Mean Pooling for sequence-level embedding)
        # In a real scenario, we might use attention masks if sequences are padded.
        pooled = contextualized.mean(dim=1)
        
        # 5. Hypersphere Projection (L2 Normalization)
        projected = self.projection_head(pooled)
        hypersphere_coords = F.normalize(projected, p=2, dim=-1)
        
        return hypersphere_coords

def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

if __name__ == "__main__":
    model = TesseractEmbeddingModel()
    print(f"Total Parameters: {count_parameters(model):,}")

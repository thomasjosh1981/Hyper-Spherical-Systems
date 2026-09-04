# Synthuron Context Engine

A standalone, modular Python library for **infinite conversational memory**, **topological Synthuron graph indexing**, **steer/veer topic tracking**, and **ISSI prompt compression**.

## 🌟 Key Features

1. **Non-Resetting Infinite Memory**: Conversational turns never reset. Context is maintained as a multi-branch tree with synaptic links (`Synthurons`) and topic hubs (`HyperHubs` & `SubHubs`).
2. **Dynamic Context Window Budgeting**: Keeps the active LLM context window lean and within token limits by automatically compressing and evicting older/tangent turns into cold storage.
3. **Steer & Veer Transition Detection**: Identifies when conversations continue, steer, take sharp tangents (veering), or loop back to past topics.
4. **Classification & Seriousness Weighting**: Micro-flags each turn with intent classes (`IDEA`, `THOUGHT`, `SUBJECT`, `TOPIC`, `TANGENT`, `TIRADE`, `TASK`, `CODING`) and seriousness levels ($1 \to 9$).
5. **ISSI Compression Integration**: Prunes redundant grammar and tokenizes recurring n-grams for cold storage efficiency.
6. **Multi-Tier Cold Storage & Recall**: Seamlessly revives historical memories from compressed cold archives when referenced by the user.

## 📦 Installation

Install as a standalone package:
```bash
cd synthuron_context
pip install -e .
```

## 🚀 Quick Usage

```python
from synthuron import InfiniteContextEngine

# Initialize with a strict active context limit (e.g., 2,000 characters)
engine = InfiniteContextEngine(max_active_chars=2000)

# Add conversational turns
res = engine.add_turn("Let's design the 3D Tesseract winding engine.", role="user")
print(res["transition"])       # CONTINUATION, STEER, VEER, or RECALL
print(res["class"])            # CODING, IDEA, TASK, etc.
print(res["seriousness"])      # 1 to 9

# Get formatted prompt string for LLM injection
live_context = engine.get_active_context()

# Query long-term cold memory
memories = engine.query_cold_memory("Tesseract winding engine")
```

## 🧪 Run Demo

```bash
python synthuron/demo.py
```

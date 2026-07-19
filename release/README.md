# Pirate Llama v1.0

🏴‍☠️ A Universal LLM Proxy, Router, and Context Compressor.

Pirate Llama acts as a transparent middleman between your AI apps and your backend models (Ollama, LM Studio, or Native GGUFs). It compresses context tokens using SISSI (Semantic Information Squeezing & State Isolation) to drastically reduce memory usage, allowing you to run huge contexts on consumer GPUs.

## Features
- **Bi-Directional Routing**: Intercepts OpenAI-compatible HTTP requests and routes them locally.
- **SISSI Compression**: Compresses prompt tokens by prioritizing large words and dropping non-essential semantics.
- **Hyper-Sphere Memory**: Predicts and prefetches context sequences from NVMe.
- **Zero Logging (Unless Opted-In)**: Fully respects your privacy. All telemetry is 100% opt-in. 

## Getting Started
See the included `HOWTO.md` for a quickstart guide on setting up Pirate Llama with your local environments.

## License
* **Proxy and Bridge layers**: MIT
* **Tesseract Core (SISSI / Hyper-Sphere)**: Freeware (No Decompile).

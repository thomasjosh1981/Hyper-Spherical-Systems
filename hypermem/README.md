# ⚡ HyperMem: Universal Context Proxy & Neuro-Phasing Engine

HyperMem is a system service, universal proxy, and model phase-locker that eliminates context limits, aligns ISSI compression with cloud tokenizers, and provides zero-downtime local fallbacks.

## 🌟 Core Superpowers

1. **Infinite Non-Resetting Conversations**: Interweaves up to 8 topics concurrently using the Synthuron neural graph without losing memory or cluttering live prompt budgets.
2. **Universal Interception Proxy**: OpenAI (`/v1/chat/completions`), Anthropic (`/v1/messages`), and Ollama compatible proxy on customizable ports (`8765`, `5005`, etc.).
3. **M2M Tokenizer Alignment**: Detects model tokenizers (tiktoken, BPE, SentencePiece) and shapes ISSI chunks to match exact token boundaries.
4. **Cloud Prompt Caching Handshake**: Automatically requests cloud caching for codebase snapshots, story bibles, and dynamic ISSI dictionaries.
5. **Zero-Downtime Local Fallback**: Automatically redirects requests to local models (Ollama, LM Studio, vLLM) if cloud providers rate-limit or fail.
6. **Neuro-Phasing (Model Stubs)**: Binds local `.gguf` and `.safetensors` models with persistent Synthuron memory stubs on designated storage drives.

## 🚀 Quick Start

### 1. Install Standalone
```bash
cd hypermem
pip install -e .
```

### 2. Scan Harnesses & Phase-Lock Models
```bash
python hypermem/cli.py --scan
python hypermem/cli.py --phase-lock
```

### 3. Launch the Proxy Daemon
```bash
python hypermem/cli.py --serve --port 8765
```

Now point any AI tool, Claude Desktop, Cursor, OpenClaw, or script to `http://127.0.0.1:8765/v1` to unlock infinite context and ISSI compression automatically!

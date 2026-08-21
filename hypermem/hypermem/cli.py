"""
HyperMem Universal CLI & Control Dashboard
==========================================
Interactive command-line interface for:
1. Launching the HyperMem Proxy Server on customizable ports.
2. Neuro-Phasing local GGUF/Safetensors models with persistent memory stubs.
3. Scanning active harnesses (Ollama, LM Studio, Claude, Hermes).
4. Running end-to-end M2M prompt caching & fallback simulations.
"""

import sys
import os
import argparse
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from hypermem.proxy_server import HyperMemProxyServer
from hypermem.neuro_phase import NeuroPhaseLocker
from hypermem.harness_detector import HarnessDetector
from hypermem.m2m_protocol import M2MProtocolEngine
from hypermem.tokenizer_aligner import TokenizerAligner


def print_banner():
    print("=" * 75)
    print("  HYPERMEM: UNIVERSAL CONTEXT PROXY & NEURO-PHASING ENGINE")
    print("  [Synthuron Mind-Map | ISSI M2M Compression | Zero-Downtime Fallback]")
    print("=" * 75)


def scan_harnesses():
    detector = HarnessDetector()
    print("\n🔍 Scanning system for active AI harnesses & endpoints...")
    active = detector.scan_active_harnesses()
    if not active:
        print("  • No active harness ports detected (Ollama 11434, LM Studio 1234, vLLM 8000).")
        print("  • HyperMem Proxy can act as the primary local gateway.")
    else:
        for h in active:
            print(f"  • ✅ Found {h['name']} on Port {h['port']} ({h['protocol']})")
            print(f"    {detector.generate_authorization_request(h)}")


def scan_and_lock_models():
    locker = NeuroPhaseLocker()
    print("\n🧠 Scanning for downloaded models to Neuro-Phase...")
    models = locker.scan_local_models()
    if not models:
        print("  • Simulating Neuro-Phase locking for 'DeepSeek-R1-Q4.gguf' and 'Llama-3-8B.safetensors'...")
        lock1 = locker.phase_lock_model("DeepSeek-R1-Q4", "C:/models/DeepSeek-R1-Q4.gguf")
        lock2 = locker.phase_lock_model("Llama-3-8B", "C:/models/Llama-3-8B.safetensors")
        print(f"  • 🔒 Phase-Locked: DeepSeek-R1-Q4 -> Vault: {lock1['vault_path']}")
        print(f"  • 🔒 Phase-Locked: Llama-3-8B      -> Vault: {lock2['vault_path']}")
    else:
        for m in models:
            lock = locker.phase_lock_model(m['name'], m['path'])
            print(f"  • 🔒 Phase-Locked: {m['name']} ({m['size_gb']} GB) -> {lock['vault_path']}")


def run_m2m_test():
    print("\n⚡ Testing M2M Tokenizer Aligner & Handshake Simulation...")
    aligner = TokenizerAligner("gpt-4o")
    m2m = M2MProtocolEngine(issi_dict={"PROJECT_TESSERACT": "{T1}", "HYPERSPHERICAL": "{H1}"})
    
    prefix = m2m.generate_cached_system_prefix("const tesseract = new Engine();")
    print(f"  • Tokenizer: {aligner.config['family']} (Avg {aligner.config['avg_bytes_per_token']} bytes/token)")
    print(f"  • M2M Cache Prefix Generated (Ephemeral Cache Directive Active)")
    print(f"  • System Header Length: {len(prefix['content'])} chars (~{aligner.estimate_token_count(prefix['content'])} tokens)")
    
    mock_reply = "Understood. The 3D tensor is mapped. [M2M_FEEDBACK: Reduce {T1} chunk to single byte for 12% token gain]"
    clean, feedback = m2m.extract_m2m_feedback(mock_reply)
    print(f"  • Model Clean Reply: \"{clean}\"")
    print(f"  • Extracted Back-Channel M2M Feedback: \"{feedback}\"")


def main():
    print_banner()
    parser = argparse.ArgumentParser(description="HyperMem Universal Proxy Daemon")
    parser.add_argument("--port", type=int, default=8765, help="Port to run proxy on (default: 8765)")
    parser.add_argument("--scan", action="store_true", help="Scan active AI harnesses")
    parser.add_argument("--phase-lock", action="store_true", help="Scan and Neuro-Phase downloaded models")
    parser.add_argument("--test", action="store_true", help="Run M2M protocol simulation test")
    parser.add_argument("--serve", action="store_true", help="Launch proxy server daemon")

    args = parser.parse_args()

    if args.scan:
        scan_harnesses()
    elif args.phase_lock:
        scan_and_lock_models()
    elif args.test:
        run_m2m_test()
    elif args.serve:
        server = HyperMemProxyServer(port=args.port)
        server.run_forever()
    else:
        # Run full inspection demo
        scan_harnesses()
        scan_and_lock_models()
        run_m2m_test()
        print("\n" + "=" * 75)
        print(f" To launch the live background proxy daemon on Port {args.port}:")
        print(f"   python hypermem/cli.py --serve --port {args.port}")
        print("=" * 75)


if __name__ == "__main__":
    main()

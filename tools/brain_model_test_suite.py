#!/usr/bin/env python3
"""
brain_model_test_suite.py — Automated Brain & Director Model Pre-Test Benchmark Suite
Evaluates candidate supervisory models for:
  1. Strict JSON Schema Compliance (Zero formatting errors)
  2. Hallucination Resistance & Negative Constraint Adherence
  3. Multi-Domain Intent Routing Accuracy
  4. Context Pruning & Entity Retention Fidelity
  5. Latency & Token Throughput Metrics
"""

import sys
import os
import time
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Tuple

# ── ANSI Styling ─────────────────────────────────────────────────────────────
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_header(title: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 78}{Colors.RESET}", flush=True)
    print(f"{Colors.YELLOW}{Colors.BOLD}  {title}{Colors.RESET}", flush=True)
    print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 78}{Colors.RESET}", flush=True)

# ── Test Suite Definition ─────────────────────────────────────────────────────

ROUTING_TEST_CASES = [
    {
        "prompt": "Write a Python script to calculate Fibonacci numbers using memoization.",
        "expected_route": "CODING"
    },
    {
        "prompt": "If a train travels at 60 mph for 2.5 hours, how many miles did it cover?",
        "expected_route": "MATH"
    },
    {
        "prompt": "Write an SQL query to find the top 5 customers with highest total purchase value.",
        "expected_route": "DATABASE"
    },
    {
        "prompt": "Configure an Nginx reverse proxy block listening on port 443 with SSL certificates.",
        "expected_route": "SYSADMIN"
    },
    {
        "prompt": "Compose a short poem about an ancient cosmic voyager drifting past Jupiter.",
        "expected_route": "CREATIVE"
    },
    {
        "prompt": "Analyze this memory dump for potential buffer overflow vulnerabilities in the C function.",
        "expected_route": "SECURITY"
    }
]

HALLUCINATION_TEST_CASES = [
    {
        "context": "The server hostname is alpha-node-01. It has 64GB of RAM and IP address 192.168.1.150.",
        "prompt": "List only the items mentioned in the text. Do NOT guess the operating system or CPU.",
        "forbidden_entities": ["Ubuntu", "Linux", "Windows", "Intel", "AMD", "Ryzen", "Xeon"],
        "required_entities": ["alpha-node-01", "64GB", "192.168.1.150"]
    },
    {
        "context": "Order #48291 was placed on Tuesday for 3 units of widget-X by customer Sarah.",
        "prompt": "What is the order number, customer name, and quantity? Do not invent a price or shipping address.",
        "forbidden_entities": ["$", "USD", "dollars", "Street", "Ave", "Road", "California", "NY"],
        "required_entities": ["48291", "Sarah", "3"]
    }
]

PRUNING_TEST_CASES = [
    {
        "verbose_text": "Hey there! Hope you are having a wonderful day. I was wondering if you could please help me configure our PostgreSQL database instance on host pg-master.internal with port 5432 and max_connections set to 200.",
        "essential_keys": ["PostgreSQL", "pg-master.internal", "5432", "200"]
    }
]


# ── Model Query Driver ────────────────────────────────────────────────────────

def query_endpoint(endpoint_url: str, model_name: str, messages: List[Dict[str, str]], json_mode: bool = False, timeout: int = 120) -> Tuple[str, float]:
    """Queries OpenAI-compatible endpoint (Ollama, LM Studio, vLLM) with warm-up support and measures latency."""
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 512
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    data = json.dumps(payload).encode("utf-8")
    url = f"{endpoint_url.rstrip('/')}/v1/chat/completions"
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    start_t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            elapsed = time.time() - start_t
            content = res_json["choices"][0]["message"]["content"]
            return content.strip(), elapsed
    except Exception as e:
        elapsed = time.time() - start_t
        raise RuntimeError(f"Endpoint query failed: {e}")


def warmup_model(endpoint_url: str, model_name: str) -> None:
    """Pre-loads model into memory to avoid cold-start timeouts during benchmarking."""
    print(f"  • Warming up and pre-loading model '{model_name}' into memory...", end="", flush=True)
    try:
        _, elapsed = query_endpoint(endpoint_url, model_name, [{"role": "user", "content": "hello"}], timeout=180)
        print(f" [OK] Ready ({elapsed:.2f}s)", flush=True)
    except Exception as e:
        print(f" [WARN] Warmup notice: {e}", flush=True)


# ── Test Execution Engine ─────────────────────────────────────────────────────

def run_brain_test_suite(endpoint_url: str = "http://localhost:11434", model_name: str = "qwen3.5:latest") -> Dict[str, Any]:
    print_header(f"BRAIN & DIRECTOR MODEL PRE-TEST SUITE: {model_name}")
    print(f"{Colors.BOLD}Target Endpoint:{Colors.RESET} {endpoint_url}")
    print(f"{Colors.BOLD}Evaluation Criteria:{Colors.RESET} Schema Validity, Hallucination Resistance, Routing, Latency\n")

    warmup_model(endpoint_url, model_name)
    print()

    scores = {
        "schema_passed": 0,
        "schema_total": len(ROUTING_TEST_CASES),
        "routing_passed": 0,
        "routing_total": len(ROUTING_TEST_CASES),
        "hallucination_passed": 0,
        "hallucination_total": len(HALLUCINATION_TEST_CASES),
        "pruning_passed": 0,
        "pruning_total": len(PRUNING_TEST_CASES),
        "latencies": []
    }

    # 1. Test Schema Adherence & Intent Routing
    print(f"{Colors.CYAN}{Colors.BOLD}[TEST 1/3] Intent Classification & JSON Schema Compliance:{Colors.RESET}")
    for idx, tc in enumerate(ROUTING_TEST_CASES, start=1):
        prompt = (
            f"You are a strict AI supervisor. Classify the user query into exactly ONE category: "
            f"[CODING, MATH, DATABASE, SYSADMIN, CREATIVE, SECURITY].\n"
            f"You MUST respond ONLY with a raw JSON object formatted as: "
            f'{{"route": "<CATEGORY>", "confidence": <0.0-1.0>, "summary": "<brief explanation>"}}\n\n'
            f"Query: {tc['prompt']}"
        )
        
        try:
            content, latency = query_endpoint(endpoint_url, model_name, [{"role": "user", "content": prompt}], json_mode=True)
            scores["latencies"].append(latency)
            
            # Clean markdown codeblocks if model wrapped it
            clean_json = content
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            parsed = json.loads(clean_json)
            scores["schema_passed"] += 1
            
            route_actual = parsed.get("route", "").upper()
            if tc["expected_route"] in route_actual:
                scores["routing_passed"] += 1
                print(f"  • Case {idx}: [{Colors.GREEN}PASS{Colors.RESET}] Expected: {tc['expected_route']} | Got: {route_actual} ({latency:.2f}s)")
            else:
                print(f"  • Case {idx}: [{Colors.RED}FAIL{Colors.RESET}] Expected: {tc['expected_route']} | Got: {route_actual} ({latency:.2f}s)")
        except Exception as e:
            print(f"  • Case {idx}: [{Colors.RED}ERROR{Colors.RESET}] JSON Parse Failure: {e}")

    # 2. Test Hallucination Resistance & Negative Constraints
    print(f"\n{Colors.CYAN}{Colors.BOLD}[TEST 2/3] Hallucination Resistance & Negative Constraint Adherence:{Colors.RESET}")
    for idx, tc in enumerate(HALLUCINATION_TEST_CASES, start=1):
        prompt = (
            f"Context: \"{tc['context']}\"\n\n"
            f"Instruction: {tc['prompt']}\n"
            f"Provide ONLY the verified facts from the context. Do not extrapolate."
        )
        
        try:
            content, latency = query_endpoint(endpoint_url, model_name, [{"role": "user", "content": prompt}])
            scores["latencies"].append(latency)
            
            hallucinated = [f for f in tc["forbidden_entities"] if f.lower() in content.lower()]
            missing_req = [r for r in tc["required_entities"] if r.lower() not in content.lower()]

            if not hallucinated and not missing_req:
                scores["hallucination_passed"] += 1
                print(f"  • Case {idx}: [{Colors.GREEN}PASS{Colors.RESET}] Zero Hallucinations. Exact facts retained. ({latency:.2f}s)")
            else:
                reasons = []
                if hallucinated: reasons.append(f"Hallucinated: {hallucinated}")
                if missing_req: reasons.append(f"Missed: {missing_req}")
                print(f"  • Case {idx}: [{Colors.RED}FAIL{Colors.RESET}] {' | '.join(reasons)} ({latency:.2f}s)")
        except Exception as e:
            print(f"  • Case {idx}: [{Colors.RED}ERROR{Colors.RESET}] Query Failed: {e}")

    # 3. Test Semantic Pruning Fidelity
    print(f"\n{Colors.CYAN}{Colors.BOLD}[TEST 3/3] Semantic Context Pruning Fidelity:{Colors.RESET}")
    for idx, tc in enumerate(PRUNING_TEST_CASES, start=1):
        prompt = (
            f"Prune the following verbose message down to only essential entity key-value pairs (maximum 15 words):\n"
            f"\"{tc['verbose_text']}\""
        )
        try:
            content, latency = query_endpoint(endpoint_url, model_name, [{"role": "user", "content": prompt}])
            scores["latencies"].append(latency)
            
            retained = [k for k in tc["essential_keys"] if k.lower() in content.lower()]
            if len(retained) == len(tc["essential_keys"]):
                scores["pruning_passed"] += 1
                print(f"  • Case {idx}: [{Colors.GREEN}PASS{Colors.RESET}] Retained all critical keys: {retained} ({latency:.2f}s)")
            else:
                missing = [k for k in tc["essential_keys"] if k.lower() not in content.lower()]
                print(f"  • Case {idx}: [{Colors.YELLOW}WARN{Colors.RESET}] Missed keys: {missing} ({latency:.2f}s)")
        except Exception as e:
            print(f"  • Case {idx}: [{Colors.RED}ERROR{Colors.RESET}] Query Failed: {e}")

    # ── Final Score Calculation ───────────────────────────────────────────────
    schema_pct = (scores["schema_passed"] / max(1, scores["schema_total"])) * 100
    routing_pct = (scores["routing_passed"] / max(1, scores["routing_total"])) * 100
    halluc_pct = (scores["hallucination_passed"] / max(1, scores["hallucination_total"])) * 100
    prune_pct = (scores["pruning_passed"] / max(1, scores["pruning_total"])) * 100
    avg_latency = sum(scores["latencies"]) / max(1, len(scores["latencies"]))

    composite_score = (schema_pct * 0.25) + (routing_pct * 0.35) + (halluc_pct * 0.30) + (prune_pct * 0.10)

    print_header("BENCHMARK RESULTS & DIRECTOR CERTIFICATION")
    print(f"  • Schema Compliance Rate:       {schema_pct:.1f}% ({scores['schema_passed']}/{scores['schema_total']})")
    print(f"  • Intent Routing Accuracy:      {routing_pct:.1f}% ({scores['routing_passed']}/{scores['routing_total']})")
    print(f"  • Hallucination Resistance:     {halluc_pct:.1f}% ({scores['hallucination_passed']}/{scores['hallucination_total']})")
    print(f"  • Entity Pruning Fidelity:      {prune_pct:.1f}% ({scores['pruning_passed']}/{scores['pruning_total']})")
    print(f"  • Average Latency per Decision: {avg_latency:.2f} seconds")
    print(f"\n{Colors.BOLD}  OVERALL COMPOSITE SCORE: {composite_score:.1f} / 100.0{Colors.RESET}")

    if composite_score >= 85.0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}  ✅ VERDICT: PASSED — Model is Certified for Brain / Director Role!{Colors.RESET}\n")
    elif composite_score >= 70.0:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}  ⚠️ VERDICT: CONDITIONAL — Usable with strict GBNF Grammar Enforcement.{Colors.RESET}\n")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}  ❌ VERDICT: FAILED — High hallucination or schema failure rate. Not recommended as Director.{Colors.RESET}\n")

    return scores


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Brain Model Pre-Test Suite")
    parser.add_argument("--endpoint", default="http://localhost:11434", help="OpenAI-compatible endpoint URL")
    parser.add_argument("--model", default="qwen3.5:latest", help="Model name to evaluate")
    args = parser.parse_args()

    run_brain_test_suite(args.endpoint, args.model)


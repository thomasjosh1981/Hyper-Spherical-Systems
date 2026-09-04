"""
Synthuron Universal Mind-Map, Vault Storage & Quantum Synapse Demo
==================================================================
Demonstrates:
1. Tree-to-Tendril Hierarchy (HyperHubs, Arterial Synthurons, MicroTendrils).
2. HyperSynthurons (Direct zero-hub wormhole links between obscure concepts).
3. 4D Hyperspherical Overlapping Sectors.
4. Obfuscated Blind File Vault (Nameless hashed files, Header, Body, 50-char Rolling Footer).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from synthuron.context_engine import InfiniteContextEngine
from synthuron.vault import ObfuscatedVaultStorage, HyperSynthuron, MicroTendril

def run_synthuron_complete_demo():
    print("=" * 90)
    print(" SYNTHURON UNIVERSAL MIND-MAP, HYPERSPHERICAL VAULT & QUANTUM SYNAPSE DEMO")
    print("=" * 90)

    engine = InfiniteContextEngine(max_active_chars=450, storage_dir="./demo_synthuron_memory")
    vault = ObfuscatedVaultStorage(vault_dir="./demo_synthuron_vault")

    turns = [
        ("The Project Tesseract 3D center-out spiral formula must start at dead-center.", "user"),
        ("Hey man, my dad died, it was impactful in my life, definitely a hard cut opening new doors.", "user"),
        ("Let's implement the 4-corner orthogonal unwrap scan in Python.", "user"),
        ("By the way, what kind of pizza dough recipe is best for high temp ovens?", "user")
    ]

    stored_nodes = []
    vault_hashes = []

    for idx, (text, role) in enumerate(turns, 1):
        res = engine.add_turn(text, role=role)
        node = engine.all_nodes[res["node_id"]]
        stored_nodes.append(node)

        # Write to Obfuscated Vault with Rolling Footer
        v_hash = vault.write_micro_cluster(node, issi_dictionary_snippet=f"REGISTRY_KEY_{node.node_id}_SEC")
        vault_hashes.append(v_hash)
        
        f = res["flag"]
        print(f"\n--- [TURN {idx}] ---")
        print(f"Message: \"{text}\"")
        print(f"  • SFIRE Tag:      [{f['packed_tag']}] (S:{f['seriousness']} F:{f['force']} I:{f['cruciality']} R:{f['relevance']} E:{f['epoch']})")
        print(f"  • 🔒 Vault File:   synthuron_vault/{v_hash} (Blind Extensionless File)")

    print("\n" + "=" * 90)
    print(" 🌌 HYPERSYNTHURON ZERO-HUB TUNNEL TEST (Linking 'Tesseract' to 'Pizza Dough'):")
    print("=" * 90)
    # Direct quantum link between Node 1 (Tesseract) and Node 4 (Pizza) with NO intermediary hub!
    tunnel = HyperSynthuron(
        source_id=stored_nodes[0].node_id,
        target_id=stored_nodes[3].node_id,
        affinity=4.5,
        context_tag="late_night_coding_session_snack"
    )
    print(f"Created direct HyperSynthuron Tunnel: [{stored_nodes[0].node_id}] ═══════(Affinity: {tunnel.weight} | Tag: '{tunnel.context_tag}')═══════► [{stored_nodes[3].node_id}]")

    print("\n" + "=" * 90)
    print(" 📂 OBFUSCATED VAULT DECOMPRESSION & STEGANOGRAPHIC FOOTER INSPECTOR:")
    print("=" * 90)
    test_hash = vault_hashes[1]  # The Dad milestone node
    decrypted_cluster = vault.read_micro_cluster(test_hash)
    h = decrypted_cluster["header"]
    p = decrypted_cluster["payload"]
    
    print(f"Reading Vault File: {test_hash}")
    print(f"  • Header:           NodeID={h['node_id']} | 4D Coordinates={h['coords']} | SFIRE Tag={h['tag']}")
    print(f"  • Payload Decompr:  Class={p['class']} | Text=\"{p['raw_text']}\"")
    print(f"  • ISSI Tokens:      {p['issi_tokens']}")
    print(f"  • 50-Char Footer:   {decrypted_cluster['footer_signature']} (Contains 30-char embedded key & rolling chaff)")

    print("\n" + "=" * 90)
    print(" 🌐 OVERLAPPING 4D HYPERSPHERICAL SECTORS:")
    print("=" * 90)
    for sid, sec in vault.sectors.items():
        print(f"  • Sector '{sid}': Center 4D={sec.center} | Radius={sec.radius} | Indexed Vault Files={len(sec.vault_file_hashes)}")


if __name__ == "__main__":
    run_synthuron_complete_demo()

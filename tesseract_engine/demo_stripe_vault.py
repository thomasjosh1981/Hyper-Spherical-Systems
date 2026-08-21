"""
Tesseract 5-File Stripe Set & Parity Recovery Demo Suite
========================================================
Demonstrates:
1. End-to-end 3D Center-Out Cube Ingress & 4-Corner Top-Down DLASC unwinding.
2. Generation of UUIDv7 Cubical Address Codes with single-digit hyphen substitutions.
3. 5-File Chameleon Stripe Set generation (S1, S2, S3, Parity, Decoy Chaff).
4. Simulated file loss (e.g. Deleting Stripe B).
5. 100% Lossless reconstruction using remaining 2 stripes + Parity slice.
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tesseract_engine.stripe_vault import TesseractStripeVault
from tesseract_engine.cubical_address import CubicalAddressEngine


def run_demo():
    print("=" * 80)
    print("  TESSERACT 5-FILE CHAMELEON STRIPE SET & PARITY RECOVERY ENGINE")
    print("=" * 80)

    test_payload = (
        "I need you to pull up everything you can about my hyperspherical systems and "
        "Project Tesseract. The center-out spiral builds from the dead center voxel and "
        "radiates outward in all three dimensions simultaneously before unwinding through "
        "the 4-corner orthogonal scan."
    )

    test_vault_dir = "./demo_vault_stripes"
    if os.path.exists(test_vault_dir):
        shutil.rmtree(test_vault_dir)

    print("\n[1] ENCODING & STRIPING PAYLOAD:")
    print(f"  • Original Raw Input: \"{test_payload[:60]}...\"")
    
    stripe_res = TesseractStripeVault.encode_and_stripe(
        raw_text=test_payload,
        output_dir=test_vault_dir,
        file_prefix="telemetry_log",
        starting_face=2,
        direction_mode=1,
        plane_seq_idx=0
    )

    addr = stripe_res["cubical_address"]
    dim = stripe_res["dimension"]
    print(f"  • Cube Dimension: {dim}x{dim}x{dim} ({stripe_res['total_voxels']} voxels)")
    print(f"  • UUIDv7 Cubical Address: {addr}")
    print(f"  • Stripe Block Size: {stripe_res['stripe_size_bytes']} bytes per slice")
    
    print("\n[2] GENERATED 5-FILE CHAMELEON STRIPE SET ON DISK:")
    for role, path in stripe_res["files"].items():
        sz = os.path.getsize(path)
        print(f"  • {role:<16} -> {os.path.basename(path):<22} ({sz} bytes)")

    # 3. Test Pristine Recovery
    print("\n[3] PRISTINE RECONSTRUCTION (All 3 data files present):")
    recon_pristine = TesseractStripeVault.reconstruct_and_decode(test_vault_dir, file_prefix="telemetry_log")
    print(f"  • Recovery Status: {recon_pristine['status']}")
    print(f"  • Mode:            {recon_pristine['recovery_mode']}")
    print(f"  • Recovered Text:  \"{recon_pristine['recovered_text'][:60]}...\"")

    # 4. Simulate Catastrophic File Loss (Delete Stripe B: telemetry_log5.dat)
    stripe_b_path = stripe_res["files"]["file_2_data_b"]
    print(f"\n[4] SIMULATING FILE CORRUPTION / DELETION:")
    print(f"  • Deleting {os.path.basename(stripe_b_path)} to trigger 3-of-4 parity recovery...")
    os.remove(stripe_b_path)
    print(f"  • File successfully deleted. Remaining files in vault: {len(os.listdir(test_vault_dir))}")

    # 5. Run Parity Rebuilding
    print("\n[5] RUNNING 3-OF-4 XOR PARITY RECONSTRUCTION:")
    recon_parity = TesseractStripeVault.reconstruct_and_decode(test_vault_dir, file_prefix="telemetry_log")
    print(f"  • Recovery Status: {recon_parity['status']}")
    print(f"  • Mode:            {recon_parity['recovery_mode']}")
    print(f"  • Recovered Text:  \"{recon_parity['recovered_text'][:60]}...\"")

    # 6. Verify Exact Match
    is_lossless = (recon_pristine["recovered_text"] == recon_parity["recovered_text"])
    print("\n[6] LOSSLESS FIDELITY VERIFICATION:")
    print(f"  • Parity Rebuilt String Match: {'100.0% EXACT LOSSLESS MATCH' if is_lossless else 'MISMATCH'}")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()

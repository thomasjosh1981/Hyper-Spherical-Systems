import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_identity import get_or_prompt_identity
from tesseract_engine.stripe_vault import TesseractStripeVault

def main():
    identity = get_or_prompt_identity()
    print("=" * 74)
    print("  HYPERSPHERICAL 5-FILE CHAMELEON STRIPE VAULT & PARITY RECOVERY TOOL")
    print(f"  Active User Profile: {identity['username']} ({identity['email']})")
    print("=" * 74)

    while True:
        print("\nChoose an action:")
        print("  1. Encode & Shard Text into 5-File Chameleon Stripe Set")
        print("  2. Reconstruct Text from 5-File Stripe Directory (Supports 1 Lost File)")
        print("  3. Run Built-In 3-of-4 Parity Deletion & Recovery Test")
        print("  4. Exit")
        choice = input("\nEnter choice (1-4): ").strip()

        if choice == "1":
            txt = input("\nEnter payload to encode and stripe: ").strip()
            out_dir = input("Enter output directory for 5 stripes [./vault_stripes]: ").strip() or "./vault_stripes"
            prefix = input("Enter chameleon file prefix [hermes_cache]: ").strip() or "hermes_cache"
            res = TesseractStripeVault.encode_and_stripe(raw_text=txt, output_dir=out_dir, file_prefix=prefix)
            print(f"\n[SUCCESS] Generated 5 Chameleon Files in: {out_dir}")
            print(f"UUIDv7 Address: {res['cubical_address']}")
            for k, p in res['files'].items():
                print(f"  • {k:<16} -> {os.path.basename(p)}")
        elif choice == "2":
            in_dir = input("\nEnter directory containing stripe files: ").strip()
            prefix = input("Enter chameleon file prefix [hermes_cache]: ").strip() or "hermes_cache"
            if os.path.exists(in_dir):
                rec = TesseractStripeVault.reconstruct_and_decode(vault_dir=in_dir, file_prefix=prefix)
                print(f"\n[Status] {rec['status']} (Mode: {rec['recovery_mode']})")
                print(f"[Recovered Text]: \"{rec['recovered_text']}\"")
            else:
                print("[ERROR] Directory does not exist.")
        elif choice == "3":
            from tesseract_engine.demo_stripe_vault import run_demo
            run_demo()
        elif choice == "4":
            break

if __name__ == "__main__":
    main()

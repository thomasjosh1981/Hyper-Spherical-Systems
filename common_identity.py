import os
import sys
import json
import hashlib
import getpass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".hyperspherical")) / "HyperSpherical"
IDENTITY_FILE = CONFIG_DIR / "local_scramble_identity.dat"

def get_or_prompt_identity(interactive=True):
    """
    Retrieves or prompts for the 4-part local scramble identity:
    Username, Password, Email, Phone.
    Privacy guarantee: Used STRICTLY locally as a mathematical entropy seed.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if IDENTITY_FILE.exists():
        try:
            with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            pass

    if not interactive:
        # Default fallback deterministic seed for headless mode
        return {
            "username": "HyperSphericalUser",
            "email": "user@hyperspherical.local",
            "phone": "0000000000",
            "seed_hash": hashlib.sha512(b"HyperSphericalDefaultSeed").hexdigest()
        }

    print("\n" + "=" * 74)
    print("  HYPERSPHERICAL LOCAL CRYPTOGRAPHIC SCRAMBLE INITIALIZATION")
    print("=" * 74)
    print("  [PRIVACY NOTICE]:")
    print("  The username, email, password, and phone number you provide are used")
    print("  STRICTLY as a mathematical local entropy seed to scramble and unscramble")
    print("  your 3D Tesseract cubes, ISSI ciphers, and 5-File Stripe sets.")
    print("  * ZERO data is sent to external servers.")
    print("  * ZERO personal info is retained outside your local machine.")
    print("=" * 74 + "\n")

    username = input("  Enter Username: ").strip()
    while not username:
        username = input("  Username cannot be empty. Enter Username: ").strip()

    email = input("  Enter Email Address (for salt): ").strip()
    while not email:
        email = input("  Email cannot be empty. Enter Email: ").strip()

    phone = input("  Enter Phone Number (used only for mathematical scramble seed): ").strip()
    phone_clean = "".join(ch for ch in phone if ch.isdigit())
    while not phone_clean:
        phone = input("  Please enter a valid numeric phone seed: ").strip()
        phone_clean = "".join(ch for ch in phone if ch.isdigit())

    password = getpass.getpass("  Enter Master Scramble Password: ").strip()
    while not password:
        password = getpass.getpass("  Password cannot be empty. Enter Password: ").strip()

    # Derive Master 512-bit Key
    salt = f"{email}:{phone_clean}".encode("utf-8")
    master_seed = hashlib.pbkdf2_hmac(
        "sha512",
        f"{username}:{password}:{phone_clean}:{email}".encode("utf-8"),
        salt,
        100000
    )

    profile = {
        "username": username,
        "email": email,
        "phone_anchor": hashlib.sha256(phone_clean.encode("utf-8")).hexdigest()[:16],
        "seed_hash": master_seed.hex()
    }

    try:
        with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        print(f"\n  [SUCCESS] Scramble seed generated and linked across all HyperSpherical modules!")
        print(f"  Configuration saved to: {IDENTITY_FILE}\n")
    except Exception as e:
        print(f"  [WARN] Could not persist profile: {e}")

    return profile

if __name__ == "__main__":
    get_or_prompt_identity()

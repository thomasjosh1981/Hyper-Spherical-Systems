# gui/pirate_ssl_bridge.py — HTTPS Traffic Optimizer & SSL Bridge
#
# Hyper-Spherical Systems — Pirate Llama SSL Traffic Optimizer
#
# How it works:
#   1. Generates a local root CA certificate on first run (stored in ~/.hypes/).
#   2. Dynamically signs per-domain certificates using the local CA.
#   3. Handles HTTPS CONNECT tunnels from pirate_intercept.py.
#   4. Presents a trusted cert (signed by local CA) to the client.
#   5. Makes a real TLS connection to the upstream cloud provider.
#   6. Optimizes traffic via CCTM compression in both directions.
#   7. Auto-installs the local CA into Windows/macOS/Linux trust stores.
#
# Developer: twiztedsocal
# License: Proprietary — All Rights Reserved

from __future__ import annotations

import os
import ssl
import sys
import json
import time
import socket
import struct
import threading
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timezone, timedelta

# ── CA storage paths ──────────────────────────────────────────────────────────
HYPES_DIR      = Path.home() / ".hypes"
CA_CERT_PATH   = HYPES_DIR / "hypes_ca.pem"
CA_KEY_PATH    = HYPES_DIR / "hypes_ca_key.pem"
CERT_CACHE_DIR = HYPES_DIR / "tls_cert_cache"
CA_INSTALLED_FLAG = HYPES_DIR / "ca_installed.flag"

# ── Log ───────────────────────────────────────────────────────────────────────
def _log(msg: str) -> None:
    print(f"[mitm-tls] {msg}")


# ── CA Generation (using cryptography library or fallback to openssl CLI) ─────
def _generate_ca_openssl() -> bool:
    """Generate CA cert + key using openssl CLI."""
    HYPES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # Generate CA key
        subprocess.run([
            "openssl", "genrsa", "-out", str(CA_KEY_PATH), "4096"
        ], check=True, capture_output=True, timeout=30)

        # Generate self-signed CA cert
        subprocess.run([
            "openssl", "req", "-new", "-x509",
            "-days", "3650",
            "-key", str(CA_KEY_PATH),
            "-out", str(CA_CERT_PATH),
            "-subj", "/CN=HypeS Pirate Llama CA/O=Hyper-Spherical Systems/C=US"
        ], check=True, capture_output=True, timeout=30)

        _log(f"CA generated via openssl → {CA_CERT_PATH}")
        return True
    except Exception as e:
        _log(f"openssl CA generation failed: {e}")
        return False


def _generate_ca_cryptography() -> bool:
    """Generate CA cert + key using the cryptography Python library."""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        HYPES_DIR.mkdir(parents=True, exist_ok=True)

        # Generate RSA key
        key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

        # Build CA cert
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "HypeS Pirate Llama CA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Hyper-Spherical Systems"),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        ])

        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, key_cert_sign=True,
                    crl_sign=True, content_commitment=False,
                    key_encipherment=False, data_encipherment=False,
                    key_agreement=False, encipher_only=False, decipher_only=False
                ), critical=True
            )
            .sign(key, hashes.SHA256())
        )

        # Write key
        CA_KEY_PATH.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()
            )
        )

        # Write cert
        CA_CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

        _log(f"CA generated via cryptography library → {CA_CERT_PATH}")
        return True

    except ImportError:
        _log("cryptography library not available, falling back to openssl CLI")
        return False
    except Exception as e:
        _log(f"CA generation via cryptography failed: {e}")
        return False


def ensure_ca() -> bool:
    """Ensure the local CA cert and key exist, generating them if needed."""
    if CA_CERT_PATH.exists() and CA_KEY_PATH.exists():
        return True

    _log("Generating HypeS local CA certificate...")
    if _generate_ca_cryptography():
        return True
    if _generate_ca_openssl():
        return True

    _log("WARNING: Could not generate CA certificate. TLS splice unavailable.")
    return False


# ── Per-domain cert generation ────────────────────────────────────────────────
def _get_domain_cert(hostname: str) -> Optional[Tuple[str, str]]:
    """
    Get or generate a domain-specific cert signed by our local CA.
    Returns (cert_path, key_path) or None if unavailable.
    """
    CERT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = hostname.replace("*", "wildcard").replace(".", "_")
    cert_path = CERT_CACHE_DIR / f"{safe_name}.pem"
    key_path  = CERT_CACHE_DIR / f"{safe_name}_key.pem"

    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)

    # Try cryptography library first
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509 import DNSName, IPAddress
        import ipaddress

        # Load CA
        ca_cert = x509.load_pem_x509_certificate(CA_CERT_PATH.read_bytes())
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        ca_key = load_pem_private_key(CA_KEY_PATH.read_bytes(), password=None)

        # Generate domain key
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        now = datetime.now(timezone.utc)
        san_list = [DNSName(hostname)]
        if not hostname.startswith("*."):
            san_list.append(DNSName(f"*.{hostname}"))

        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, hostname),
            ]))
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
            .add_extension(
                x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False
            )
            .sign(ca_key, hashes.SHA256())
        )

        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()
            )
        )
        cert_path.write_bytes(
            cert.public_bytes(serialization.Encoding.PEM) + CA_CERT_PATH.read_bytes()
        )

        return str(cert_path), str(key_path)

    except ImportError:
        pass
    except Exception as e:
        _log(f"Domain cert generation failed for {hostname}: {e}")

    # Fallback: openssl CLI
    try:
        san_conf = tempfile.NamedTemporaryFile(mode="w", suffix=".cnf", delete=False)
        san_conf.write(f"""[req]
distinguished_name=req_distinguished_name
x509_extensions=v3_req
prompt=no
[req_distinguished_name]
CN={hostname}
[v3_req]
subjectAltName=DNS:{hostname},DNS:*.{hostname}
extendedKeyUsage=serverAuth
""")
        san_conf.close()

        tmp_key = str(key_path)
        tmp_csr = str(key_path).replace("_key.pem", "_csr.pem")
        tmp_cert = str(cert_path)

        subprocess.run([
            "openssl", "genrsa", "-out", tmp_key, "2048"
        ], check=True, capture_output=True, timeout=15)

        subprocess.run([
            "openssl", "req", "-new",
            "-key", tmp_key, "-out", tmp_csr,
            "-subj", f"/CN={hostname}",
        ], check=True, capture_output=True, timeout=15)

        subprocess.run([
            "openssl", "x509", "-req",
            "-days", "365",
            "-in", tmp_csr,
            "-CA", str(CA_CERT_PATH),
            "-CAkey", str(CA_KEY_PATH),
            "-CAcreateserial",
            "-out", tmp_cert,
            "-extensions", "v3_req",
            "-extfile", san_conf.name,
        ], check=True, capture_output=True, timeout=15)

        os.unlink(san_conf.name)
        try:
            os.unlink(tmp_csr)
        except Exception:
            pass

        return tmp_cert, tmp_key

    except Exception as e:
        _log(f"openssl domain cert fallback failed for {hostname}: {e}")
        return None


# ── CA installation ───────────────────────────────────────────────────────────
def install_ca_system_trust() -> bool:
    """
    Install the HypeS local CA into the system trust store.
    Requires admin rights (already elevated via UAC in installer).
    Returns True if successful.
    """
    if CA_INSTALLED_FLAG.exists():
        return True  # Already installed

    if not CA_CERT_PATH.exists():
        _log("CA cert not found — generate it first")
        return False

    _log("Installing HypeS CA into system trust store...")

    if sys.platform == "win32":
        try:
            # Windows: Import into Root store via certutil
            result = subprocess.run(
                ["certutil", "-addstore", "-f", "Root", str(CA_CERT_PATH)],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                CA_INSTALLED_FLAG.write_text("installed")
                _log("CA installed into Windows Root store via certutil")
                return True
            else:
                _log(f"certutil failed: {result.stderr.strip()}")
                # Try PowerShell Import-Certificate as fallback
                ps_cmd = (
                    f"Import-Certificate -FilePath '{CA_CERT_PATH}' "
                    f"-CertStoreLocation Cert:\\LocalMachine\\Root"
                )
                result2 = subprocess.run(
                    ["powershell", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=15
                )
                if result2.returncode == 0:
                    CA_INSTALLED_FLAG.write_text("installed")
                    _log("CA installed into Windows Root store via PowerShell")
                    return True
        except Exception as e:
            _log(f"Windows CA install failed: {e}")

    elif sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["security", "add-trusted-cert", "-d", "-r", "trustRoot",
                 "-k", "/Library/Keychains/System.keychain", str(CA_CERT_PATH)],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                CA_INSTALLED_FLAG.write_text("installed")
                _log("CA installed into macOS System Keychain")
                return True
        except Exception as e:
            _log(f"macOS CA install failed: {e}")

    else:
        # Linux — try update-ca-certificates
        try:
            dest = Path("/usr/local/share/ca-certificates/hypes_ca.crt")
            import shutil as _sh
            _sh.copy2(str(CA_CERT_PATH), str(dest))
            subprocess.run(["update-ca-certificates"], check=True,
                           capture_output=True, timeout=15)
            CA_INSTALLED_FLAG.write_text("installed")
            _log("CA installed via update-ca-certificates (Linux)")
            return True
        except Exception as e:
            _log(f"Linux CA install failed: {e}")

    return False


def uninstall_ca_system_trust() -> bool:
    """Remove HypeS CA from system trust store."""
    if sys.platform == "win32":
        try:
            # Find and remove by subject
            result = subprocess.run(
                ["certutil", "-delstore", "Root", "HypeS Pirate Llama CA"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                CA_INSTALLED_FLAG.unlink(missing_ok=True)
                _log("CA removed from Windows Root store")
                return True
        except Exception as e:
            _log(f"CA removal failed: {e}")
    return False


# ── TLS splice core ───────────────────────────────────────────────────────────
def splice_tls_connection(
    client_sock: socket.socket,
    target_host: str,
    target_port: int
) -> None:
    """
    SSL Bridge — optimized HTTPS relay:
    1. Wrap client socket with a trusted domain cert.
    2. Open TLS connection to real upstream server.
    3. Optimize and relay data in both directions.
    """
    if not ensure_ca():
        raise RuntimeError("CA not available — TLS splice aborted")

    domain_cert = _get_domain_cert(target_host)
    if domain_cert is None:
        raise RuntimeError(f"Could not generate cert for {target_host}")

    cert_path, key_path = domain_cert

    # ── Wrap client socket with our forged cert ──
    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    client_ctx.load_cert_chain(cert_path, key_path)
    client_ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    try:
        tls_client = client_ctx.wrap_socket(client_sock, server_side=True)
    except ssl.SSLError as e:
        _log(f"Client TLS handshake failed for {target_host}: {e}")
        raise

    # ── Open TLS connection to real upstream ──
    upstream_ctx = ssl.create_default_context()
    upstream_ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    try:
        raw_upstream = socket.create_connection((target_host, target_port), timeout=15)
        tls_upstream = upstream_ctx.wrap_socket(raw_upstream, server_hostname=target_host)
    except Exception as e:
        _log(f"Upstream TLS connection failed for {target_host}: {e}")
        try:
            tls_client.close()
        except Exception:
            pass
        raise

    # ── Bidirectional relay with interception ──
    def _intercept_client_to_upstream():
        """Read from client, optimize, send to upstream."""
        try:
            buffer = b""
            while True:
                try:
                    chunk = tls_client.recv(8192)
                    if not chunk:
                        break
                    buffer += chunk

                    # Try to parse and optimize HTTP request
                    if b"\r\n\r\n" in buffer:
                        optimized = _optimize_https_request(buffer, target_host)
                        tls_upstream.sendall(optimized)
                        buffer = b""
                    elif len(buffer) > 1_000_000:
                        # Safety: flush large buffers unmodified
                        tls_upstream.sendall(buffer)
                        buffer = b""

                except ssl.SSLWantReadError:
                    continue
                except Exception:
                    break
            if buffer:
                try:
                    tls_upstream.sendall(buffer)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            try:
                tls_upstream.close()
            except Exception:
                pass

    def _relay_upstream_to_client():
        """Read upstream response, decompress, send to client."""
        try:
            buffer = b""
            while True:
                try:
                    chunk = tls_upstream.recv(8192)
                    if not chunk:
                        break
                    buffer += chunk

                    if b"\r\n\r\n" in buffer:
                        decompressed = _decompress_https_response(buffer)
                        tls_client.sendall(decompressed)
                        buffer = b""
                    elif len(buffer) > 1_000_000:
                        tls_client.sendall(buffer)
                        buffer = b""

                except ssl.SSLWantReadError:
                    continue
                except Exception:
                    break
            if buffer:
                try:
                    tls_client.sendall(buffer)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            try:
                tls_client.close()
            except Exception:
                pass

    t1 = threading.Thread(target=_intercept_client_to_upstream, daemon=True)
    t2 = threading.Thread(target=_relay_upstream_to_client, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=120)
    t2.join(timeout=120)


# ── HTTPS body optimization ───────────────────────────────────────────────────
def _optimize_https_request(raw: bytes, host: str) -> bytes:
    """Apply CCTM compression to HTTPS request body before forwarding upstream."""
    try:
        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            return raw
        headers_raw = raw[:header_end + 4]
        body = raw[header_end + 4:]

        if not body:
            return raw

        body_json = json.loads(body.decode("utf-8", errors="replace"))
        messages = body_json.get("messages", [])
        if not messages:
            return raw

        from pirate_intercept import _cctm_compress  # shared compression core
        for msg in messages:
            if msg.get("content"):
                msg["content"], _ = _cctm_compress(msg["content"])
        if isinstance(body_json.get("system"), str):
            body_json["system"], _ = _cctm_compress(body_json["system"])

        new_body = json.dumps(body_json).encode("utf-8")

        # Update Content-Length header
        headers_str = headers_raw.decode("utf-8", errors="replace")
        updated_headers = "\r\n".join(
            f"Content-Length: {len(new_body)}"
            if h.lower().startswith("content-length:") else h
            for h in headers_str.split("\r\n")
        )
        return updated_headers.encode() + new_body

    except Exception:
        return raw


def _decompress_https_response(raw: bytes) -> bytes:
    """Reverse CCTM substitution in HTTPS response body."""
    try:
        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            return raw
        headers_raw = raw[:header_end + 4]
        body = raw[header_end + 4:]

        if not body:
            return raw

        resp_json = json.loads(body.decode("utf-8", errors="replace"))

        from pirate_ssl_bridge import _cctm_decompress  # shared decompression core
        for choice in resp_json.get("choices", []):
            content = choice.get("message", {}).get("content", "")
            if content:
                choice["message"]["content"] = _cctm_decompress(content)
        for block in resp_json.get("content", []):
            if block.get("type") == "text":
                block["text"] = _cctm_decompress(block["text"])

        new_body = json.dumps(resp_json).encode("utf-8")
        headers_str = headers_raw.decode("utf-8", errors="replace")
        updated_headers = "\r\n".join(
            f"Content-Length: {len(new_body)}"
            if h.lower().startswith("content-length:") else h
            for h in headers_str.split("\r\n")
        )
        return updated_headers.encode() + new_body

    except Exception:
        return raw


# ── Public API ────────────────────────────────────────────────────────────────
def initialize(auto_install_ca: bool = True) -> dict:
    """
    Initialize the SSL Bridge module.
    - Generates local CA if not present.
    - Optionally installs CA into system trust store.
    Returns status dict.
    """
    ca_ok = ensure_ca()
    ca_installed = False

    if ca_ok and auto_install_ca:
        ca_installed = install_ca_system_trust()

    return {
        "ca_ready": ca_ok,
        "ca_path": str(CA_CERT_PATH) if ca_ok else None,
        "ca_installed_in_system_store": ca_installed or CA_INSTALLED_FLAG.exists(),
        "cert_cache_dir": str(CERT_CACHE_DIR),
    }


def get_ca_cert_pem() -> Optional[str]:
    """Returns the CA cert PEM content (for manual installation if needed)."""
    if CA_CERT_PATH.exists():
        return CA_CERT_PATH.read_text()
    return None


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HypeS SSL Traffic Bridge")
    parser.add_argument("--init", action="store_true", help="Initialize CA and install into system")
    parser.add_argument("--uninstall-ca", action="store_true", help="Remove CA from system trust")
    parser.add_argument("--show-ca", action="store_true", help="Print CA cert PEM")
    args = parser.parse_args()

    if args.init:
        status = initialize(auto_install_ca=True)
        print(json.dumps(status, indent=2))
    elif args.uninstall_ca:
        ok = uninstall_ca_system_trust()
        print(f"CA removal: {'success' if ok else 'failed'}")
    elif args.show_ca:
        pem = get_ca_cert_pem()
        print(pem if pem else "CA cert not found. Run --init first.")

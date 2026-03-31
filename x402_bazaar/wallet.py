"""Wallet management — generate, encrypt (AES-256-GCM), decrypt."""

from __future__ import annotations

import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from eth_account import Account

from x402_bazaar.exceptions import InvalidConfigError
from x402_bazaar.types import WalletInfo

# Default wallet location
DEFAULT_WALLET_DIR = Path.home() / ".x402-bazaar"
DEFAULT_WALLET_PATH = DEFAULT_WALLET_DIR / "sdk-wallet.json"


def generate_wallet() -> WalletInfo:
    """Generate a new Ethereum wallet."""
    account = Account.create()
    key_hex = account.key.hex()
    if not key_hex.startswith("0x"):
        key_hex = "0x" + key_hex
    return WalletInfo(
        private_key=key_hex,
        address=account.address,
        is_new=True,
    )


def _derive_machine_key() -> bytes:
    """Derive AES-256 key from machine identity (matches JS SDK)."""
    hostname = platform.node()
    username = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    homedir = str(Path.home())
    raw = f"{hostname}:{username}:{homedir}"
    return hashlib.sha256(raw.encode()).digest()


def encrypt_wallet(
    private_key: str,
    path: str | Path | None = None,
    *,
    password: str | None = None,
) -> Path:
    """Encrypt and save wallet to disk.

    If password is provided, uses PBKDF2 + AES-256-GCM.
    If no password, uses machine-derived key (matches JS SDK behavior).
    """
    path = Path(path) if path else DEFAULT_WALLET_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    if password:
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), b"x402-bazaar-sdk", 100_000)
    else:
        key = _derive_machine_key()

    iv = os.urandom(12)
    aesgcm = AESGCM(key)

    # Ensure private_key starts with 0x and is 32 bytes (64 hex chars)
    raw = private_key.replace("0x", "")
    raw = raw.zfill(64)  # pad to 64 hex chars
    pk = f"0x{raw}"
    ciphertext = aesgcm.encrypt(iv, pk.encode(), None)

    # Separate ciphertext and tag (last 16 bytes)
    encrypted = ciphertext[:-16]
    tag = ciphertext[-16:]

    account = Account.from_key(pk)

    wallet_data = {
        "encrypted": encrypted.hex(),
        "iv": iv.hex(),
        "tag": tag.hex(),
        "address": account.address,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "note": "Auto-generated wallet for x402 Bazaar Python SDK. Do not share.",
        "password_protected": password is not None,
    }

    path.write_text(json.dumps(wallet_data, indent=2))

    # Restrict permissions on Unix
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows doesn't support Unix permissions

    return path


def decrypt_wallet(
    path: str | Path | None = None,
    *,
    password: str | None = None,
) -> WalletInfo:
    """Decrypt wallet from disk."""
    path = Path(path) if path else DEFAULT_WALLET_PATH

    if not path.exists():
        raise InvalidConfigError(f"Wallet file not found: {path}")

    wallet_data = json.loads(path.read_text())

    is_password_protected = wallet_data.get("password_protected", False)

    if is_password_protected and not password:
        raise InvalidConfigError("Wallet is password-protected. Provide password to decrypt.")

    if is_password_protected and password:
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), b"x402-bazaar-sdk", 100_000)
    else:
        key = _derive_machine_key()

    iv = bytes.fromhex(wallet_data["iv"])
    encrypted = bytes.fromhex(wallet_data["encrypted"])
    tag = bytes.fromhex(wallet_data["tag"])

    aesgcm = AESGCM(key)

    try:
        plaintext = aesgcm.decrypt(iv, encrypted + tag, None)
    except Exception as e:
        raise InvalidConfigError(f"Failed to decrypt wallet: {e}") from e

    private_key = plaintext.decode()
    account = Account.from_key(private_key)

    return WalletInfo(
        private_key=private_key,
        address=account.address,
        is_new=False,
    )


def load_or_create_wallet(
    path: str | Path | None = None,
    *,
    private_key: str | None = None,
    password: str | None = None,
) -> WalletInfo:
    """Load existing wallet, import from key, or generate new one.

    Priority:
    1. If private_key provided, use it directly
    2. If wallet file exists, decrypt it
    3. Generate new wallet and save encrypted
    """
    if private_key:
        raw = private_key.replace("0x", "").zfill(64)
        pk = f"0x{raw}"
        account = Account.from_key(pk)
        return WalletInfo(private_key=pk, address=account.address, is_new=False)

    wallet_path = Path(path) if path else DEFAULT_WALLET_PATH

    if wallet_path.exists():
        return decrypt_wallet(wallet_path, password=password)

    # Generate new wallet
    wallet = generate_wallet()
    encrypt_wallet(wallet.private_key, wallet_path, password=password)
    return wallet

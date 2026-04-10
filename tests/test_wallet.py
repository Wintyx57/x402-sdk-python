"""Tests for wallet management."""

import json
import tempfile
from pathlib import Path

import pytest

from x402_bazaar.exceptions import InvalidConfigError
from x402_bazaar.wallet import (
    decrypt_wallet,
    encrypt_wallet,
    generate_wallet,
    load_or_create_wallet,
)


def test_generate_wallet():
    wallet = generate_wallet()
    assert wallet.private_key.startswith("0x")
    assert wallet.address.startswith("0x")
    assert len(wallet.address) == 42
    assert wallet.is_new is True


def test_generate_wallet_unique():
    w1 = generate_wallet()
    w2 = generate_wallet()
    assert w1.private_key != w2.private_key
    assert w1.address != w2.address


def test_encrypt_decrypt_machine_key():
    wallet = generate_wallet()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "wallet.json"
        encrypt_wallet(wallet.private_key, path)

        assert path.exists()
        data = json.loads(path.read_text())
        assert "encrypted" in data
        assert "iv" in data
        assert "tag" in data
        assert data["address"] == wallet.address
        assert data["password_protected"] is False

        decrypted = decrypt_wallet(path)
        assert decrypted.private_key == wallet.private_key
        assert decrypted.address == wallet.address
        assert decrypted.is_new is False


def test_encrypt_decrypt_password():
    wallet = generate_wallet()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "wallet.json"
        encrypt_wallet(wallet.private_key, path, password="my-secret-123")

        data = json.loads(path.read_text())
        assert data["password_protected"] is True

        # Wrong password should fail
        with pytest.raises(InvalidConfigError, match="Failed to decrypt"):
            decrypt_wallet(path, password="wrong-password")

        # No password should fail
        with pytest.raises(InvalidConfigError, match="password-protected"):
            decrypt_wallet(path)

        # Right password works
        decrypted = decrypt_wallet(path, password="my-secret-123")
        assert decrypted.private_key == wallet.private_key


def test_decrypt_nonexistent():
    with pytest.raises(InvalidConfigError, match="not found"):
        decrypt_wallet("/nonexistent/wallet.json")


def test_load_or_create_with_key():
    wallet = load_or_create_wallet(private_key="0x" + "ab" * 32)
    assert wallet.address.startswith("0x")
    assert wallet.is_new is False


def test_load_or_create_generates_new():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "new-wallet.json"
        wallet = load_or_create_wallet(path)
        assert wallet.is_new is True
        assert path.exists()

        # Second call loads existing
        wallet2 = load_or_create_wallet(path)
        assert wallet2.is_new is False
        assert wallet2.private_key == wallet.private_key


def test_encrypt_normalizes_key():
    """Keys without 0x prefix should be handled."""
    wallet = generate_wallet()
    key_no_prefix = wallet.private_key[2:]  # Remove 0x

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "wallet.json"
        encrypt_wallet(key_no_prefix, path)
        decrypted = decrypt_wallet(path)
        assert decrypted.private_key == wallet.private_key


def test_wallet_file_format():
    wallet = generate_wallet()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "wallet.json"
        encrypt_wallet(wallet.private_key, path)

        data = json.loads(path.read_text())
        assert set(data.keys()) == {
            "encrypted",
            "iv",
            "tag",
            "address",
            "createdAt",
            "note",
            "password_protected",
        }
        # IV should be 12 bytes = 24 hex chars
        assert len(data["iv"]) == 24
        # Tag should be 16 bytes = 32 hex chars
        assert len(data["tag"]) == 32

"""Tests for HMAC validation, quality score, and fund_wallet."""

import hashlib
import hmac as hmac_mod
import json

import httpx
import respx

from x402_bazaar.client import X402Client

# ── HMAC Validation ─────────────────────────────────────────────────


def test_verify_hmac_valid():
    key = "0x" + "ab" * 32
    secret = "my-secret-key"
    client = X402Client(private_key=key, validation_secret=secret)

    metadata = {"timestamp": "2026-03-31T12:00:00Z", "service": "joke-api"}
    canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    sig = hmac_mod.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()

    data = {
        "data": {"joke": "test"},
        "_x402": {"_validation": {**metadata, "signature": sig}},
    }
    assert client._verify_hmac(data, sig) is True


def test_verify_hmac_invalid():
    key = "0x" + "ab" * 32
    secret = "my-secret-key"
    client = X402Client(private_key=key, validation_secret=secret)

    data = {
        "data": {"joke": "test"},
        "_x402": {"_validation": {"timestamp": "2026-03-31", "signature": "wrong-sig"}},
    }
    assert client._verify_hmac(data, "wrong-sig") is False


def test_verify_hmac_no_secret():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)  # No validation_secret
    assert client._verify_hmac({}, "any") is True  # Always passes without secret


@respx.mock
def test_hmac_mismatch_blacklists():
    """If HMAC fails, service should be blacklisted."""
    key = "0x" + "ab" * 32
    secret = "my-secret"
    client = X402Client(private_key=key, validation_secret=secret)

    respx.post("https://x402-api.onrender.com/api/call/bad-svc").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {"result": "ok"},
                "_x402": {
                    "_validation": {
                        "timestamp": "2026-03-31",
                        "signature": "definitely-wrong-signature",
                    }
                },
            },
        )
    )

    # First call succeeds but should blacklist
    result = client.call("bad-svc")
    assert result.status == "success"

    # Now service is blacklisted
    assert client._is_blacklisted("bad-svc") is True


# ── Quality Score ────────────────────────────────────────────────────


def test_quality_score_none():
    assert X402Client._compute_quality_score(None) == 0.0


def test_quality_score_empty_string():
    assert X402Client._compute_quality_score("") == 0.0


def test_quality_score_short_string():
    score = X402Client._compute_quality_score("hello")
    assert 0 < score < 1


def test_quality_score_long_string():
    score = X402Client._compute_quality_score("a" * 100)
    assert score == 1.0


def test_quality_score_empty_dict():
    assert X402Client._compute_quality_score({}) == 0.0


def test_quality_score_full_dict():
    score = X402Client._compute_quality_score({"a": 1, "b": "text", "c": [1, 2]})
    assert score == 1.0


def test_quality_score_dict_with_nones():
    score = X402Client._compute_quality_score({"a": None, "b": None, "c": None})
    assert score == 0.0


def test_quality_score_empty_list():
    assert X402Client._compute_quality_score([]) == 0.0


def test_quality_score_list():
    score = X402Client._compute_quality_score([1, 2, 3])
    assert score == 1.0


def test_quality_score_number():
    assert X402Client._compute_quality_score(42) == 0.5


def test_quality_score_bool():
    assert X402Client._compute_quality_score(True) == 0.5


@respx.mock
def test_quality_check_blacklists_on_mismatch():
    """Server claims high quality but response is empty → blacklist."""
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    respx.post("https://x402-api.onrender.com/api/call/empty-svc").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": None,
                "_x402": {"quality_score": 0.9},
            },
        )
    )

    client.call("empty-svc")
    assert client._is_blacklisted("empty-svc") is True


@respx.mock
def test_quality_check_ok():
    """Good quality response should NOT be blacklisted."""
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    respx.post("https://x402-api.onrender.com/api/call/good-svc").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {"joke": "Why did the chicken cross the road?", "id": 123},
                "_x402": {"quality_score": 0.9},
            },
        )
    )

    client.call("good-svc")
    assert client._is_blacklisted("good-svc") is False


# ── Fund Wallet ──────────────────────────────────────────────────────


def test_fund_wallet_skale():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, chain="skale")
    info = client.fund_wallet()
    assert info["network"] == "skale"
    assert info["wallet_address"] == client.wallet_address
    assert "claim_faucet" in str(info["instructions"])


def test_fund_wallet_base():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, chain="base")
    info = client.fund_wallet()
    assert info["network"] == "base"
    assert "bridge.base.org" in str(info["instructions"])


def test_fund_wallet_polygon():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, chain="polygon")
    info = client.fund_wallet()
    assert info["network"] == "polygon"
    assert "EIP-3009" in str(info["instructions"])


def test_fund_wallet_contains_explorer():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, chain="base")
    info = client.fund_wallet()
    assert "basescan.org" in info["explorer"]
    assert client.wallet_address in info["explorer"]

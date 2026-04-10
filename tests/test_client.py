"""Tests for X402Client."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from x402_bazaar.client import X402Client
from x402_bazaar.exceptions import (
    ApiError,
    BudgetExceededError,
    InvalidConfigError,
)

# ── Initialization ───────────────────────────────────────────────────


def test_client_init_auto_wallet():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "wallet.json"
        client = X402Client(wallet_path=path)
        assert client.wallet_address.startswith("0x")
        assert client.network == "skale"
        assert path.exists()


def test_client_init_explicit_key():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)
    assert client.wallet_address.startswith("0x")


def test_client_init_with_chain():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, chain="base")
    assert client.network == "base"


def test_client_init_network_alias():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, network="polygon")
    assert client.network == "polygon"


def test_client_init_invalid_chain():
    with pytest.raises(InvalidConfigError, match="Unsupported chain"):
        X402Client(private_key="0x" + "ab" * 32, chain="ethereum")  # type: ignore


def test_client_init_custom_url():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, base_url="https://custom.api")
    assert client.base_url == "https://custom.api"


def test_client_init_with_budget():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, budget={"max": 5.0, "period": "daily"})
    status = client.get_budget_status()
    assert status.limit == 5.0
    assert status.period == "daily"


def test_client_repr():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, chain="base")
    r = repr(client)
    assert "X402Client" in r
    assert "base" in r


def test_client_from_encrypted():
    from x402_bazaar.wallet import encrypt_wallet, generate_wallet

    wallet = generate_wallet()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "wallet.json"
        encrypt_wallet(wallet.private_key, path, password="test123")
        client = X402Client.from_encrypted(path, password="test123")
        assert client.wallet_address == wallet.address


# ── Context Managers ─────────────────────────────────────────────────


def test_sync_context_manager():
    key = "0x" + "ab" * 32
    with X402Client(private_key=key) as client:
        assert client._sync_client is not None
    assert client._sync_client is None


# ── Search ───────────────────────────────────────────────────────────


@respx.mock
def test_search():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    respx.get("https://x402-api.onrender.com/api/services").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "joke-1",
                        "name": "Joke API",
                        "url": "https://jokes.test",
                        "price_usdc": 0.005,
                        "description": "Get jokes",
                    }
                ]
            },
        )
    )

    results = client.search("joke")
    assert len(results) == 1
    assert results[0].id == "joke-1"
    assert results[0].price_usdc == 0.005


@respx.mock
def test_search_empty():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    respx.get("https://x402-api.onrender.com/api/services").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    results = client.search("nonexistent")
    assert results == []


@respx.mock
def test_search_error():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    respx.get("https://x402-api.onrender.com/api/services").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(ApiError) as exc_info:
        client.search("test")
    assert exc_info.value.status_code == 500


# ── List Services ────────────────────────────────────────────────────


@respx.mock
def test_list_services():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    respx.get("https://x402-api.onrender.com/api/services").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "s1", "name": "S1", "url": "https://s1.test", "price_usdc": 0.01},
                    {"id": "s2", "name": "S2", "url": "https://s2.test", "price_usdc": 0.02},
                ]
            },
        )
    )

    services = client.list_services()
    assert len(services) == 2


# ── Call (free tier) ─────────────────────────────────────────────────


@respx.mock
def test_call_free_tier():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    respx.post("https://x402-api.onrender.com/api/call/joke-api").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "data": {"joke": "Why did the chicken..."}},
            headers={"x-free-tier": "true", "x-free-tier-remaining": "4"},
        )
    )

    result = client.call("joke-api")
    assert result.status == "success"
    assert result.free_tier_used is True
    assert result.data["joke"] == "Why did the chicken..."


# ── Call (with 402 payment) ──────────────────────────────────────────


@respx.mock
def test_call_402_then_success():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, chain="skale")

    # First call returns 402
    route = respx.post("https://x402-api.onrender.com/api/call/weather-api")
    route.side_effect = [
        httpx.Response(
            402,
            json={
                "error": "Payment Required",
                "payment_details": {
                    "amount": 0.01,
                    "currency": "USDC",
                    "network": "skale",
                    "chainId": 1187947933,
                    "recipient": "0xfb1c478BD5567BdcD39782E0D6D23418bFda2430",
                    "networks": [],
                },
            },
        ),
        # After payment, returns success
        httpx.Response(
            200,
            json={"status": "success", "data": {"temp": 15}},
        ),
    ]

    # Mock the payment handler
    with patch.object(client._payment, "pay_sync") as mock_pay:
        from x402_bazaar.types import PaymentResult

        mock_pay.return_value = PaymentResult(
            tx_hash="0xdeadbeef" + "0" * 56,
            explorer="https://explorer.test/tx/0x123",
            from_address=client.wallet_address,
            amount=0.01,
            chain="skale",
        )

        result = client.call("weather-api", params={"city": "Paris"})

    assert result.status == "success"
    assert result.data["temp"] == 15
    assert result.tx_hash is not None
    assert result.payment_amount == 0.01


# ── Call (budget exceeded) ───────────────────────────────────────────


@respx.mock
def test_call_budget_exceeded():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key, budget={"max": 0.005, "period": "daily"})

    respx.post("https://x402-api.onrender.com/api/call/expensive-api").mock(
        return_value=httpx.Response(
            402,
            json={
                "error": "Payment Required",
                "payment_details": {
                    "amount": 0.01,
                    "recipient": "0xabc",
                },
            },
        )
    )

    with pytest.raises(BudgetExceededError):
        client.call("expensive-api")


# ── Blacklist ────────────────────────────────────────────────────────


def test_blacklist():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    client._blacklist["bad-service"] = 9999999999  # far future
    with pytest.raises(ApiError, match="blacklisted"):
        client.call("bad-service")


def test_blacklist_expired():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)
    client._blacklist["old-service"] = 0  # epoch = expired
    assert client._is_blacklisted("old-service") is False


# ── Budget ───────────────────────────────────────────────────────────


def test_set_budget():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)
    client.set_budget(max_daily=10.0)
    status = client.get_budget_status()
    assert status.limit == 10.0
    assert status.period == "daily"


def test_set_budget_weekly():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)
    client.set_budget(max_weekly=50.0)
    status = client.get_budget_status()
    assert status.limit == 50.0
    assert status.period == "weekly"


# ── Health ───────────────────────────────────────────────────────────


@respx.mock
def test_health():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    respx.get("https://x402-api.onrender.com/health").mock(
        return_value=httpx.Response(
            200,
            json={"status": "ok", "version": "3.2.5", "network": "mainnet"},
        )
    )

    health = client.health()
    assert health.status == "ok"
    assert health.version == "3.2.5"


# ── Faucet ───────────────────────────────────────────────────────────


@respx.mock
def test_claim_faucet():
    key = "0x" + "ab" * 32
    client = X402Client(private_key=key)

    respx.post("https://x402-api.onrender.com/api/faucet/claim").mock(
        return_value=httpx.Response(
            200,
            json={"funded": True, "amount": "0.01", "tx_hash": "0xabc"},
        )
    )

    result = client.claim_faucet()
    assert result["funded"] is True

"""Tests for async methods."""

import httpx
import pytest
import respx

from x402_bazaar.client import X402Client
from x402_bazaar.exceptions import ApiError

# ── Async Search ─────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_search_async():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
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
                        }
                    ]
                },
            )
        )

        results = await client.search_async("joke")
        assert len(results) == 1
        assert results[0].id == "joke-1"


@respx.mock
@pytest.mark.asyncio
async def test_search_async_empty():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
        respx.get("https://x402-api.onrender.com/api/services").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        results = await client.search_async("nonexistent")
        assert results == []


@respx.mock
@pytest.mark.asyncio
async def test_search_async_error():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
        respx.get("https://x402-api.onrender.com/api/services").mock(
            return_value=httpx.Response(500, text="Internal Error")
        )
        with pytest.raises(ApiError):
            await client.search_async("test")


# ── Async List Services ──────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_list_services_async():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
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
        services = await client.list_services_async()
        assert len(services) == 2


# ── Async Get Service ────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_service_async():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
        respx.get("https://x402-api.onrender.com/api/services/joke-api").mock(
            return_value=httpx.Response(
                200,
                json={
                    "service": {
                        "id": "joke-api",
                        "name": "Joke API",
                        "url": "https://jokes.test",
                        "price_usdc": 0.005,
                    }
                },
            )
        )
        svc = await client.get_service_async("joke-api")
        assert svc.id == "joke-api"
        assert svc.price_usdc == 0.005


@respx.mock
@pytest.mark.asyncio
async def test_get_service_async_not_found():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
        respx.get("https://x402-api.onrender.com/api/services/nonexistent").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        with pytest.raises(ApiError) as exc_info:
            await client.get_service_async("nonexistent")
        assert exc_info.value.status_code == 404


# ── Async Call (free tier) ───────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_call_async_free_tier():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
        respx.post("https://x402-api.onrender.com/api/call/joke-api").mock(
            return_value=httpx.Response(
                200,
                json={"status": "success", "data": {"joke": "Async joke!"}},
                headers={"x-free-tier": "true"},
            )
        )
        result = await client.call_async("joke-api")
        assert result.status == "success"
        assert result.free_tier_used is True
        assert result.data["joke"] == "Async joke!"


# ── Async Call (402 with payment) ────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_call_async_402():
    from unittest.mock import AsyncMock, patch

    from x402_bazaar.types import PaymentResult

    key = "0x" + "ab" * 32
    async with X402Client(private_key=key, chain="skale") as client:
        route = respx.post("https://x402-api.onrender.com/api/call/weather")
        route.side_effect = [
            httpx.Response(
                402,
                json={
                    "error": "Payment Required",
                    "payment_details": {
                        "amount": 0.01,
                        "recipient": "0xabc",
                        "networks": [],
                    },
                },
            ),
            httpx.Response(200, json={"status": "success", "data": {"temp": 20}}),
        ]

        with patch.object(client._payment, "pay", new_callable=AsyncMock) as mock_pay:
            mock_pay.return_value = PaymentResult(
                tx_hash="0x" + "ff" * 32,
                explorer="https://explorer/tx/0xfff",
                from_address=client.wallet_address,
                amount=0.01,
                chain="skale",
            )
            result = await client.call_async("weather", params={"city": "Paris"})

        assert result.status == "success"
        assert result.data["temp"] == 20
        assert result.tx_hash is not None
        assert result.payment_amount == 0.01


# ── Async Health ─────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_health_async():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
        respx.get("https://x402-api.onrender.com/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "version": "3.2.5"})
        )
        health = await client.health_async()
        assert health.status == "ok"
        assert health.version == "3.2.5"


# ── Async Fund Wallet ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fund_wallet_async():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key, chain="base") as client:
        info = await client.fund_wallet_async()
        assert info["network"] == "base"
        assert info["wallet_address"] == client.wallet_address


# ── Async Faucet ────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_claim_faucet_async():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
        respx.post("https://x402-api.onrender.com/api/faucet/claim").mock(
            return_value=httpx.Response(
                200,
                json={"funded": True, "amount": "0.01", "tx_hash": "0xabc"},
            )
        )
        result = await client.claim_faucet_async()
        assert result["funded"] is True
        assert result["amount"] == "0.01"


# ── Async Context Manager ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_context_manager():
    key = "0x" + "ab" * 32
    async with X402Client(private_key=key) as client:
        assert client._async_client is not None
    assert client._async_client is None

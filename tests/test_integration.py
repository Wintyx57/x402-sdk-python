"""Integration tests against the real x402 Bazaar backend.

Run with: pytest tests/test_integration.py -m integration -v
"""

import pytest

from x402_bazaar.client import X402Client


@pytest.fixture
def live_client():
    """Client with auto-generated wallet for live tests."""
    return X402Client(chain="skale")


@pytest.mark.integration
def test_health_live(live_client: X402Client):
    """Backend should be healthy."""
    health = live_client.health()
    assert health.status == "ok"
    assert health.version  # non-empty


@pytest.mark.integration
def test_search_live(live_client: X402Client):
    """Search should return results for common queries."""
    results = live_client.search("joke")
    assert len(results) > 0
    assert results[0].id  # has an ID
    assert results[0].name  # has a name
    assert results[0].price_usdc >= 0  # has a price


@pytest.mark.integration
def test_search_multiple_queries(live_client: X402Client):
    """Search across different categories."""
    for query in ["weather", "translation", "ai"]:
        results = live_client.search(query)
        # At least some queries should return results
        # (not all queries guaranteed to match)
        assert isinstance(results, list)


@pytest.mark.integration
def test_list_services_live(live_client: X402Client):
    """Should list services with pagination."""
    services = live_client.list_services(page=1, limit=10)
    assert len(services) > 0
    assert len(services) <= 10
    for svc in services:
        assert svc.id
        assert svc.url


@pytest.mark.integration
def test_list_services_pagination(live_client: X402Client):
    """Page 1 and page 2 should return different services."""
    page1 = live_client.list_services(page=1, limit=5)
    page2 = live_client.list_services(page=2, limit=5)
    if len(page2) > 0:
        ids1 = {s.id for s in page1}
        ids2 = {s.id for s in page2}
        assert ids1 != ids2  # Different pages


@pytest.mark.integration
def test_fund_wallet_live(live_client: X402Client):
    """Fund wallet instructions should be valid."""
    info = live_client.fund_wallet()
    assert info["network"] == "skale"
    assert info["wallet_address"] == live_client.wallet_address
    assert len(info["instructions"]) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_async_live():
    """Async search should work against real backend."""
    async with X402Client(chain="skale") as client:
        results = await client.search_async("joke")
        assert len(results) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_async_live():
    """Async health should work."""
    async with X402Client(chain="skale") as client:
        health = await client.health_async()
        assert health.status == "ok"


@pytest.mark.integration
def test_call_free_tier_live(live_client: X402Client):
    """Call a service via free tier (no payment needed)."""
    from x402_bazaar.exceptions import InsufficientBalanceError, PaymentError

    services = live_client.search("joke")
    if not services:
        pytest.skip("No joke services found")

    try:
        result = live_client.call(services[0].id)
        assert result.status == "success"
        assert result.data is not None
    except (InsufficientBalanceError, PaymentError):
        pass  # Expected — free tier exhausted, wallet has no funds
    except Exception as e:
        if "402" in str(e) or "Payment" in str(e):
            pass
        else:
            raise

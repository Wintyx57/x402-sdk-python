"""Tests for Pydantic models."""

from x402_bazaar.types import (
    BudgetStatus,
    CallResult,
    FreeTierInfo,
    HealthResponse,
    NetworkInfo,
    PaymentDetails,
    PaymentResponse,
    PaymentResult,
    ServiceInfo,
    SplitInfo,
    WalletInfo,
)


def test_service_info_minimal():
    svc = ServiceInfo(id="test", name="Test", url="https://test.com", price_usdc=0.01)
    assert svc.id == "test"
    assert svc.tags == []
    assert svc.has_credentials is False


def test_service_info_full():
    svc = ServiceInfo(
        id="weather",
        name="Weather API",
        url="https://weather.com/api",
        price_usdc=0.05,
        description="Get weather data",
        tags=["weather", "data"],
        verified_status="verified",
        category="data",
        trust_score=95.5,
        payment_protocol="x402-bazaar",
    )
    assert svc.trust_score == 95.5
    assert len(svc.tags) == 2


def test_payment_details():
    pd = PaymentDetails(
        amount=0.01,
        currency="USDC",
        network="base",
        chainId=8453,
        recipient="0xfb1c478BD5567BdcD39782E0D6D23418bFda2430",
        networks=[
            NetworkInfo(network="base", chainId=8453, label="Base"),
            NetworkInfo(network="skale", chainId=1187947933, label="SKALE"),
        ],
    )
    assert pd.amount == 0.01
    assert len(pd.networks) == 2


def test_payment_response_parse():
    raw = {
        "error": "Payment Required",
        "message": "This action costs 0.01 USDC",
        "payment_details": {
            "amount": 0.01,
            "currency": "USDC",
            "network": "base",
            "chainId": 8453,
            "recipient": "0xabc",
            "networks": [],
            "accepted": ["USDC"],
        },
    }
    pr = PaymentResponse(**raw)
    assert pr.payment_details.amount == 0.01
    assert pr.payment_details.recipient == "0xabc"


def test_call_result_defaults():
    cr = CallResult()
    assert cr.status == "success"
    assert cr.data is None
    assert cr.tx_hash is None
    assert cr.free_tier_used is False


def test_call_result_with_payment():
    cr = CallResult(
        data={"joke": "Why did the chicken..."},
        tx_hash="0x123",
        payment_amount=0.01,
        chain="base",
    )
    assert cr.tx_hash == "0x123"
    assert cr.payment_amount == 0.01


def test_budget_status():
    bs = BudgetStatus(spent=3.5, limit=10, remaining=6.5, period="daily", call_count=7)
    assert bs.remaining == 6.5
    assert bs.call_count == 7


def test_wallet_info():
    wi = WalletInfo(private_key="0xabc", address="0x123", is_new=True)
    assert wi.is_new is True


def test_health_response():
    hr = HealthResponse(status="ok", version="3.2.5")
    assert hr.status == "ok"


def test_payment_result():
    pr = PaymentResult(
        tx_hash="0xdeadbeef",
        explorer="https://basescan.org/tx/0xdeadbeef",
        from_address="0x123",
        amount=0.05,
        chain="base",
    )
    assert pr.chain == "base"


def test_split_info():
    si = SplitInfo(provider_amount=0.0095, platform_amount=0.0005)
    assert si.provider_percent == 95


def test_free_tier_info():
    ft = FreeTierInfo(exhausted=True, reason="daily_limit_reached", limit=5)
    assert ft.exhausted is True


def test_network_info_with_facilitator():
    ni = NetworkInfo(
        network="polygon",
        chainId=137,
        label="Polygon",
        facilitator="https://facilitator.example.com",
    )
    assert ni.facilitator is not None


def test_service_info_from_dict():
    """Simulate parsing from API response."""
    raw = {
        "id": "joke-api",
        "name": "Joke API",
        "url": "https://jokes.com",
        "price_usdc": 0.005,
        "tags": ["humor"],
        "status": "online",
        "extra_field": "should be ignored",
    }
    svc = ServiceInfo(**{k: v for k, v in raw.items() if k in ServiceInfo.model_fields})
    assert svc.id == "joke-api"

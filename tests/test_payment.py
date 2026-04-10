"""Tests for payment handler."""

import httpx
import respx

from x402_bazaar.payment import PaymentHandler, parse_402_response
from x402_bazaar.types import NetworkInfo, PaymentDetails


def test_payment_handler_init():
    key = "0x" + "ab" * 32
    handler = PaymentHandler(key, "base")
    assert handler.address.startswith("0x")
    assert handler.network == "base"
    assert handler.chain_config.chain_id == 8453


def test_payment_handler_skale():
    key = "0x" + "cd" * 32
    handler = PaymentHandler(key, "skale")
    assert handler.chain_config.usdc_decimals == 18


def test_should_use_facilitator_polygon():
    key = "0x" + "ab" * 32
    handler = PaymentHandler(key, "polygon")
    details = PaymentDetails(
        amount=0.01,
        networks=[
            NetworkInfo(
                network="polygon",
                chainId=137,
                label="Polygon",
                facilitator="https://facilitator.test",
            )
        ],
    )
    assert handler.should_use_facilitator(details) is True


def test_should_not_use_facilitator_base():
    key = "0x" + "ab" * 32
    handler = PaymentHandler(key, "base")
    details = PaymentDetails(amount=0.01, networks=[])
    assert handler.should_use_facilitator(details) is False


def test_should_not_use_facilitator_no_url():
    key = "0x" + "ab" * 32
    handler = PaymentHandler(key, "polygon")
    details = PaymentDetails(
        amount=0.01,
        networks=[NetworkInfo(network="polygon", chainId=137, label="Polygon")],
    )
    assert handler.should_use_facilitator(details) is False


def test_get_facilitator_url():
    key = "0x" + "ab" * 32
    handler = PaymentHandler(key, "polygon")
    details = PaymentDetails(
        amount=0.01,
        networks=[
            NetworkInfo(
                network="polygon",
                chainId=137,
                label="Polygon",
                facilitator="https://facil.test",
            )
        ],
    )
    assert handler.get_facilitator_url(details) == "https://facil.test"


def test_get_facilitator_url_none():
    key = "0x" + "ab" * 32
    handler = PaymentHandler(key, "base")
    details = PaymentDetails(amount=0.01, networks=[])
    assert handler.get_facilitator_url(details) is None


def test_parse_402_response_valid():
    resp = httpx.Response(
        402,
        json={
            "error": "Payment Required",
            "message": "Pay 0.01",
            "payment_details": {
                "amount": 0.01,
                "currency": "USDC",
                "recipient": "0xabc",
                "networks": [],
            },
        },
    )
    result = parse_402_response(resp)
    assert result is not None
    assert result.payment_details.amount == 0.01


def test_parse_402_response_not_402():
    resp = httpx.Response(200, json={"ok": True})
    assert parse_402_response(resp) is None


def test_parse_402_response_invalid_json():
    resp = httpx.Response(402, text="not json")
    result = parse_402_response(resp)
    assert result is None


def test_parse_402_with_free_tier():
    resp = httpx.Response(
        402,
        json={
            "error": "Payment Required",
            "payment_details": {
                "amount": 0.01,
                "recipient": "0xabc",
            },
            "free_tier": {
                "exhausted": True,
                "reason": "daily_limit_reached",
                "limit": 5,
            },
        },
    )
    result = parse_402_response(resp)
    assert result is not None
    assert result.free_tier is not None
    assert result.free_tier.exhausted is True


def test_parse_402_with_split():
    resp = httpx.Response(
        402,
        json={
            "error": "Payment Required",
            "payment_details": {
                "amount": 0.01,
                "recipient": "0xabc",
                "split": {
                    "provider_amount": 0.0095,
                    "platform_amount": 0.0005,
                    "provider_percent": 95,
                    "platform_percent": 5,
                },
            },
        },
    )
    result = parse_402_response(resp)
    assert result.payment_details.split.provider_amount == 0.0095


def test_parse_402_with_extensions():
    resp = httpx.Response(
        402,
        json={
            "error": "Payment Required",
            "payment_details": {"amount": 0.01, "recipient": "0xabc"},
            "extensions": {
                "inputSchema": {"required": ["city"], "properties": {"city": {"type": "string"}}},
            },
        },
    )
    result = parse_402_response(resp)
    assert result.extensions["inputSchema"]["required"] == ["city"]


@respx.mock
def test_get_balance():
    key = "0x" + "ab" * 32
    handler = PaymentHandler(key, "base")
    respx.post("https://mainnet.base.org").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "result": hex(5_000_000), "id": 1})
    )
    balance = handler.get_balance_sync()
    assert balance == 5.0

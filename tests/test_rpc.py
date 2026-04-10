"""Tests for RPC client."""

import httpx
import pytest
import respx

from x402_bazaar._rpc import RpcClient, encode_transfer
from x402_bazaar.exceptions import NetworkError


@respx.mock
def test_get_balance():
    """Test USDC balance fetch."""
    rpc = RpcClient(["https://rpc1.test"])

    # 1000000 = 1.0 USDC (6 decimals)
    respx.post("https://rpc1.test").mock(
        return_value=httpx.Response(
            200,
            json={"jsonrpc": "2.0", "result": hex(1_000_000), "id": 1},
        )
    )

    balance = rpc.get_balance_sync(
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "0x1234567890123456789012345678901234567890",
        6,
    )
    assert balance == 1.0


@respx.mock
def test_get_balance_zero():
    rpc = RpcClient(["https://rpc1.test"])
    respx.post("https://rpc1.test").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "result": "0x", "id": 1})
    )
    balance = rpc.get_balance_sync("0xabc", "0xdef", 6)
    assert balance == 0.0


@respx.mock
def test_get_balance_18_decimals():
    """SKALE USDC has 18 decimals."""
    rpc = RpcClient(["https://rpc1.test"])
    # 1e18 = 1.0 USDC
    respx.post("https://rpc1.test").mock(
        return_value=httpx.Response(
            200,
            json={"jsonrpc": "2.0", "result": hex(10**18), "id": 1},
        )
    )
    balance = rpc.get_balance_sync("0xabc", "0xdef", 18)
    assert balance == 1.0


@respx.mock
def test_rpc_fallback():
    """Should try second URL if first fails."""
    rpc = RpcClient(["https://rpc1.test", "https://rpc2.test"])

    respx.post("https://rpc1.test").mock(side_effect=httpx.ConnectError("down"))
    respx.post("https://rpc2.test").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "result": hex(500_000), "id": 1})
    )

    balance = rpc.get_balance_sync("0xabc", "0xdef", 6)
    assert balance == 0.5


@respx.mock
def test_rpc_all_fail():
    rpc = RpcClient(["https://rpc1.test", "https://rpc2.test"])
    respx.post("https://rpc1.test").mock(side_effect=httpx.ConnectError("down"))
    respx.post("https://rpc2.test").mock(side_effect=httpx.ConnectError("down"))

    with pytest.raises(NetworkError, match="All RPC URLs failed"):
        rpc.get_balance_sync("0xabc", "0xdef", 6)


@respx.mock
def test_rpc_error_response():
    rpc = RpcClient(["https://rpc1.test"])
    respx.post("https://rpc1.test").mock(
        return_value=httpx.Response(
            200, json={"jsonrpc": "2.0", "error": {"code": -32000, "message": "fail"}, "id": 1}
        )
    )
    with pytest.raises(NetworkError, match="RPC error"):
        rpc.get_balance_sync("0xabc", "0xdef", 6)


@respx.mock
def test_get_transaction_count():
    rpc = RpcClient(["https://rpc1.test"])
    respx.post("https://rpc1.test").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "result": "0xa", "id": 1})
    )
    nonce = rpc.get_transaction_count_sync("0xabc")
    assert nonce == 10


def test_encode_transfer():
    result = encode_transfer("0x1234567890123456789012345678901234567890", 1_000_000)
    assert result.startswith("0xa9059cbb")
    assert len(result) == 10 + 64 + 64  # selector + address + amount


def test_encode_transfer_large_amount():
    result = encode_transfer("0xabc", 10**18)
    assert "0xa9059cbb" in result


@respx.mock
def test_send_raw_transaction():
    rpc = RpcClient(["https://rpc1.test"])
    tx_hash = "0xdeadbeef" + "0" * 56
    respx.post("https://rpc1.test").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "result": tx_hash, "id": 1})
    )
    result = rpc.send_raw_transaction_sync("0xsignedtx")
    assert result == tx_hash


def test_rpc_client_timeout():
    rpc = RpcClient(["https://rpc1.test"], timeout=5)
    assert rpc.timeout == 5


def test_rpc_request_id_increments():
    rpc = RpcClient(["https://rpc1.test"])
    assert rpc._next_id() == 1
    assert rpc._next_id() == 2
    assert rpc._next_id() == 3

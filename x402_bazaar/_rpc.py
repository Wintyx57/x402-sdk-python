"""Minimal JSON-RPC client — no web3.py dependency."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from x402_bazaar._abi import BALANCE_OF_SELECTOR, TRANSFER_SELECTOR
from x402_bazaar.exceptions import NetworkError

logger = logging.getLogger("x402_bazaar.rpc")


class RpcClient:
    """Lightweight Ethereum JSON-RPC client with fallback URLs."""

    def __init__(self, rpc_urls: list[str], timeout: float = 10) -> None:
        self.rpc_urls = rpc_urls
        self.timeout = timeout
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _call_rpc(
        self, method: str, params: list[Any], *, client: httpx.AsyncClient | None = None
    ) -> Any:
        """Call JSON-RPC method with fallback across RPC URLs."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._next_id(),
        }

        last_error: Exception | None = None
        should_close = False

        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)
            should_close = True

        try:
            for url in self.rpc_urls:
                try:
                    resp = await client.post(url, json=payload)
                    data = resp.json()
                    if "error" in data:
                        raise NetworkError(f"RPC error: {data['error']}")
                    return data.get("result")
                except (httpx.HTTPError, KeyError) as e:
                    last_error = e
                    logger.debug("RPC %s failed: %s, trying next", url, e)
                    continue
        finally:
            if should_close:
                await client.aclose()

        raise NetworkError(f"All RPC URLs failed: {last_error}", cause=last_error)

    def _call_rpc_sync(
        self, method: str, params: list[Any], *, client: httpx.Client | None = None
    ) -> Any:
        """Synchronous version of _call_rpc."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._next_id(),
        }

        last_error: Exception | None = None
        should_close = False

        if client is None:
            client = httpx.Client(timeout=self.timeout)
            should_close = True

        try:
            for url in self.rpc_urls:
                try:
                    resp = client.post(url, json=payload)
                    data = resp.json()
                    if "error" in data:
                        raise NetworkError(f"RPC error: {data['error']}")
                    return data.get("result")
                except (httpx.HTTPError, KeyError) as e:
                    last_error = e
                    logger.debug("RPC %s failed: %s, trying next", url, e)
                    continue
        finally:
            if should_close:
                client.close()

        raise NetworkError(f"All RPC URLs failed: {last_error}", cause=last_error)

    async def get_balance(
        self,
        token_contract: str,
        wallet_address: str,
        decimals: int = 6,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> float:
        """Get ERC-20 token balance."""
        # Encode balanceOf(address) call
        address_padded = wallet_address.lower().replace("0x", "").zfill(64)
        call_data = BALANCE_OF_SELECTOR + address_padded

        result = await self._call_rpc(
            "eth_call",
            [{"to": token_contract, "data": call_data}, "latest"],
            client=client,
        )

        if not result or result == "0x":
            return 0.0
        raw_balance = int(str(result), 16)
        return float(raw_balance / (10**decimals))

    def get_balance_sync(
        self,
        token_contract: str,
        wallet_address: str,
        decimals: int = 6,
        *,
        client: httpx.Client | None = None,
    ) -> float:
        """Synchronous version of get_balance."""
        address_padded = wallet_address.lower().replace("0x", "").zfill(64)
        call_data = BALANCE_OF_SELECTOR + address_padded

        result = self._call_rpc_sync(
            "eth_call",
            [{"to": token_contract, "data": call_data}, "latest"],
            client=client,
        )

        if not result or result == "0x":
            return 0.0
        raw_balance = int(str(result), 16)
        return float(raw_balance / (10**decimals))

    async def get_transaction_count(
        self, address: str, *, client: httpx.AsyncClient | None = None
    ) -> int:
        """Get nonce for address."""
        result = await self._call_rpc(
            "eth_getTransactionCount",
            [address, "latest"],
            client=client,
        )
        return int(str(result), 16)

    def get_transaction_count_sync(
        self, address: str, *, client: httpx.Client | None = None
    ) -> int:
        """Synchronous nonce."""
        result = self._call_rpc_sync(
            "eth_getTransactionCount",
            [address, "latest"],
            client=client,
        )
        return int(str(result), 16)

    async def get_gas_price(self, *, client: httpx.AsyncClient | None = None) -> int:
        """Get current gas price in wei."""
        result = await self._call_rpc("eth_gasPrice", [], client=client)
        return int(str(result), 16)

    async def send_raw_transaction(
        self, signed_tx: str, *, client: httpx.AsyncClient | None = None
    ) -> str:
        """Broadcast signed transaction, return tx hash."""
        result = await self._call_rpc(
            "eth_sendRawTransaction",
            [signed_tx],
            client=client,
        )
        return str(result)

    def send_raw_transaction_sync(
        self, signed_tx: str, *, client: httpx.Client | None = None
    ) -> str:
        """Synchronous broadcast."""
        result = self._call_rpc_sync(
            "eth_sendRawTransaction",
            [signed_tx],
            client=client,
        )
        return str(result)

    async def wait_for_receipt(
        self,
        tx_hash: str,
        *,
        confirmations: int = 1,
        max_retries: int = 30,
        delay: float = 2.0,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Wait for transaction receipt with confirmations."""
        import asyncio

        for _ in range(max_retries):
            result = await self._call_rpc("eth_getTransactionReceipt", [tx_hash], client=client)
            if result is not None:
                status = int(result.get("status", "0x0"), 16)
                if status == 0:
                    raise NetworkError(f"Transaction reverted: {tx_hash}")
                if confirmations <= 1:
                    return dict(result)
                # Check block confirmations
                block_number = int(result["blockNumber"], 16)
                latest = await self._call_rpc("eth_blockNumber", [], client=client)
                current_block = int(latest, 16)
                if current_block - block_number >= confirmations - 1:
                    return result
            await asyncio.sleep(delay)

        raise NetworkError(f"Transaction not confirmed after {max_retries} retries: {tx_hash}")


def encode_transfer(to: str, amount_raw: int) -> str:
    """Encode ERC-20 transfer(address, uint256) call data."""
    to_padded = to.lower().replace("0x", "").zfill(64)
    amount_hex = hex(amount_raw)[2:].zfill(64)
    return TRANSFER_SELECTOR + to_padded + amount_hex

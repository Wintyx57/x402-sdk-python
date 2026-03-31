"""Payment handler — USDC transfers, EIP-3009 signing, 402 detection."""

from __future__ import annotations

import logging
import os
import secrets
import time

import httpx
from eth_account import Account
from eth_account.messages import encode_typed_data

from x402_bazaar._rpc import RpcClient, encode_transfer
from x402_bazaar.chains import (
    CHAINS,
    POLYGON_EIP712_DOMAIN,
    TRANSFER_WITH_AUTHORIZATION_TYPES,
    Network,
)
from x402_bazaar.exceptions import (
    InsufficientBalanceError,
    NetworkError,
    PaymentError,
)
from x402_bazaar.types import PaymentDetails, PaymentResponse, PaymentResult

logger = logging.getLogger("x402_bazaar.payment")


class PaymentHandler:
    """Handles USDC payments across multiple chains."""

    def __init__(self, private_key: str, network: Network) -> None:
        self.private_key = private_key
        self.network = network
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        self.chain_config = CHAINS[network]
        self.rpc = RpcClient(self.chain_config.rpc_urls)

    # ── Balance ──────────────────────────────────────────────────────

    async def get_balance(self, *, client: httpx.AsyncClient | None = None) -> float:
        """Get USDC balance on configured chain."""
        return await self.rpc.get_balance(
            self.chain_config.usdc_contract,
            self.address,
            self.chain_config.usdc_decimals,
            client=client,
        )

    def get_balance_sync(self, *, client: httpx.Client | None = None) -> float:
        """Synchronous balance check."""
        return self.rpc.get_balance_sync(
            self.chain_config.usdc_contract,
            self.address,
            self.chain_config.usdc_decimals,
            client=client,
        )

    # ── Direct USDC Transfer ─────────────────────────────────────────

    async def send_usdc(
        self,
        to: str,
        amount_usdc: float,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> PaymentResult:
        """Send USDC via on-chain transfer."""
        amount_raw = int(amount_usdc * (10**self.chain_config.usdc_decimals))
        call_data = encode_transfer(to, amount_raw)

        # Get nonce and gas price
        nonce = await self.rpc.get_transaction_count(self.address, client=client)
        gas_price = await self.rpc.get_gas_price(client=client)

        tx = {
            "to": self.chain_config.usdc_contract,
            "data": bytes.fromhex(call_data[2:]) if call_data.startswith("0x") else bytes.fromhex(call_data),
            "gas": 100_000,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": self.chain_config.chain_id,
            "value": 0,
        }

        signed = self.account.sign_transaction(tx)
        raw_tx = signed.raw_transaction
        if isinstance(raw_tx, bytes):
            raw_tx_hex = "0x" + raw_tx.hex()
        else:
            raw_tx_hex = raw_tx

        tx_hash = await self.rpc.send_raw_transaction(raw_tx_hex, client=client)
        logger.info("USDC transfer sent: %s (%.6f USDC to %s)", tx_hash, amount_usdc, to)

        # Wait for confirmation
        await self.rpc.wait_for_receipt(
            tx_hash,
            confirmations=self.chain_config.confirmations,
            client=client,
        )

        return PaymentResult(
            tx_hash=tx_hash,
            explorer=f"{self.chain_config.explorer}/tx/{tx_hash}",
            from_address=self.address,
            amount=amount_usdc,
            chain=self.network,
        )

    def send_usdc_sync(
        self,
        to: str,
        amount_usdc: float,
        *,
        client: httpx.Client | None = None,
    ) -> PaymentResult:
        """Synchronous USDC transfer."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.send_usdc(to, amount_usdc, client=None)
        )

    # ── EIP-3009 Gas-Free (Polygon) ─────────────────────────────────

    async def send_via_facilitator(
        self,
        to: str,
        amount_usdc: float,
        facilitator_url: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> PaymentResult:
        """Send USDC via EIP-3009 (gas-free on Polygon)."""
        amount_raw = int(amount_usdc * (10**self.chain_config.usdc_decimals))

        # Generate random nonce (32 bytes)
        nonce = "0x" + secrets.token_hex(32)
        valid_after = 0
        valid_before = int(time.time()) + 300  # 5 minutes

        # Build EIP-712 typed data
        message = {
            "from": self.address,
            "to": to,
            "value": amount_raw,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": bytes.fromhex(nonce[2:]),
        }

        # Sign typed data (EIP-712)
        signable = encode_typed_data(
            domain_data=POLYGON_EIP712_DOMAIN,
            message_types=TRANSFER_WITH_AUTHORIZATION_TYPES,
            message_data=message,
        )
        signed = self.account.sign_message(signable)
        signature = signed.signature.hex() if isinstance(signed.signature, bytes) else str(signed.signature)
        if not signature.startswith("0x"):
            signature = "0x" + signature

        # Build facilitator payload
        payload = {
            "x402Version": 1,
            "paymentPayload": {
                "x402Version": 1,
                "scheme": "exact",
                "network": self.network,
                "payload": {
                    "signature": signature,
                    "authorization": {
                        "from": self.address,
                        "to": to,
                        "value": str(amount_raw),
                        "validAfter": str(valid_after),
                        "validBefore": str(valid_before),
                        "nonce": nonce,
                    },
                },
            },
            "paymentRequirements": {
                "scheme": "exact",
                "network": self.network,
                "maxAmountRequired": str(amount_raw),
                "resource": "x402-sdk-payment",
                "description": "x402 Bazaar API payment",
                "mimeType": "application/json",
                "payTo": to,
                "asset": self.chain_config.usdc_contract,
                "maxTimeoutSeconds": 60,
            },
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=30)
            should_close = True

        try:
            settle_url = facilitator_url.rstrip("/") + "/settle"
            resp = await client.post(settle_url, json=payload)

            if resp.status_code != 200:
                raise PaymentError(
                    f"Facilitator returned {resp.status_code}: {resp.text}",
                    amount=amount_usdc,
                    recipient=to,
                )

            data = resp.json()
            tx_hash = data.get("txHash") or data.get("tx_hash") or data.get("transactionHash", "")

            logger.info(
                "EIP-3009 payment via facilitator: %s (%.6f USDC to %s)",
                tx_hash, amount_usdc, to,
            )

            return PaymentResult(
                tx_hash=tx_hash,
                explorer=f"{self.chain_config.explorer}/tx/{tx_hash}",
                from_address=self.address,
                amount=amount_usdc,
                chain=self.network,
            )
        finally:
            if should_close:
                await client.aclose()

    # ── 402 Payment Flow ─────────────────────────────────────────────

    def should_use_facilitator(self, details: PaymentDetails) -> bool:
        """Check if EIP-3009 facilitator should be used."""
        if self.network != "polygon":
            return False
        # Check if any network in the 402 response has a facilitator
        for net in details.networks:
            if net.network == "polygon" and net.facilitator:
                return True
        return False

    def get_facilitator_url(self, details: PaymentDetails) -> str | None:
        """Get facilitator URL from payment details."""
        for net in details.networks:
            if net.network == self.network and net.facilitator:
                return net.facilitator
        return None

    async def pay(
        self,
        details: PaymentDetails,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> PaymentResult:
        """Execute payment based on 402 details."""
        amount = details.amount
        recipient = details.recipient

        if not recipient:
            raise PaymentError("No payment recipient in 402 response", amount=amount)

        # Check balance
        balance = await self.get_balance(client=client)
        if balance < amount:
            raise InsufficientBalanceError(balance, amount)

        # Try facilitator (gas-free) first
        facilitator_url = self.get_facilitator_url(details)
        if facilitator_url and self.should_use_facilitator(details):
            return await self.send_via_facilitator(
                recipient, amount, facilitator_url, client=client
            )

        # Direct transfer
        return await self.send_usdc(recipient, amount, client=client)

    def pay_sync(self, details: PaymentDetails) -> PaymentResult:
        """Synchronous payment."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run, self.pay(details)
                ).result()
        else:
            return asyncio.run(self.pay(details))


def parse_402_response(response: httpx.Response) -> PaymentResponse | None:
    """Parse a 402 response into PaymentResponse, or None if not 402."""
    if response.status_code != 402:
        return None
    try:
        data = response.json()
        return PaymentResponse(**data)
    except Exception:
        logger.warning("Failed to parse 402 response body")
        return None

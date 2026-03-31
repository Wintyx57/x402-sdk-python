"""X402Client — main entry point for the SDK."""

from __future__ import annotations

import hashlib
import hmac
import json as json_module
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from x402_bazaar.budget import BudgetConfig, BudgetTracker
from x402_bazaar.chains import (
    BLACKLIST_TTL,
    CHAINS,
    DEFAULT_BASE_URL,
    DEFAULT_NETWORK,
    DEFAULT_TIMEOUT,
    Network,
)
from x402_bazaar.exceptions import (
    ApiError,
    InvalidConfigError,
    TimeoutError,
)
from x402_bazaar.payment import PaymentHandler, parse_402_response
from x402_bazaar.types import (
    BudgetStatus,
    CallResult,
    HealthResponse,
    ServiceInfo,
)
from x402_bazaar.wallet import load_or_create_wallet

logger = logging.getLogger("x402_bazaar")


class X402Client:
    """x402 Bazaar SDK client with auto-payment.

    Usage:
        # Zero-config (auto wallet on SKALE)
        client = X402Client()
        data = client.call("weather-api", params={"city": "Paris"})

        # Explicit config
        client = X402Client(private_key="0x...", chain="base", budget={"max": 5, "period": "daily"})

        # From encrypted wallet
        client = X402Client.from_encrypted("wallet.json", password="secret")

        # Async
        async with X402Client() as client:
            data = await client.call_async("service-id")
    """

    def __init__(
        self,
        *,
        private_key: str | None = None,
        chain: Network | None = None,
        network: Network | None = None,  # alias
        base_url: str | None = None,
        budget: dict[str, Any] | BudgetConfig | None = None,
        timeout: int | float | None = None,
        wallet_path: str | Path | None = None,
        password: str | None = None,
        validation_secret: str | None = None,
    ) -> None:
        # Resolve network
        self._network: Network = chain or network or DEFAULT_NETWORK
        if self._network not in CHAINS:
            raise InvalidConfigError(f"Unsupported chain: {self._network}")

        # Load or create wallet
        wallet = load_or_create_wallet(wallet_path, private_key=private_key, password=password)
        self._private_key = wallet.private_key
        self._address = wallet.address
        self._is_new_wallet = wallet.is_new

        if wallet.is_new:
            logger.info("New wallet generated: %s (chain: %s)", self._address, self._network)

        # Config
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout or DEFAULT_TIMEOUT

        # Payment handler
        self._payment = PaymentHandler(self._private_key, self._network)

        # Budget
        if isinstance(budget, dict):
            self._budget = BudgetTracker(
                config=BudgetConfig(
                    max=budget.get("max", float("inf")),
                    period=budget.get("period", "daily"),
                )
            )
        elif isinstance(budget, BudgetConfig):
            self._budget = BudgetTracker(config=budget)
        else:
            self._budget = BudgetTracker()

        # Validation
        self._validation_secret = validation_secret

        # Service blacklist
        self._blacklist: dict[str, float] = {}

        # HTTP clients (lazy)
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    @classmethod
    def from_encrypted(
        cls,
        path: str | Path,
        *,
        password: str | None = None,
        **kwargs: Any,
    ) -> X402Client:
        """Create client from encrypted wallet file."""
        from x402_bazaar.wallet import decrypt_wallet

        wallet = decrypt_wallet(path, password=password)
        return cls(private_key=wallet.private_key, **kwargs)

    # ── Properties ───────────────────────────────────────────────────

    @property
    def wallet_address(self) -> str:
        return self._address

    @property
    def network(self) -> Network:
        return self._network

    @property
    def base_url(self) -> str:
        return self._base_url

    # ── Context Manager ──────────────────────────────────────────────

    async def __aenter__(self) -> X402Client:
        self._async_client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    def __enter__(self) -> X402Client:
        self._sync_client = httpx.Client(timeout=self._timeout)
        return self

    def __exit__(self, *args: Any) -> None:
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    # ── HTTP Helpers ─────────────────────────────────────────────────

    def _get_sync_client(self) -> httpx.Client:
        if self._sync_client is None:
            self._sync_client = httpx.Client(timeout=self._timeout)
        return self._sync_client

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self._timeout)
        return self._async_client

    def _is_blacklisted(self, service_id: str) -> bool:
        ts = self._blacklist.get(service_id)
        if ts is None:
            return False
        if time.time() - ts > BLACKLIST_TTL:
            del self._blacklist[service_id]
            return False
        return True

    # ── Search ───────────────────────────────────────────────────────

    def search(self, query: str, *, limit: int = 50) -> list[ServiceInfo]:
        """Search services by keyword."""
        client = self._get_sync_client()
        try:
            resp = client.get(
                f"{self._base_url}/api/services",
                params={"search": query, "limit": limit},
            )
        except httpx.TimeoutException:
            raise TimeoutError(f"/api/services?search={query}", int(self._timeout * 1000))

        if resp.status_code != 200:
            raise ApiError(resp.text, resp.status_code, "/api/services")

        data = resp.json()
        services = data.get("data", data.get("services", []))
        return [ServiceInfo(**s) for s in services]

    async def search_async(self, query: str, *, limit: int = 50) -> list[ServiceInfo]:
        """Async search."""
        client = self._get_async_client()
        try:
            resp = await client.get(
                f"{self._base_url}/api/services",
                params={"search": query, "limit": limit},
            )
        except httpx.TimeoutException:
            raise TimeoutError(f"/api/services?search={query}", int(self._timeout * 1000))

        if resp.status_code != 200:
            raise ApiError(resp.text, resp.status_code, "/api/services")

        data = resp.json()
        services = data.get("data", data.get("services", []))
        return [ServiceInfo(**s) for s in services]

    # ── List Services ────────────────────────────────────────────────

    def list_services(self, *, page: int = 1, limit: int = 50) -> list[ServiceInfo]:
        """List all services with pagination."""
        client = self._get_sync_client()
        resp = client.get(
            f"{self._base_url}/api/services",
            params={"page": page, "limit": limit},
        )
        if resp.status_code != 200:
            raise ApiError(resp.text, resp.status_code, "/api/services")

        data = resp.json()
        services = data.get("data", data.get("services", []))
        return [ServiceInfo(**s) for s in services]

    async def list_services_async(self, *, page: int = 1, limit: int = 50) -> list[ServiceInfo]:
        """Async list."""
        client = self._get_async_client()
        resp = await client.get(
            f"{self._base_url}/api/services",
            params={"page": page, "limit": limit},
        )
        if resp.status_code != 200:
            raise ApiError(resp.text, resp.status_code, "/api/services")

        data = resp.json()
        services = data.get("data", data.get("services", []))
        return [ServiceInfo(**s) for s in services]

    # ── Get Service ──────────────────────────────────────────────────

    def get_service(self, service_id: str) -> ServiceInfo:
        """Get service details by ID."""
        client = self._get_sync_client()
        resp = client.get(f"{self._base_url}/api/services/{service_id}")
        if resp.status_code != 200:
            raise ApiError(resp.text, resp.status_code, f"/api/services/{service_id}")

        data = resp.json()
        return ServiceInfo(**(data.get("service") or data))

    async def get_service_async(self, service_id: str) -> ServiceInfo:
        """Async get service."""
        client = self._get_async_client()
        resp = await client.get(f"{self._base_url}/api/services/{service_id}")
        if resp.status_code != 200:
            raise ApiError(resp.text, resp.status_code, f"/api/services/{service_id}")

        data = resp.json()
        return ServiceInfo(**(data.get("service") or data))

    # ── Call (with auto-payment) ─────────────────────────────────────

    def call(
        self,
        service_id: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: int | float | None = None,
        max_retries: int = 1,
    ) -> CallResult:
        """Call an API service with automatic 402 payment.

        Args:
            service_id: Service identifier
            params: Request parameters (sent as JSON body)
            timeout: Override default timeout
            max_retries: Retries after payment (default 1)

        Returns:
            CallResult with response data
        """
        if self._is_blacklisted(service_id):
            raise ApiError("Service is temporarily blacklisted", 403, service_id)

        client = self._get_sync_client()
        url = f"{self._base_url}/api/call/{service_id}"
        effective_timeout = timeout or self._timeout

        # First request (no payment)
        try:
            resp = client.post(
                url,
                json=params or {},
                headers={"X-Agent-Wallet": self._address},
                timeout=effective_timeout,
            )
        except httpx.TimeoutException:
            raise TimeoutError(url, int(effective_timeout * 1000))

        # Check for free tier success
        if resp.status_code == 200:
            return self._parse_success(resp, service_id)

        # Handle 402
        if resp.status_code == 402:
            return self._handle_402_sync(resp, service_id, params, effective_timeout, max_retries)

        raise ApiError(resp.text, resp.status_code, url)

    async def call_async(
        self,
        service_id: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: int | float | None = None,
        max_retries: int = 1,
    ) -> CallResult:
        """Async version of call()."""
        if self._is_blacklisted(service_id):
            raise ApiError("Service is temporarily blacklisted", 403, service_id)

        client = self._get_async_client()
        url = f"{self._base_url}/api/call/{service_id}"
        effective_timeout = timeout or self._timeout

        try:
            resp = await client.post(
                url,
                json=params or {},
                headers={"X-Agent-Wallet": self._address},
                timeout=effective_timeout,
            )
        except httpx.TimeoutException:
            raise TimeoutError(url, int(effective_timeout * 1000))

        if resp.status_code == 200:
            return self._parse_success(resp, service_id)

        if resp.status_code == 402:
            return await self._handle_402_async(
                resp, service_id, params, effective_timeout, max_retries
            )

        raise ApiError(resp.text, resp.status_code, url)

    def _handle_402_sync(
        self,
        resp: httpx.Response,
        service_id: str,
        params: dict[str, Any] | None,
        timeout: float,
        max_retries: int,
    ) -> CallResult:
        """Handle 402 payment flow (sync)."""
        payment_resp = parse_402_response(resp)
        if not payment_resp:
            raise ApiError("Invalid 402 response", 402, service_id)

        details = payment_resp.payment_details

        # Budget check
        self._budget.check(details.amount)

        # Pay
        result = self._payment.pay_sync(details)

        # Record spending
        self._budget.record(details.amount)

        # Retry with payment proof
        client = self._get_sync_client()
        url = f"{self._base_url}/api/call/{service_id}"

        for attempt in range(max_retries):
            try:
                retry_resp = client.post(
                    url,
                    json=params or {},
                    headers={
                        "X-Payment-TxHash": result.tx_hash,
                        "X-Payment-Chain": self._network,
                        "X-Agent-Wallet": self._address,
                    },
                    timeout=timeout,
                )
            except httpx.TimeoutException:
                raise TimeoutError(url, int(timeout * 1000))

            if retry_resp.status_code == 200:
                call_result = self._parse_success(retry_resp, service_id)
                call_result.tx_hash = result.tx_hash
                call_result.payment_amount = details.amount
                call_result.chain = self._network

                # Check for auto-refund
                if call_result.raw.get("_payment_status") == "refunded":
                    self._budget.reverse(details.amount)
                    self._blacklist[service_id] = time.time()

                return call_result

            if retry_resp.status_code != 402:
                raise ApiError(retry_resp.text, retry_resp.status_code, url)

        raise ApiError("Payment accepted but service still returned 402", 402, url)

    async def _handle_402_async(
        self,
        resp: httpx.Response,
        service_id: str,
        params: dict[str, Any] | None,
        timeout: float,
        max_retries: int,
    ) -> CallResult:
        """Handle 402 payment flow (async)."""
        payment_resp = parse_402_response(resp)
        if not payment_resp:
            raise ApiError("Invalid 402 response", 402, service_id)

        details = payment_resp.payment_details

        # Budget check
        self._budget.check(details.amount)

        # Pay
        client = self._get_async_client()
        result = await self._payment.pay(details, client=client)

        # Record spending
        self._budget.record(details.amount)

        # Retry with payment proof
        url = f"{self._base_url}/api/call/{service_id}"

        for attempt in range(max_retries):
            try:
                retry_resp = await client.post(
                    url,
                    json=params or {},
                    headers={
                        "X-Payment-TxHash": result.tx_hash,
                        "X-Payment-Chain": self._network,
                        "X-Agent-Wallet": self._address,
                    },
                    timeout=timeout,
                )
            except httpx.TimeoutException:
                raise TimeoutError(url, int(timeout * 1000))

            if retry_resp.status_code == 200:
                call_result = self._parse_success(retry_resp, service_id)
                call_result.tx_hash = result.tx_hash
                call_result.payment_amount = details.amount
                call_result.chain = self._network

                if call_result.raw.get("_payment_status") == "refunded":
                    self._budget.reverse(details.amount)
                    self._blacklist[service_id] = time.time()

                return call_result

            if retry_resp.status_code != 402:
                raise ApiError(retry_resp.text, retry_resp.status_code, url)

        raise ApiError("Payment accepted but service still returned 402", 402, url)

    def _parse_success(self, resp: httpx.Response, service_id: str = "") -> CallResult:
        """Parse successful API response with validation."""
        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text}

        free_tier = "true" in (resp.headers.get("x-free-tier", "")).lower()

        # HMAC signature verification
        if self._validation_secret and isinstance(data, dict):
            validation = (data.get("_x402") or {}).get("_validation", {})
            server_sig = validation.get("signature")
            if server_sig:
                if not self._verify_hmac(data, server_sig):
                    logger.warning("HMAC signature mismatch for %s — blacklisting", service_id)
                    if service_id:
                        self._blacklist[service_id] = time.time()

        # Quality score check
        if isinstance(data, dict) and service_id:
            self._check_quality(data, service_id)

        return CallResult(
            status="success",
            data=data.get("data", data) if isinstance(data, dict) else data,
            raw=data if isinstance(data, dict) else {"data": data},
            free_tier_used=free_tier,
        )

    def _verify_hmac(self, data: dict[str, Any], expected_sig: str) -> bool:
        """Verify HMAC-SHA256 signature on response metadata."""
        if not self._validation_secret:
            return True

        validation = (data.get("_x402") or {}).get("_validation", {})
        metadata = {k: v for k, v in validation.items() if k != "signature"}

        # Sort keys for deterministic serialization
        canonical = json_module.dumps(metadata, sort_keys=True, separators=(",", ":"))
        computed = hmac.new(
            self._validation_secret.encode(),
            canonical.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed, expected_sig)

    def _check_quality(self, data: dict[str, Any], service_id: str) -> None:
        """Check response quality — detect empty/invalid responses."""
        x402_meta = data.get("_x402", {})
        server_score = x402_meta.get("quality_score", -1)

        # If server says quality is high but response is essentially empty, blacklist
        if server_score > 0.7:
            response_data = data.get("data", data)
            client_score = self._compute_quality_score(response_data)
            if client_score < 0.2:
                logger.warning(
                    "Quality mismatch for %s (server=%.2f, client=%.2f) — blacklisting",
                    service_id,
                    server_score,
                    client_score,
                )
                self._blacklist[service_id] = time.time()

    @staticmethod
    def _compute_quality_score(data: Any) -> float:
        """Compute a simple quality score for response data."""
        if data is None:
            return 0.0
        if isinstance(data, str):
            return min(1.0, len(data.strip()) / 50)
        if isinstance(data, dict):
            if not data:
                return 0.0
            # Check if values are non-empty
            non_empty = sum(1 for v in data.values() if v is not None and v != "" and v != [])
            return min(1.0, non_empty / max(len(data), 1))
        if isinstance(data, list):
            return min(1.0, len(data) / 3)
        return 0.5  # numbers, bools, etc.

    # ── Balance ──────────────────────────────────────────────────────

    def get_balance(self, chain: Network | None = None) -> dict[str, float]:
        """Get USDC balance. If chain specified, returns single chain. Otherwise all chains."""
        if chain:
            handler = PaymentHandler(self._private_key, chain)
            bal = handler.get_balance_sync()
            return {chain: round(bal, 6)}

        balances: dict[str, float] = {}
        for net in CHAINS:
            try:
                handler = PaymentHandler(self._private_key, net)
                bal = handler.get_balance_sync()
                balances[net] = round(bal, 6)
            except Exception:
                balances[net] = -1  # error
        return balances

    async def get_balance_async(self, chain: Network | None = None) -> dict[str, float]:
        """Async balance check."""
        if chain:
            handler = PaymentHandler(self._private_key, chain)
            bal = await handler.get_balance()
            return {chain: round(bal, 6)}

        balances: dict[str, float] = {}
        for net in CHAINS:
            try:
                handler = PaymentHandler(self._private_key, net)
                bal = await handler.get_balance()
                balances[net] = round(bal, 6)
            except Exception:
                balances[net] = -1
        return balances

    # ── Budget ───────────────────────────────────────────────────────

    def get_budget_status(self) -> BudgetStatus:
        """Get current budget tracking status."""
        return self._budget.status()

    def set_budget(
        self,
        *,
        max_per_call: float | None = None,
        max_daily: float | None = None,
        max_weekly: float | None = None,
        max_monthly: float | None = None,
    ) -> None:
        """Set budget limits."""
        if max_daily is not None:
            self._budget.config.max = max_daily
            self._budget.config.period = "daily"
        elif max_weekly is not None:
            self._budget.config.max = max_weekly
            self._budget.config.period = "weekly"
        elif max_monthly is not None:
            self._budget.config.max = max_monthly
            self._budget.config.period = "monthly"

    # ── Health ───────────────────────────────────────────────────────

    def health(self) -> HealthResponse:
        """Check backend health."""
        client = self._get_sync_client()
        resp = client.get(f"{self._base_url}/health")
        return HealthResponse(**resp.json())

    async def health_async(self) -> HealthResponse:
        """Async health check."""
        client = self._get_async_client()
        resp = await client.get(f"{self._base_url}/health")
        return HealthResponse(**resp.json())

    # ── Faucet (SKALE) ───────────────────────────────────────────────

    def claim_faucet(self) -> dict[str, Any]:
        """Claim SKALE CREDITS faucet."""
        client = self._get_sync_client()
        resp = client.post(
            f"{self._base_url}/api/faucet/claim",
            json={"address": self._address},
        )
        return resp.json()

    async def claim_faucet_async(self) -> dict[str, Any]:
        """Async SKALE CREDITS faucet claim."""
        client = self._get_async_client()
        resp = await client.post(
            f"{self._base_url}/api/faucet/claim",
            json={"address": self._address},
        )
        return resp.json()

    # ── Fund Wallet ──────────────────────────────────────────────────

    def fund_wallet(self) -> dict[str, Any]:
        """Get funding instructions for the wallet.

        Returns bridge URLs and instructions for each supported chain.
        """
        chain_config = CHAINS[self._network]
        instructions: dict[str, Any] = {
            "wallet_address": self._address,
            "network": self._network,
            "chain_id": chain_config.chain_id,
            "usdc_contract": chain_config.usdc_contract,
            "explorer": f"{chain_config.explorer}/address/{self._address}",
            "instructions": [],
        }

        if self._network == "skale":
            instructions["instructions"] = [
                "1. Get free CREDITS gas: client.claim_faucet()",
                "2. Bridge USDC from Base to SKALE: https://bridge.skale.space",
                "3. Or use the faucet for test amounts",
            ]
        elif self._network == "base":
            instructions["instructions"] = [
                "1. Buy USDC on Coinbase and withdraw to Base",
                "2. Or bridge from Ethereum: https://bridge.base.org",
                "3. Send USDC to your wallet address above",
            ]
        elif self._network == "polygon":
            instructions["instructions"] = [
                "1. Buy USDC on any exchange and withdraw to Polygon",
                "2. Or bridge from Ethereum: https://wallet.polygon.technology",
                "3. Gas is paid in POL (~$0.001 per tx)",
                "4. EIP-3009 payments are gas-free (facilitator pays gas)",
            ]
        else:
            instructions["instructions"] = [
                f"Send USDC to {self._address} on {self._network}",
            ]

        return instructions

    async def fund_wallet_async(self) -> dict[str, Any]:
        """Async version (same result, no network call needed)."""
        return self.fund_wallet()

    # ── Repr ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"X402Client(address={self._address!r}, "
            f"chain={self._network!r}, "
            f"base_url={self._base_url!r})"
        )

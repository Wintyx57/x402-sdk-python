"""Pydantic models for API responses and SDK types."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ServiceInfo(BaseModel):
    """A service registered on x402 Bazaar."""

    id: str
    name: str
    url: str
    price_usdc: float
    description: str = ""
    owner_address: str | None = None
    tags: list[str] = Field(default_factory=list)
    verified_status: str | None = None
    category: str | None = None
    method: str | None = None
    status: str | None = None
    trust_score: float | None = None
    credential_type: str | None = None
    has_credentials: bool = False
    created_at: str | None = None
    required_parameters: dict[str, Any] | None = None
    payment_protocol: str | None = None
    logo_url: str | None = None


class NetworkInfo(BaseModel):
    """Supported payment network."""

    network: str
    chainId: int
    label: str
    usdc_contract: str = ""
    explorer: str = ""
    gas: str = ""
    facilitator: str | None = None


class SplitInfo(BaseModel):
    """Payment split details."""

    provider_amount: float = 0
    platform_amount: float = 0
    provider_percent: int = 95
    platform_percent: int = 5


class PaymentDetails(BaseModel):
    """Payment information from 402 response."""

    amount: float
    currency: str = "USDC"
    network: str = "base"
    chainId: int = 8453
    networks: list[NetworkInfo] = Field(default_factory=list)
    recipient: str = ""
    accepted: list[str] = Field(default_factory=list)
    action: str = ""
    provider_wallet: str | None = None
    split: SplitInfo | None = None
    payment_mode: str | None = None


class FreeTierInfo(BaseModel):
    """Free tier status."""

    exhausted: bool = False
    reason: str | None = None
    limit: int = 5
    resets_at: str | None = None


class PaymentResponse(BaseModel):
    """402 Payment Required response body."""

    error: str = "Payment Required"
    message: str = ""
    payment_details: PaymentDetails
    extensions: dict[str, Any] | None = None
    free_tier: FreeTierInfo | None = None


class CallResult(BaseModel):
    """Successful API call result."""

    status: str = "success"
    data: Any = None
    raw: dict[str, Any] = Field(default_factory=dict)
    tx_hash: str | None = None
    payment_amount: float | None = None
    chain: str | None = None
    free_tier_used: bool = False


class BudgetStatus(BaseModel):
    """Current budget tracking status."""

    spent: float = 0
    limit: float = float("inf")
    remaining: float = float("inf")
    period: Literal["daily", "weekly", "monthly"] = "daily"
    call_count: int = 0
    reset_at: datetime | None = None


class WalletInfo(BaseModel):
    """Wallet information."""

    private_key: str
    address: str
    is_new: bool = False


class HealthResponse(BaseModel):
    """Backend health check response."""

    status: str
    network: str = ""
    version: str = ""
    timestamp: str = ""
    uptime_seconds: int = 0


class PaymentResult(BaseModel):
    """Result of a USDC payment."""

    tx_hash: str
    explorer: str = ""
    from_address: str = ""
    amount: float = 0
    chain: str = ""

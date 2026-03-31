"""Chain configurations — Base, Polygon, SKALE, Base Sepolia."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Network = Literal["base", "base-sepolia", "skale", "polygon"]


@dataclass(frozen=True)
class ChainConfig:
    """Configuration for a supported blockchain."""

    chain_id: int
    usdc_contract: str
    usdc_decimals: int
    rpc_urls: list[str] = field(default_factory=list)
    explorer: str = ""
    confirmations: int = 1
    chain_name: str = ""
    native_currency: str = "ETH"

    @property
    def usdc_unit(self) -> int:
        """1 USDC in smallest unit."""
        return 10**self.usdc_decimals


CHAINS: dict[Network, ChainConfig] = {
    "base": ChainConfig(
        chain_id=8453,
        usdc_contract="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        usdc_decimals=6,
        rpc_urls=[
            "https://mainnet.base.org",
            "https://base.llamarpc.com",
            "https://1rpc.io/base",
        ],
        explorer="https://basescan.org",
        confirmations=2,
        chain_name="Base Mainnet",
        native_currency="ETH",
    ),
    "base-sepolia": ChainConfig(
        chain_id=84532,
        usdc_contract="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        usdc_decimals=6,
        rpc_urls=["https://sepolia.base.org"],
        explorer="https://sepolia.basescan.org",
        confirmations=1,
        chain_name="Base Sepolia",
        native_currency="ETH",
    ),
    "skale": ChainConfig(
        chain_id=1187947933,
        usdc_contract="0x85889c8c714505E0c94b30fcfcF64fE3Ac8FCb20",
        usdc_decimals=18,
        rpc_urls=[
            "https://skale-base.skalenodes.com/v1/base",
            "https://1187947933.rpc.thirdweb.com",
        ],
        explorer="https://skale-base-explorer.skalenodes.com",
        confirmations=1,
        chain_name="SKALE on Base",
        native_currency="CREDITS",
    ),
    "polygon": ChainConfig(
        chain_id=137,
        usdc_contract="0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        usdc_decimals=6,
        rpc_urls=[
            "https://polygon-bor-rpc.publicnode.com",
            "https://polygon.publicnode.com",
        ],
        explorer="https://polygonscan.com",
        confirmations=2,
        chain_name="Polygon Mainnet",
        native_currency="POL",
    ),
}

# EIP-712 domain for Polygon Circle USDC (EIP-3009 gas-free transfers)
POLYGON_EIP712_DOMAIN = {
    "name": "USD Coin",
    "version": "2",
    "chainId": 137,
    "verifyingContract": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
}

TRANSFER_WITH_AUTHORIZATION_TYPES = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}

DEFAULT_BASE_URL = "https://x402-api.onrender.com"
DEFAULT_NETWORK: Network = "skale"
DEFAULT_TIMEOUT = 30  # seconds
BLACKLIST_TTL = 600  # 10 minutes

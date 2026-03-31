"""x402 Bazaar Python SDK — autonomous API marketplace with auto-payment."""

from x402_bazaar.client import X402Client
from x402_bazaar.exceptions import (
    ApiError,
    BazaarError,
    BudgetExceededError,
    InsufficientBalanceError,
    InvalidConfigError,
    NetworkError,
    PaymentError,
    TimeoutError,
)
from x402_bazaar.wallet import decrypt_wallet, encrypt_wallet, generate_wallet

__all__ = [
    "X402Client",
    "generate_wallet",
    "encrypt_wallet",
    "decrypt_wallet",
    "BazaarError",
    "PaymentError",
    "InsufficientBalanceError",
    "BudgetExceededError",
    "ApiError",
    "NetworkError",
    "TimeoutError",
    "InvalidConfigError",
]

__version__ = "1.0.0"

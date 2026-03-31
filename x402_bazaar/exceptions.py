"""Typed exception hierarchy for x402 Bazaar SDK."""


class BazaarError(Exception):
    """Base exception for all x402 Bazaar errors."""

    def __init__(self, message: str, code: str = "BAZAAR_ERROR") -> None:
        self.code = code
        super().__init__(message)


class PaymentError(BazaarError):
    """Payment failed."""

    def __init__(
        self,
        message: str,
        *,
        amount: float | None = None,
        recipient: str | None = None,
        tx_hash: str | None = None,
    ) -> None:
        self.amount = amount
        self.recipient = recipient
        self.tx_hash = tx_hash
        super().__init__(message, "PAYMENT_ERROR")


class InsufficientBalanceError(PaymentError):
    """Not enough USDC to pay."""

    def __init__(self, available: float, required: float) -> None:
        self.available = available
        self.required = required
        super().__init__(
            f"Insufficient USDC balance: {available:.6f} USDC available (need: {required} USDC)",
            amount=required,
        )
        self.code = "INSUFFICIENT_BALANCE"


class BudgetExceededError(BazaarError):
    """Spending limit exceeded."""

    def __init__(self, spent: float, limit: float, period: str) -> None:
        self.spent = spent
        self.limit = limit
        self.period = period
        super().__init__(
            f"{period} budget exceeded: {spent:.4f} USDC spent out of {limit} USDC maximum",
            "BUDGET_EXCEEDED",
        )


class ApiError(BazaarError):
    """Backend API returned an error."""

    def __init__(self, message: str, status_code: int, endpoint: str) -> None:
        self.status_code = status_code
        self.endpoint = endpoint
        super().__init__(message, f"API_ERROR_{status_code}")


class NetworkError(BazaarError):
    """Network/RPC error."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        self.cause = cause
        super().__init__(message, "NETWORK_ERROR")


class TimeoutError(BazaarError):
    """Request timed out."""

    def __init__(self, endpoint: str, timeout_ms: int) -> None:
        self.endpoint = endpoint
        self.timeout_ms = timeout_ms
        super().__init__(
            f"Timeout after {timeout_ms}ms for {endpoint}",
            "TIMEOUT_ERROR",
        )


class InvalidConfigError(BazaarError):
    """Invalid SDK configuration."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "INVALID_CONFIG")

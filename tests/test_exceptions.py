"""Tests for exception hierarchy."""

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


def test_bazaar_error_base():
    e = BazaarError("test", "CODE")
    assert str(e) == "test"
    assert e.code == "CODE"


def test_payment_error():
    e = PaymentError("fail", amount=0.01, recipient="0xabc", tx_hash="0x123")
    assert e.amount == 0.01
    assert e.recipient == "0xabc"
    assert e.tx_hash == "0x123"
    assert e.code == "PAYMENT_ERROR"
    assert isinstance(e, BazaarError)


def test_insufficient_balance():
    e = InsufficientBalanceError(1.5, 3.0)
    assert e.available == 1.5
    assert e.required == 3.0
    assert "1.500000" in str(e)
    assert "3.0" in str(e)
    assert e.code == "INSUFFICIENT_BALANCE"
    assert isinstance(e, PaymentError)


def test_budget_exceeded():
    e = BudgetExceededError(4.5, 5.0, "daily")
    assert e.spent == 4.5
    assert e.limit == 5.0
    assert e.period == "daily"
    assert "daily" in str(e)
    assert isinstance(e, BazaarError)


def test_api_error():
    e = ApiError("Not Found", 404, "/api/services")
    assert e.status_code == 404
    assert e.endpoint == "/api/services"
    assert e.code == "API_ERROR_404"


def test_network_error():
    cause = ConnectionError("timeout")
    e = NetworkError("RPC failed", cause=cause)
    assert e.cause is cause
    assert e.code == "NETWORK_ERROR"


def test_timeout_error():
    e = TimeoutError("/api/call/svc", 30000)
    assert e.endpoint == "/api/call/svc"
    assert e.timeout_ms == 30000
    assert "30000ms" in str(e)


def test_invalid_config():
    e = InvalidConfigError("bad chain")
    assert e.code == "INVALID_CONFIG"


def test_inheritance():
    assert issubclass(PaymentError, BazaarError)
    assert issubclass(InsufficientBalanceError, PaymentError)
    assert issubclass(BudgetExceededError, BazaarError)
    assert issubclass(ApiError, BazaarError)
    assert issubclass(NetworkError, BazaarError)
    assert issubclass(TimeoutError, BazaarError)
    assert issubclass(InvalidConfigError, BazaarError)

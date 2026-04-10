"""Tests for budget tracking."""

import time

import pytest

from x402_bazaar.budget import PERIOD_SECONDS, BudgetConfig, BudgetTracker
from x402_bazaar.exceptions import BudgetExceededError


def test_unlimited_budget():
    tracker = BudgetTracker()
    tracker.check(1000)  # Should not raise
    tracker.record(1000)
    status = tracker.status()
    assert status.spent == 1000
    assert status.limit == float("inf")
    assert status.remaining == float("inf")


def test_budget_check_ok():
    tracker = BudgetTracker(config=BudgetConfig(max=10.0, period="daily"))
    tracker.check(5.0)  # Should not raise
    tracker.record(5.0)
    tracker.check(4.0)  # Still ok
    tracker.record(4.0)
    assert tracker.status().spent == 9.0


def test_budget_exceeded():
    tracker = BudgetTracker(config=BudgetConfig(max=5.0, period="daily"))
    tracker.record(4.0)
    with pytest.raises(BudgetExceededError) as exc_info:
        tracker.check(2.0)
    assert exc_info.value.spent == 4.0
    assert exc_info.value.limit == 5.0
    assert exc_info.value.period == "daily"


def test_budget_exact_limit():
    tracker = BudgetTracker(config=BudgetConfig(max=5.0, period="daily"))
    tracker.check(5.0)  # Exactly at limit — ok
    tracker.record(5.0)
    with pytest.raises(BudgetExceededError):
        tracker.check(0.01)  # Over limit


def test_budget_reverse():
    tracker = BudgetTracker(config=BudgetConfig(max=10.0, period="daily"))
    tracker.record(7.0)
    tracker.reverse(3.0)
    assert tracker.status().spent == 4.0
    assert tracker.status().remaining == 6.0


def test_budget_reverse_below_zero():
    tracker = BudgetTracker(config=BudgetConfig(max=10.0, period="daily"))
    tracker.record(2.0)
    tracker.reverse(5.0)  # More than spent
    assert tracker.status().spent == 0.0


def test_budget_call_count():
    tracker = BudgetTracker()
    tracker.record(1.0)
    tracker.record(2.0)
    tracker.record(0.5)
    assert tracker.status().call_count == 3


def test_budget_status_format():
    tracker = BudgetTracker(config=BudgetConfig(max=10.0, period="weekly"))
    tracker.record(3.14159)
    status = tracker.status()
    assert status.spent == 3.14159  # rounded to 6 decimals
    assert status.period == "weekly"
    assert status.reset_at is not None


def test_budget_reset_on_period_elapsed():
    tracker = BudgetTracker(config=BudgetConfig(max=5.0, period="daily"))
    tracker.record(4.0)
    # Simulate period elapsed
    tracker.period_start = time.time() - PERIOD_SECONDS["daily"] - 1
    tracker.check(5.0)  # Should work after reset
    assert tracker.status().spent == 0.0


def test_period_seconds():
    assert PERIOD_SECONDS["daily"] == 86400
    assert PERIOD_SECONDS["weekly"] == 604800
    assert PERIOD_SECONDS["monthly"] == 2592000


def test_unlimited_budget_no_reset():
    tracker = BudgetTracker()
    status = tracker.status()
    assert status.reset_at is None

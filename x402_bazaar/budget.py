"""Local budget tracking — daily/weekly/monthly spending limits."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from x402_bazaar.exceptions import BudgetExceededError
from x402_bazaar.types import BudgetStatus

BudgetPeriod = Literal["daily", "weekly", "monthly"]

PERIOD_SECONDS: dict[BudgetPeriod, int] = {
    "daily": 86400,
    "weekly": 604800,
    "monthly": 2592000,  # 30 days
}


@dataclass
class BudgetConfig:
    """Budget configuration."""

    max: float = float("inf")
    period: BudgetPeriod = "daily"


@dataclass
class BudgetTracker:
    """Tracks spending against budget limits."""

    config: BudgetConfig = field(default_factory=BudgetConfig)
    spent: float = 0.0
    call_count: int = 0
    period_start: float = field(default_factory=time.time)

    def _maybe_reset(self) -> None:
        """Reset counters if period has elapsed."""
        if self.config.max == float("inf"):
            return
        elapsed = time.time() - self.period_start
        period_seconds = PERIOD_SECONDS[self.config.period]
        if elapsed >= period_seconds:
            self.spent = 0.0
            self.call_count = 0
            self.period_start = time.time()

    def check(self, amount: float) -> None:
        """Check if amount fits within budget. Raises BudgetExceededError if not."""
        if self.config.max == float("inf"):
            return
        self._maybe_reset()
        if self.spent + amount > self.config.max:
            raise BudgetExceededError(self.spent, self.config.max, self.config.period)

    def record(self, amount: float) -> None:
        """Record spending."""
        self._maybe_reset()
        self.spent += amount
        self.call_count += 1

    def reverse(self, amount: float) -> None:
        """Reverse spending (e.g., auto-refund)."""
        self.spent = max(0, self.spent - amount)

    def status(self) -> BudgetStatus:
        """Get current budget status."""
        self._maybe_reset()
        from datetime import datetime, timezone

        remaining = max(0, self.config.max - self.spent) if self.config.max != float("inf") else float("inf")
        period_seconds = PERIOD_SECONDS[self.config.period]
        reset_ts = self.period_start + period_seconds

        return BudgetStatus(
            spent=round(self.spent, 6),
            limit=self.config.max,
            remaining=round(remaining, 6) if remaining != float("inf") else float("inf"),
            period=self.config.period,
            call_count=self.call_count,
            reset_at=datetime.fromtimestamp(reset_ts, tz=timezone.utc) if self.config.max != float("inf") else None,
        )

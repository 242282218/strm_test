import math
from datetime import UTC, datetime

import pytest

import app.services.scoring.freshness as freshness_module
from app.services.scoring.freshness import FreshnessCalculator


class _FixedDateTime:
    @staticmethod
    def fromisoformat(value: str) -> datetime:
        return datetime.fromisoformat(value)

    @staticmethod
    def now(_: object = None) -> datetime:
        return datetime(2026, 1, 31, tzinfo=UTC)


def test_calculate_returns_mid_score_for_missing_or_invalid_date() -> None:
    calculator = FreshnessCalculator()

    assert calculator.calculate(None) == 0.5
    assert calculator.calculate("not-a-date") == 0.5


def test_calculate_uses_exponential_decay_for_past_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(freshness_module, "datetime", _FixedDateTime)
    calculator = FreshnessCalculator()

    score = calculator.calculate("2026-01-01T00:00:00Z")

    assert score == pytest.approx(math.exp(-30 / 60))


def test_calculate_returns_one_for_future_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(freshness_module, "datetime", _FixedDateTime)
    calculator = FreshnessCalculator()

    assert calculator.calculate("2026-03-01T00:00:00Z") == 1.0

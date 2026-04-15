import math

from app.services.scoring.popularity import PopularityCalculator


def test_calculate_returns_zero_for_non_positive_views() -> None:
    calculator = PopularityCalculator()

    assert calculator.calculate(0) == 0.0
    assert calculator.calculate(-5) == 0.0


def test_calculate_uses_logarithmic_growth_before_cap() -> None:
    calculator = PopularityCalculator()

    score_10 = calculator.calculate(10)
    score_50 = calculator.calculate(50)
    expected_50 = math.log1p(50) / math.log1p(200)

    assert 0.0 < score_10 < score_50 < 1.0
    assert score_50 == expected_50


def test_calculate_caps_score_for_very_large_views() -> None:
    calculator = PopularityCalculator()

    assert calculator.calculate(200) == 1.0
    assert calculator.calculate(10000) == 1.0

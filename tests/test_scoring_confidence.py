import pytest

from app.services.scoring.confidence import ConfidenceCalculator


def test_text_similarity_returns_one_when_query_fully_in_title() -> None:
    calculator = ConfidenceCalculator()
    assert calculator._text_similarity("Interstellar", "Interstellar 2014 4K") == 1.0


def test_text_similarity_returns_zero_for_empty_bigrams() -> None:
    calculator = ConfidenceCalculator()
    assert calculator._text_similarity("a", "b") == 0.0


def test_text_similarity_handles_query_without_ascii_tokens() -> None:
    calculator = ConfidenceCalculator()
    assert calculator._text_similarity("星际穿越", "星际穿越 2014 蓝光") == 1.0


def test_intent_score_handles_negative_and_iso_exception() -> None:
    calculator = ConfidenceCalculator()

    negative = calculator._intent_score("这是一个教程资源", {"1080p"})
    iso_exception = calculator._intent_score("教程 原盘.iso", {"bluray"})

    assert negative == 0.0
    assert iso_exception == pytest.approx(0.7)


def test_intent_score_adds_positive_and_tags_bonus_with_cap() -> None:
    calculator = ConfidenceCalculator()
    score = calculator._intent_score("电影 4k 蓝光", {"4k", "x265"})
    assert score == pytest.approx(0.9)


def test_plausibility_score_uses_high_quality_tag_shortcut() -> None:
    calculator = ConfidenceCalculator()

    assert calculator._plausibility_score("demo", {"4k"}) == 0.9
    assert calculator._plausibility_score("demo", set()) == 0.7


def test_calculate_applies_low_quality_penalty_for_zero_intent() -> None:
    calculator = ConfidenceCalculator()
    confidence = calculator.calculate("movie", "完全无关教程文案", {"1080p"})
    assert confidence == 0.0
    assert calculator.intent_score == 0.0


def test_calculate_updates_intermediate_scores_and_bounds() -> None:
    calculator = ConfidenceCalculator()
    confidence = calculator.calculate("Interstellar", "Interstellar 2014 4K 蓝光", {"4k", "bluray", "x265"})

    assert 0.0 <= confidence <= 1.0
    assert calculator.text_similarity > 0
    assert calculator.intent_score > 0
    assert calculator.plausibility_score == 0.9

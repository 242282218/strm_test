from app.services.scoring.quality import QualityCalculator


def test_calculate_returns_zero_without_quality_tags() -> None:
    calculator = QualityCalculator()
    score = calculator.calculate("plain title", set())
    assert score == 0.0


def test_calculate_applies_conflict_penalty_for_4k_and_1080p() -> None:
    calculator = QualityCalculator()

    with_conflict = calculator.calculate("movie", {"4k", "1080p", "remux"})
    without_conflict = calculator.calculate("movie", {"4k", "remux"})

    assert with_conflict < without_conflict
    assert with_conflict == (25 + 30 - 12) / 110


def test_calculate_caps_score_to_one_for_dense_high_quality_tags() -> None:
    calculator = QualityCalculator()

    tags = {
        "4k",
        "bdmv",
        "dv",
        "hdr",
        "atmos",
        "dtsx",
        "truehd",
        "dtshd",
        "ddp",
        "x265",
        "x264",
        "fx_sub",
        "multi_audio",
        "imax",
        "hfr",
        "collection",
    }

    score = calculator.calculate("高码率 demo", tags)
    assert score == 1.0


def test_calculate_uses_cn_sub_when_fx_sub_missing() -> None:
    calculator = QualityCalculator()

    score = calculator.calculate("demo", {"1080p", "bluray", "cn_sub"})
    expected_points = 15 + 24 + 3

    assert score == expected_points / 110

from app.services.scoring.engine import ScoringEngine


def test_calculate_alpha_boundaries() -> None:
    engine = ScoringEngine()

    assert engine._calculate_alpha(0.49) == 0.7
    assert engine._calculate_alpha(0.5) == 0.55
    assert engine._calculate_alpha(0.79) == 0.55
    assert engine._calculate_alpha(0.8) == 0.4


def test_calculate_pr_gate_boundaries() -> None:
    engine = ScoringEngine()

    assert engine._calculate_pr_gate(0.39) == 0.0
    assert engine._calculate_pr_gate(0.4) == 0.3
    assert engine._calculate_pr_gate(0.59) == 0.3
    assert engine._calculate_pr_gate(0.6) == 1.0


def test_score_uses_low_confidence_bypass(monkeypatch) -> None:
    engine = ScoringEngine()
    monkeypatch.setattr(engine.tag_extractor, "extract", lambda _title: {"4k"})
    monkeypatch.setattr(engine.confidence_calc, "calculate", lambda query, title, tags: 0.05)
    monkeypatch.setattr(engine.quality_calc, "calculate", lambda title, tags: 1.0)
    monkeypatch.setattr(engine.popularity_calc, "calculate", lambda views: 1.0)
    monkeypatch.setattr(engine.freshness_calc, "calculate", lambda pub_date: 1.0)

    result = engine.score("query", {"title": "demo", "pub_date": "2026-04-16"})

    assert result["confidence"] == 0.05
    assert result["score"] == 0.05
    assert result["tags"] == ["4k"]


def test_score_combines_dimensions_when_confidence_not_low(monkeypatch) -> None:
    engine = ScoringEngine()
    monkeypatch.setattr(engine.tag_extractor, "extract", lambda _title: {"1080p"})
    monkeypatch.setattr(engine.confidence_calc, "calculate", lambda query, title, tags: 0.6)
    monkeypatch.setattr(engine.quality_calc, "calculate", lambda title, tags: 0.5)
    monkeypatch.setattr(engine.popularity_calc, "calculate", lambda views: 0.2)
    monkeypatch.setattr(engine.freshness_calc, "calculate", lambda pub_date: 0.4)

    result = engine.score("query", {"title": "demo", "pub_date": "2026-04-16"})

    # confidence=0.6 => alpha=0.55, pr_gate=1.0
    # score=0.55*0.6 + 0.45*0.5 + (0.1*0.2 + 0.05*0.4)=0.595
    assert result["alpha"] == 0.55
    assert result["pr_gate"] == 1.0
    assert result["score"] == 0.595

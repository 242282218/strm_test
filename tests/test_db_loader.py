from __future__ import annotations

import sys
import types

import pytest

from app.core import db_loader


class DummyStatement:
    def __init__(self, model: object) -> None:
        self.model = model
        self.options_calls: list[tuple[object, ...]] = []
        self.filter_by_calls: list[dict[str, object]] = []

    def options(self, *options: object) -> DummyStatement:
        self.options_calls.append(options)
        return self

    def filter_by(self, **kwargs: object) -> DummyStatement:
        self.filter_by_calls.append(kwargs)
        return self


class _SentinelSelectInload:
    def __call__(self, attr: object) -> str:
        return f"selectin:{attr}"


def _install_model_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    user_module = types.SimpleNamespace(User=types.SimpleNamespace(security_events="security_events_field"))
    task_module = types.SimpleNamespace(Task=type("Task", (), {}))
    scrape_module = types.SimpleNamespace(ScrapeRecord=type("ScrapeRecord", (), {}))
    emby_module = types.SimpleNamespace(EmbyCache=type("EmbyCache", (), {}))
    notification_module = types.SimpleNamespace(Notification=type("Notification", (), {}))

    monkeypatch.setitem(sys.modules, "app.models.user", user_module)
    monkeypatch.setitem(sys.modules, "app.models.task", task_module)
    monkeypatch.setitem(sys.modules, "app.models.scrape", scrape_module)
    monkeypatch.setitem(sys.modules, "app.models.emby", emby_module)
    monkeypatch.setitem(sys.modules, "app.models.notification", notification_module)


def test_load_strategy_wrappers_delegate_to_sqlalchemy_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_loader, "joinedload", lambda *attrs: ("joined", attrs))
    monkeypatch.setattr(db_loader, "selectinload", lambda *attrs: ("selectin", attrs))
    monkeypatch.setattr(db_loader, "subqueryload", lambda *attrs: ("subquery", attrs))

    assert db_loader.QueryOptimizer.joinedload("a", "b") == ("joined", ("a", "b"))
    assert db_loader.QueryOptimizer.selectinload("x") == ("selectin", ("x",))
    assert db_loader.QueryOptimizer.subqueryload("y") == ("subquery", ("y",))


def test_get_user_options_returns_selectinload_option(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model_modules(monkeypatch)
    monkeypatch.setattr(db_loader, "selectinload", _SentinelSelectInload())

    options = db_loader.QueryOptimizer.get_user_options()

    assert options == ["selectin:security_events_field"]


def test_other_model_options_return_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model_modules(monkeypatch)

    assert db_loader.QueryOptimizer.get_task_options() == []
    assert db_loader.QueryOptimizer.get_scrape_options() == []
    assert db_loader.QueryOptimizer.get_emby_options() == []
    assert db_loader.QueryOptimizer.get_notification_options() == []


def test_apply_options_applies_resolved_model_options(monkeypatch: pytest.MonkeyPatch) -> None:
    stmt = DummyStatement(model="User")
    monkeypatch.setattr(db_loader.QueryOptimizer, "get_user_options", staticmethod(lambda: ["opt-a", "opt-b"]))

    result = db_loader.QueryOptimizer.apply_options(stmt, "user")

    assert result is stmt
    assert stmt.options_calls == [("opt-a", "opt-b")]


def test_apply_options_logs_warning_for_unknown_model_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[str] = []
    stmt = DummyStatement(model="Unknown")
    monkeypatch.setattr(db_loader.logger, "warning", lambda message: warnings.append(message))

    result = db_loader.QueryOptimizer.apply_options(stmt, "missing-model")

    assert result is stmt
    assert stmt.options_calls == []
    assert warnings == ["Unknown model type: missing-model"]


def test_optimize_query_delegates_to_apply_options(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str]] = []
    sentinel_stmt = object()

    def fake_apply_options(stmt: object, model_type: str) -> str:
        calls.append((stmt, model_type))
        return "optimized"

    monkeypatch.setattr(db_loader.QueryOptimizer, "apply_options", staticmethod(fake_apply_options))

    result = db_loader.optimize_query(sentinel_stmt, "user")

    assert result == "optimized"
    assert calls == [(sentinel_stmt, "user")]


def test_create_optimized_select_builds_select_and_applies_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model_modules(monkeypatch)

    def fake_select(model: object) -> DummyStatement:
        return DummyStatement(model)

    monkeypatch.setattr(db_loader, "select", fake_select)
    monkeypatch.setattr(db_loader, "optimize_query", lambda stmt, model_type: (stmt, model_type))

    stmt, model_type = db_loader.create_optimized_select("user", is_active=True)

    assert model_type == "user"
    assert isinstance(stmt, DummyStatement)
    assert stmt.filter_by_calls == [{"is_active": True}]


def test_create_optimized_select_without_filter_uses_plain_select(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model_modules(monkeypatch)

    def fake_select(model: object) -> DummyStatement:
        return DummyStatement(model)

    monkeypatch.setattr(db_loader, "select", fake_select)
    monkeypatch.setattr(db_loader, "optimize_query", lambda stmt, model_type: (stmt, model_type))

    stmt, model_type = db_loader.create_optimized_select("task")

    assert model_type == "task"
    assert stmt.filter_by_calls == []


def test_create_optimized_select_raises_for_unknown_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model_modules(monkeypatch)

    with pytest.raises(ValueError, match="Unknown model type: invalid"):
        db_loader.create_optimized_select("invalid")

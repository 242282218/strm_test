from app.services.scrape_state_machine import ScrapeStateMachine


def test_happy_path_transitions():
    sm = ScrapeStateMachine()
    chain = ["pending", "scanned", "scraping", "scraped", "renaming", "renamed"]
    for idx in range(len(chain) - 1):
        current = chain[idx]
        nxt = chain[idx + 1]
        assert sm.can_transition(current, nxt)
        result = sm.assert_transition(current, nxt)
        assert result.changed is True


def test_scrape_failed_retry_transition():
    sm = ScrapeStateMachine()
    assert sm.can_transition("scraping", "scrape_failed")
    assert sm.can_transition("scrape_failed", "scanned")
    sm.assert_transition("scraping", "scrape_failed")
    sm.assert_transition("scrape_failed", "scanned")


def test_rename_failed_retry_transition():
    sm = ScrapeStateMachine()
    assert sm.can_transition("renaming", "rename_failed")
    assert sm.can_transition("rename_failed", "renaming")
    sm.assert_transition("renaming", "rename_failed")
    sm.assert_transition("rename_failed", "renaming")


def test_invalid_transition_is_rejected():
    sm = ScrapeStateMachine()
    assert sm.can_transition("pending", "scraping") is False
    try:
        sm.assert_transition("pending", "scraping")
        assert False, "Expected ValueError for invalid transition"
    except ValueError as exc:
        assert "Invalid status transition" in str(exc)


def test_same_state_idempotent_by_default():
    sm = ScrapeStateMachine()
    result = sm.assert_transition("pending", "pending")
    assert result.changed is False


from __future__ import annotations

from dataclasses import dataclass


SCRAPE_WORKFLOW_STATUSES = (
    "pending",
    "scanned",
    "scraping",
    "scraped",
    "renaming",
    "renamed",
    "scrape_failed",
    "rename_failed",
)


ALLOWED_SCRAPE_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"scanned", "scrape_failed"},
    "scanned": {"scraping", "scrape_failed"},
    "scraping": {"scraped", "scrape_failed"},
    "scraped": {"renaming", "renamed", "rename_failed"},
    "renaming": {"renamed", "rename_failed"},
    "renamed": set(),
    "scrape_failed": {"scanned"},
    "rename_failed": {"renaming", "scanned"},
}


@dataclass(frozen=True)
class TransitionResult:
    current: str
    target: str
    changed: bool


class ScrapeStateMachine:
    def __init__(self, allow_same_state: bool = True):
        self.allow_same_state = allow_same_state

    def is_valid_status(self, status: str) -> bool:
        return status in ALLOWED_SCRAPE_TRANSITIONS

    def can_transition(self, current: str, target: str) -> bool:
        if not self.is_valid_status(current) or not self.is_valid_status(target):
            return False
        if current == target:
            return self.allow_same_state
        return target in ALLOWED_SCRAPE_TRANSITIONS[current]

    def assert_transition(self, current: str, target: str) -> TransitionResult:
        if not self.is_valid_status(current):
            raise ValueError(f"Unknown current status: {current}")
        if not self.is_valid_status(target):
            raise ValueError(f"Unknown target status: {target}")
        if current == target and self.allow_same_state:
            return TransitionResult(current=current, target=target, changed=False)
        if target not in ALLOWED_SCRAPE_TRANSITIONS[current]:
            raise ValueError(f"Invalid status transition: {current} -> {target}")
        return TransitionResult(current=current, target=target, changed=True)


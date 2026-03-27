"""Budget tracker for API calls per repository and principle."""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class BudgetTracker:
    """Tracks detection and refactoring API calls per repo per principle."""

    budget_file: Path
    detections_per_principle: int = 12
    refactorings_per_principle: int = 12
    principles: list[str] = field(
        default_factory=lambda: ["SRP", "OCP", "LSP", "ISP", "DIP"]
    )
    _state: dict = field(default_factory=dict)

    def __post_init__(self):
        self._load()

    def _default_repo_state(self) -> dict:
        return {
            "detections": {p: 0 for p in self.principles},
            "refactorings": {p: 0 for p in self.principles},
        }

    def _load(self):
        if self.budget_file.exists():
            with open(self.budget_file) as f:
                self._state = json.load(f)
        else:
            self._state = {}

    def _save(self):
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.budget_file, "w") as f:
            json.dump(self._state, f, indent=2)

    def _ensure_repo(self, repo: str):
        if repo not in self._state:
            self._state[repo] = self._default_repo_state()

    def can_detect(self, repo: str, principle: str) -> bool:
        self._ensure_repo(repo)
        return self._state[repo]["detections"].get(principle, 0) < self.detections_per_principle

    def can_refactor(self, repo: str, principle: str) -> bool:
        self._ensure_repo(repo)
        return self._state[repo]["refactorings"].get(principle, 0) < self.refactorings_per_principle

    def record_detection(self, repo: str, principle: str):
        self._ensure_repo(repo)
        self._state[repo]["detections"][principle] = (
            self._state[repo]["detections"].get(principle, 0) + 1
        )
        self._save()

    def record_refactoring(self, repo: str, principle: str):
        self._ensure_repo(repo)
        self._state[repo]["refactorings"][principle] = (
            self._state[repo]["refactorings"].get(principle, 0) + 1
        )
        self._save()

    def get_detection_count(self, repo: str, principle: str) -> int:
        self._ensure_repo(repo)
        return self._state[repo]["detections"].get(principle, 0)

    def get_refactoring_count(self, repo: str, principle: str) -> int:
        self._ensure_repo(repo)
        return self._state[repo]["refactorings"].get(principle, 0)

    def get_total_detections(self, repo: str) -> int:
        self._ensure_repo(repo)
        return sum(self._state[repo]["detections"].values())

    def get_total_refactorings(self, repo: str) -> int:
        self._ensure_repo(repo)
        return sum(self._state[repo]["refactorings"].values())

    def summary(self, repo: str) -> dict:
        self._ensure_repo(repo)
        return {
            "detections": dict(self._state[repo]["detections"]),
            "refactorings": dict(self._state[repo]["refactorings"]),
            "total_detections": self.get_total_detections(repo),
            "total_refactorings": self.get_total_refactorings(repo),
        }

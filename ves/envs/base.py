from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class EnvError(RuntimeError):
    """The environment itself failed (not the agent): the run is recorded as an infrastructure error."""


class DesktopEnv(ABC):
    native_size: tuple[int, int] = (1920, 1080)

    @abstractmethod
    def reset(self, seed: int) -> dict:
        """Start the desktop and run the task's setup; return metadata (software versions, ids)."""

    @abstractmethod
    def screenshot(self) -> bytes:
        """Full-resolution PNG of the current screen."""

    @abstractmethod
    def execute(self, action: dict) -> bytes:
        """Execute one action, wait for the UI to settle, return the screenshot taken after it."""

    @abstractmethod
    def finalize(self, outputs_dir: Path) -> dict:
        """Run the task's post-task hook and verifier; copy output files into outputs_dir.
        Returns {"passed": bool, "score": float (0-1), "feedback": str, "verifier": str, "raw": dict}."""

    @abstractmethod
    def close(self) -> None:
        """Release the environment (idempotent)."""

    def diff_ignore_boxes(self) -> list[tuple[int, int, int, int]]:
        """Screen regions that change without any action (e.g. the clock in the top bar)."""
        return []

"""
results.py
QAResult: the single object that bundles everything about one image's
QA run -- its metadata, every check result from all nine categories,
and (once scoring.py exists) its final verdict.
"""

from dataclasses import dataclass, field
from typing import Optional

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult


@dataclass
class QAResult:
    filepath: str
    filename: str
    metadata: RasterMetadata

    # All CheckResults from all nine categories, flattened into one list.
    # Keeping this flat (not nested per-category) makes scoring simpler --
    # scoring.py just needs to scan every result for CRITICAL severity,
    # it doesn't care which category a result came from.
    all_checks: list[CheckResult] = field(default_factory=list)

    # Filled in later by scoring.py -- left optional here so QAResult can
    # be constructed and inspected even before scoring runs.
    passed: Optional[bool] = None
    score: Optional[float] = None
    fail_reason: Optional[str] = None

    def critical_failures(self) -> list[CheckResult]:
        """Convenience accessor: every CRITICAL-severity failed check."""
        return [c for c in self.all_checks if not c.passed and c.severity.name == "CRITICAL"]

    def warnings(self) -> list[CheckResult]:
        """Convenience accessor: every WARNING-severity failed check."""
        return [c for c in self.all_checks if not c.passed and c.severity.name == "WARNING"]

    def summary(self) -> str:
        """One-line human-readable summary, useful for quick console output."""
        total = len(self.all_checks)
        failed = len([c for c in self.all_checks if not c.passed])
        status = "UNSCORED" if self.passed is None else ("PASS" if self.passed else "FAIL")
        return f"{self.filename}: {status} ({failed}/{total} checks failed)"
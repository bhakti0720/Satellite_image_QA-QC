"""
base.py
Shared result structure used by every QA check across all categories.
"""

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CheckResult:
    check_name: str        # e.g. "file_exists"
    passed: bool
    severity: Severity
    message: str           # human-readable explanation


def pass_result(check_name: str, message: str = "OK") -> CheckResult:
    return CheckResult(check_name=check_name, passed=True, severity=Severity.INFO, message=message)


def fail_result(check_name: str, severity: Severity, message: str) -> CheckResult:
    return CheckResult(check_name=check_name, passed=False, severity=severity, message=message)
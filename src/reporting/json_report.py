"""
json_report.py
Writes a list of QAResult objects to a JSON file, preserving full nested
detail (every individual CheckResult, not packed into strings like the
CSV report). Intended as the machine-readable / programmatic-consumption
counterpart to csv_report.py's human-skimmable format.
"""

import json
from pathlib import Path
from typing import Union
from dataclasses import asdict

from src.engine.results import QAResult
from src.checks.base import CheckResult, Severity


def check_result_to_dict(check: CheckResult) -> dict:
    """Converts one CheckResult into a JSON-safe dict (Severity enum -> string)."""
    return {
        "check_name": check.check_name,
        "passed": check.passed,
        "severity": check.severity.value,  # Severity is an Enum -- .value gives the plain string
        "message": check.message,
    }


def qa_result_to_dict(result: QAResult) -> dict:
    """Converts one QAResult into a fully nested, JSON-safe dict."""
    return {
        "filename": result.filename,
        "filepath": result.filepath,
        "passed": result.passed,
        "score": result.score,
        "fail_reason": result.fail_reason,
        "metadata": {
            "is_valid": result.metadata.is_valid,
            "width": result.metadata.width,
            "height": result.metadata.height,
            "band_count": result.metadata.band_count,
            "dtype": result.metadata.dtype,
            "crs": result.metadata.crs,
            "driver": result.metadata.driver,
            "file_size_bytes": result.metadata.file_size_bytes,
        },
        "summary": {
            "total_checks": len(result.all_checks),
            "failed_checks": len([c for c in result.all_checks if not c.passed]),
            "critical_failures": len(result.critical_failures()),
            "warning_failures": len(result.warnings()),
        },
        "checks": [check_result_to_dict(c) for c in result.all_checks],
    }


def write_json_report(results: list[QAResult], output_path: Union[str, Path]) -> None:
    """
    Writes a list of scored QAResults to a JSON file at output_path.
    Output is a single JSON array of per-image objects. Creates parent
    directories if they don't exist.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = [qa_result_to_dict(r) for r in results]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)

    print(f"JSON report written: {output_path} ({len(results)} images)")
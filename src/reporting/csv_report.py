"""
csv_report.py
Writes a list of QAResult objects to a CSV file, one row per image.
Detailed check-level failures are packed into a single semicolon-separated
column rather than given individual columns, to keep the CSV readable
regardless of how many checks an image fails.
"""

import csv
from pathlib import Path
from typing import Union

from src.engine.results import QAResult


CSV_COLUMNS = [
    "filename",
    "filepath",
    "passed",
    "score",
    "fail_reason",
    "total_checks",
    "failed_checks_count",
    "critical_failures_count",
    "warning_failures_count",
    "critical_failures",
    "warnings",
]


def qa_result_to_row(result: QAResult) -> dict:
    """Converts one QAResult into a flat dict matching CSV_COLUMNS."""
    critical = result.critical_failures()
    warnings = result.warnings()
    failed_total = len([c for c in result.all_checks if not c.passed])

    return {
        "filename": result.filename,
        "filepath": result.filepath,
        "passed": result.passed,
        "score": result.score,
        "fail_reason": result.fail_reason or "",
        "total_checks": len(result.all_checks),
        "failed_checks_count": failed_total,
        "critical_failures_count": len(critical),
        "warning_failures_count": len(warnings),
        "critical_failures": "; ".join(f"{c.check_name}: {c.message}" for c in critical),
        "warnings": "; ".join(f"{c.check_name}: {c.message}" for c in warnings),
    }


def write_csv_report(results: list[QAResult], output_path: Union[str, Path]) -> None:
    """
    Writes a list of scored QAResults to a CSV file at output_path.
    Creates parent directories if they don't exist.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for result in results:
            writer.writerow(qa_result_to_row(result))

    print(f"CSV report written: {output_path} ({len(results)} rows)")
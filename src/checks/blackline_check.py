"""
blackline_check.py
Category 8 (visual artifact detection): Sensor striping/banding detection.

Distinct from saturation_check.py's check_saturation_by_line, which catches
rows/columns dropped to exactly zero (an exposure/clipping phenomenon).
This check instead detects rows or columns that are anomalously UNIFORM
relative to their neighbors -- the signature of sensor calibration drift
or detector striping, where a row/column reads a near-constant value
distinctly different from the rows around it, without necessarily being
zero. This is a common real-world satellite sensor artifact that a pure
zero-value check would miss entirely.
"""

import rasterio
import numpy as np

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


def compute_row_col_uniformity(filepath: str) -> dict:
    """
    For band 1, computes the standard deviation *within* each row and
    each column. A normal row has real spatial variation (std well above
    zero). A striped/banded row is anomalously flat compared to its
    neighbors -- its own internal std collapses even though the image
    around it looks normal.
    Returns per-row and per-column std arrays for further analysis.
    """
    with rasterio.open(filepath) as src:
        band1 = src.read(1).astype(np.float64)

    row_stds = band1.std(axis=1)  # variation within each row
    col_stds = band1.std(axis=0)  # variation within each column

    return {"row_stds": row_stds, "col_stds": col_stds}


def check_striping(meta: RasterMetadata, low_std_ratio: float = 0.15) -> CheckResult:
    """
    Flags a row or column whose internal std is much lower than the
    median row/column std -- i.e. anomalously flat/uniform compared to
    its neighbors. low_std_ratio=0.15 means: a row is flagged if its std
    is less than 15% of the median row std.
    """
    data = compute_row_col_uniformity(meta.filepath)
    row_stds, col_stds = data["row_stds"], data["col_stds"]

    median_row_std = np.median(row_stds)
    median_col_std = np.median(col_stds)

    # Avoid division-by-zero on a degenerate image (already caught by
    # constant_bands in statistics_check.py, but guard here too)
    if median_row_std == 0 or median_col_std == 0:
        return fail_result("striping_check", Severity.CRITICAL, "Cannot evaluate — image has zero overall variance")

    flagged_rows = np.where(row_stds < median_row_std * low_std_ratio)[0]
    flagged_cols = np.where(col_stds < median_col_std * low_std_ratio)[0]

    if len(flagged_rows) > 0 or len(flagged_cols) > 0:
        details = []
        if len(flagged_rows) > 0:
            details.append(f"{len(flagged_rows)} row(s) (e.g. row {flagged_rows[0]})")
        if len(flagged_cols) > 0:
            details.append(f"{len(flagged_cols)} col(s) (e.g. col {flagged_cols[0]})")
        return fail_result(
            "striping_check",
            Severity.WARNING,
            f"Anomalously uniform line(s) detected: {', '.join(details)} — possible sensor striping"
        )
    return pass_result("striping_check", "No striping artifacts detected")


def run_blackline_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs striping check. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("blackline_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    return [check_striping(meta)]
"""
saturation_check.py
Category 6: Saturation detection.

Flags pixels clipped at the extremes — pure black (dropout/underexposed)
or pinned at a high plateau (overexposed/blown-out highlights). Distinct
from nodata_check.py: NoData checks look for *missing* data injected as
zero blocks; this looks for *sensor* saturation, which can occur even in
otherwise valid, complete images (e.g. bright rooftops, sun glint).
"""

import rasterio
import numpy as np

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


def compute_saturation_fractions(filepath: str, high_threshold: int = 10000) -> list[dict]:
    """
    Reads each band and computes the fraction of pixels at the low extreme
    (== 0) and high extreme (>= high_threshold), per band.
    Returns a list of dicts: [{"band": 1, "low_frac": .., "high_frac": ..}, ...]
    """
    results = []
    with rasterio.open(filepath) as src:
        for band_idx in range(1, src.count + 1):
            band = src.read(band_idx)
            total = band.size
            low_frac = float(np.sum(band == 0)) / total
            high_frac = float(np.sum(band >= high_threshold)) / total
            results.append({"band": band_idx, "low_frac": low_frac, "high_frac": high_frac})
    return results


def check_low_saturation(meta: RasterMetadata, max_low_fraction: float = 0.05) -> CheckResult:
    """
    Pixels pinned at exactly 0. Note: this overlaps conceptually with
    nodata_check.py's zero-fraction check — that's expected. NoData check
    treats it as a "missing data" problem; this treats it as an "exposure"
    problem. Keeping both is intentional so the report labels it correctly
    depending on context (e.g. a black_line.tif defect should show up here
    with a clear spatial line, not just a raw percentage).
    """
    fractions = compute_saturation_fractions(meta.filepath)
    bad_bands = [f["band"] for f in fractions if f["low_frac"] > max_low_fraction]

    if bad_bands:
        return fail_result(
            "low_saturation",
            Severity.WARNING,
            f"Band(s) {bad_bands} have >{max_low_fraction:.0%} pixels at 0 (underexposed/clipped)"
        )
    return pass_result("low_saturation", "No significant low-end clipping")


def check_high_saturation(meta: RasterMetadata, high_threshold: int = 10000, max_high_fraction: float = 0.02) -> CheckResult:
    """
    Pixels pinned at or above a high-reflectance threshold. A small amount
    is normal (bright surfaces genuinely exist), but a large fraction
    suggests overexposure or a scaling/processing error.
    """
    fractions = compute_saturation_fractions(meta.filepath, high_threshold)
    bad_bands = [f["band"] for f in fractions if f["high_frac"] > max_high_fraction]

    if bad_bands:
        return fail_result(
            "high_saturation",
            Severity.WARNING,
            f"Band(s) {bad_bands} have >{max_high_fraction:.0%} pixels >= {high_threshold} (overexposed)"
        )
    return pass_result("high_saturation", "No significant high-end clipping")


def check_saturation_by_line(meta: RasterMetadata, line_fraction_threshold: float = 0.4) -> CheckResult:
    """
    Detects a row or column with a high concentration of zero-value pixels —
    the signature of a sensor dropout line/strip. Note: based on empirical
    testing against this project's black_line.tif defects, injected lines
    are partial-width (~50-58% of row width) rather than full-width, so the
    threshold is tuned to catch partial segments while staying well above
    normal image noise (clean tiles showed 0% max row/col fraction).
    """
    with rasterio.open(meta.filepath) as src:
        band1 = src.read(1)

    zero_mask = (band1 == 0)
    row_fractions = zero_mask.mean(axis=1)
    col_fractions = zero_mask.mean(axis=0)

    max_row_frac = float(row_fractions.max())
    max_col_frac = float(col_fractions.max())

    if max_row_frac > line_fraction_threshold or max_col_frac > line_fraction_threshold:
        direction = "row" if max_row_frac > max_col_frac else "column"
        worst_frac = max(max_row_frac, max_col_frac)
        return fail_result(
            "saturation_by_line",
            Severity.CRITICAL,
            f"Detected a zero-value {direction} segment ({worst_frac:.0%} of that line) — likely sensor dropout"
        )
    return pass_result("saturation_by_line", "No dropout line detected")

def run_saturation_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs all saturation checks. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("saturation_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    return [
        check_low_saturation(meta),
        check_high_saturation(meta),
        check_saturation_by_line(meta),
    ]
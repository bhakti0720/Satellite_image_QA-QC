"""
statistics_check.py
Category 5: Pixel statistics — min/max/mean/std/percentiles per band.

Checks the overall distribution health of each band: is it a flat/constant
image, are values within the plausible range for Sentinel-2 L2A uint16
reflectance data, is variance suspiciously low (hints at corruption/blur).
"""

import rasterio
import numpy as np
from dataclasses import dataclass

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


@dataclass
class BandStatistics:
    band_index: int
    min: float
    max: float
    mean: float
    std: float
    p2: float    # 2nd percentile
    p98: float   # 98th percentile


def compute_band_statistics(filepath: str) -> list[BandStatistics]:
    """Reads each band and computes standard descriptive statistics."""
    stats = []
    with rasterio.open(filepath) as src:
        for band_idx in range(1, src.count + 1):
            band = src.read(band_idx).astype(np.float64)
            stats.append(BandStatistics(
                band_index=band_idx,
                min=float(np.min(band)),
                max=float(np.max(band)),
                mean=float(np.mean(band)),
                std=float(np.std(band)),
                p2=float(np.percentile(band, 2)),
                p98=float(np.percentile(band, 98)),
            ))
    return stats


def check_constant_bands(meta: RasterMetadata, std_threshold: float = 1.0) -> CheckResult:
    """
    Flags a band that's essentially flat (near-zero standard deviation).
    A real image band always has some natural pixel-to-pixel variation;
    a constant value usually means corrupted or blank data.
    """
    stats = compute_band_statistics(meta.filepath)
    flat_bands = [s.band_index for s in stats if s.std < std_threshold]

    if flat_bands:
        return fail_result(
            "constant_bands",
            Severity.CRITICAL,
            f"Band(s) {flat_bands} have near-zero variance (std < {std_threshold})"
        )
    return pass_result("constant_bands", "All bands show normal variance")


def check_value_range(meta: RasterMetadata, min_valid: int = 0, max_valid: int = 10000) -> CheckResult:
    """
    Sentinel-2 L2A surface reflectance is scaled to roughly 0-10000
    (representing 0-100% reflectance, with some headroom for bright targets).
    Values wildly outside this range suggest a scaling or dtype error.
    """
    stats = compute_band_statistics(meta.filepath)
    out_of_range_bands = [
        s.band_index for s in stats
        if s.min < min_valid or s.max > max_valid
    ]

    if out_of_range_bands:
        details = ", ".join(
            f"band {s.band_index}: [{s.min:.0f}, {s.max:.0f}]"
            for s in stats if s.band_index in out_of_range_bands
        )
        return fail_result(
            "value_range",
            Severity.WARNING,
            f"Value(s) outside expected [{min_valid}, {max_valid}] range: {details}"
        )
    return pass_result("value_range", "All bands within expected reflectance range")


def check_low_contrast(meta: RasterMetadata, min_dynamic_range: float = 100.0) -> CheckResult:
    """
    Checks the 2nd-to-98th percentile spread per band. A very narrow spread
    means the image has almost no contrast — often a symptom of blur,
    fog/haze, or a processing error, even if std isn't literally zero.
    """
    stats = compute_band_statistics(meta.filepath)
    low_contrast_bands = [
        s.band_index for s in stats
        if (s.p98 - s.p2) < min_dynamic_range
    ]

    if low_contrast_bands:
        return fail_result(
            "low_contrast",
            Severity.WARNING,
            f"Band(s) {low_contrast_bands} have narrow dynamic range (p98-p2 < {min_dynamic_range})"
        )
    return pass_result("low_contrast", "All bands show adequate dynamic range")


def run_statistics_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs all statistics checks. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("statistics_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    return [
        check_constant_bands(meta),
        check_value_range(meta),
        check_low_contrast(meta),
    ]
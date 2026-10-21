"""
nodata_check.py
Category 4: NoData analysis.

Sentinel-2 scenes in this project have no formal NoData value set — edge
padding shows up as zero pixels instead. So this check reads actual pixel
data and measures zero-pixel fraction per band, same approach used in
the Day 1 tiling filter (max_zero_fraction).
"""

import rasterio
import numpy as np

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


def compute_zero_fraction_per_band(filepath: str) -> list[float]:
    """
    Reads the raster and returns the fraction of zero-value pixels
    for each band, e.g. [0.02, 0.01, 0.015] for a 3-band image.
    """
    with rasterio.open(filepath) as src:
        fractions = []
        for band_idx in range(1, src.count + 1):
            band = src.read(band_idx)
            zero_count = np.sum(band == 0)
            total_pixels = band.size
            fractions.append(zero_count / total_pixels)
    return fractions


def check_nodata_declared(meta: RasterMetadata) -> CheckResult:
    """
    Informational only — we already know this project's data has no formal
    NoData value set. This just documents that fact per-file rather than
    treating it as a failure.
    """
    if meta.nodata_value is None:
        return pass_result("nodata_declared", "No formal NoData value set (expected for this dataset)")
    return pass_result("nodata_declared", f"NoData value: {meta.nodata_value}")


def check_zero_pixel_fraction(meta: RasterMetadata, max_zero_fraction: float = 0.05) -> CheckResult:
    """
    Checks whether any band exceeds the allowed zero-pixel fraction.
    Mirrors the Day 1 tiling filter logic — a tile shouldn't have made it
    into the dataset if it failed this, but defective test images
    (missing_data.tif) are built specifically to trip this.
    """
    fractions = compute_zero_fraction_per_band(meta.filepath)
    max_found = max(fractions)

    if max_found > max_zero_fraction:
        worst_band = fractions.index(max_found) + 1  # 1-indexed for readability
        return fail_result(
            "zero_pixel_fraction",
            Severity.CRITICAL,
            f"Band {worst_band} has {max_found:.1%} zero pixels (max allowed: {max_zero_fraction:.1%})"
        )

    return pass_result(
        "zero_pixel_fraction",
        f"Max zero fraction across bands: {max_found:.1%}"
    )


def check_nodata_spatial_pattern(meta: RasterMetadata, block_threshold: float = 0.15) -> CheckResult:
    """
    Distinguishes scattered zero pixels (often noise/sensor artifacts) from
    a large contiguous block of zeros (often a missing-data injection or
    edge-padding issue). Uses a coarse grid-based check rather than true
    connected-component analysis, to keep this fast and simple.
    """
    with rasterio.open(meta.filepath) as src:
        band1 = src.read(1)

    zero_mask = (band1 == 0)
    h, w = zero_mask.shape

    # Split into a 4x4 grid of blocks, check if any single block is
    # almost entirely zero — that signals a contiguous dropout region
    # rather than scattered noise.
    grid_size = 4
    block_h, block_w = h // grid_size, w // grid_size

    max_block_zero_fraction = 0.0
    for i in range(grid_size):
        for j in range(grid_size):
            block = zero_mask[i*block_h:(i+1)*block_h, j*block_w:(j+1)*block_w]
            block_fraction = np.sum(block) / block.size
            max_block_zero_fraction = max(max_block_zero_fraction, block_fraction)

    if max_block_zero_fraction > block_threshold:
        return fail_result(
            "nodata_spatial_pattern",
            Severity.WARNING,
            f"Contiguous zero-data block detected (block zero fraction: {max_block_zero_fraction:.1%})"
        )

    return pass_result("nodata_spatial_pattern", "No contiguous dropout blocks detected")


def run_nodata_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs all NoData checks. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("nodata_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    return [
        check_nodata_declared(meta),
        check_zero_pixel_fraction(meta),
        check_nodata_spatial_pattern(meta),
    ]
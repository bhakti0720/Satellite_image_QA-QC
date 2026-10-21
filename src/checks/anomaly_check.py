"""
anomaly_check.py
Category 8 (visual artifact detection): Spatial anomaly detection.

Splits the image into a grid of blocks, computes each block's mean pixel
value, and flags any block whose mean deviates far from the image's
overall block-mean distribution (using a z-score-style threshold). This
generalizes nodata_check.py's spatial pattern check (which only looks for
zero-pixel concentration) to catch any localized statistical outlier
region -- unusual brightness, texture, or artifacts confined to one area,
not just dropout blocks.
"""

import rasterio
import numpy as np

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


def compute_block_means(filepath: str, grid_size: int = 8) -> np.ndarray:
    """
    Reads band 1, splits it into a grid_size x grid_size grid of blocks,
    and returns a 2D array of each block's mean pixel value.
    A finer grid (8x8) than nodata_check.py's 4x4 is used here since we're
    looking for smaller, more localized anomalies, not just large dropout
    regions.
    """
    with rasterio.open(filepath) as src:
        band1 = src.read(1).astype(np.float64)

    h, w = band1.shape
    block_h, block_w = h // grid_size, w // grid_size

    block_means = np.zeros((grid_size, grid_size))
    for i in range(grid_size):
        for j in range(grid_size):
            block = band1[i*block_h:(i+1)*block_h, j*block_w:(j+1)*block_w]
            block_means[i, j] = block.mean()

    return block_means


def check_spatial_anomaly(meta: RasterMetadata, grid_size: int = 8, z_threshold: float = 3.5) -> CheckResult:
    """
    Flags a tile if any grid block's value deviates significantly from
    the robust (median-based) center of the block-mean distribution.

    Uses median + MAD (median absolute deviation) instead of mean + std.
    EMPIRICAL FINDING: mean+std was tested first and found to fail badly
    when the anomaly itself is large relative to the grid (e.g. a 25%
    dropout region inflated std from ~466 to ~1052 on missing_data_2.tif,
    making the actual zero-blocks score only 1.6 std from the mean --
    well under threshold). Median and MAD are far more resistant to being
    dragged around by a large contaminated cluster, since median just
    picks a positional middle value rather than being pulled by magnitude.
    z_threshold raised to 3.5 (from a mean+std default of 2.5) since
    MAD-based z-scores use a different scale correction (see the 0.6745
    constant below) and the two aren't directly comparable numbers.
    """
    block_means = compute_block_means(meta.filepath, grid_size)

    median = np.median(block_means)
    mad = np.median(np.abs(block_means - median))

    # Guard against a near-uniform image (already caught by constant_bands
    # in statistics_check.py, but avoid a divide-by-zero here too)
    if mad < 1e-6:
        return pass_result("spatial_anomaly", "Image too uniform to evaluate block variance")

    # 0.6745 is the standard scale factor that makes MAD comparable to a
    # normal distribution's standard deviation -- a well-known constant
    # from robust statistics, not something we invented.
    modified_z_scores = 0.6745 * np.abs(block_means - median) / mad
    max_z = modified_z_scores.max()

    if max_z > z_threshold:
        worst_block = np.unravel_index(np.argmax(modified_z_scores), modified_z_scores.shape)
        return fail_result(
            "spatial_anomaly",
            Severity.WARNING,
            f"Block {worst_block} deviates {max_z:.1f} (modified z-score) from image median — possible localized anomaly"
        )
    return pass_result("spatial_anomaly", f"Max block deviation: {max_z:.1f} (modified z-score) — within normal range")

def run_anomaly_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs spatial anomaly check. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("anomaly_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    return [check_spatial_anomaly(meta)]
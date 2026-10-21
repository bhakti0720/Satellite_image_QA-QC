"""
blur_check.py
Category 7 (OpenCV image quality): Blur detection via Laplacian variance.

Converts the RGB tile to grayscale, applies a Laplacian filter, and measures
the variance of the result. Sharp images have high-frequency edge detail
(high variance); blurred images lose that detail (low variance).
"""

import rasterio
import numpy as np
import cv2

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


def compute_laplacian_variance(filepath: str) -> float:
    """
    Reads the RGB bands, converts to an 8-bit grayscale image (required by
    OpenCV's Laplacian for consistent, interpretable results), and returns
    the variance of the Laplacian-filtered image.
    """
    with rasterio.open(filepath) as src:
        if src.count < 3:
            gray = src.read(1).astype(np.float64)
        else:
            r = src.read(1).astype(np.float64)
            g = src.read(2).astype(np.float64)
            b = src.read(3).astype(np.float64)

            # Standard luminance-weighted grayscale conversion (same weights used
            # by most image libraries, based on human eye sensitivity to each color)
            gray = 0.299 * r + 0.587 * g + 0.114 * b

    # Our data is uint16 reflectance (~0-10000+), but OpenCV's Laplacian
    # expects standard 8-bit (0-255) images for predictable, comparable
    # results. Normalize using percentile stretch (same 2-98 percentile
    # idea used in statistics_check.py) rather than raw min/max, to avoid
    # outlier pixels compressing the useful range.
    p2, p98 = np.percentile(gray, [2, 98])
    gray_stretched = np.clip((gray - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)

    laplacian = cv2.Laplacian(gray_stretched, cv2.CV_64F)
    return float(laplacian.var())


def check_blur(meta: RasterMetadata, min_variance: float = 100.0) -> CheckResult:
    """
    Flags images with Laplacian variance below the threshold as blurred.
    NOTE: min_variance is dataset-dependent and typically needs empirical
    tuning — see the manual test script for how this threshold was chosen.
    """
    variance = compute_laplacian_variance(meta.filepath)

    if variance < min_variance:
        return fail_result(
            "blur_check",
            Severity.WARNING,
            f"Laplacian variance {variance:.1f} is below threshold {min_variance} — image appears blurred"
        )
    return pass_result("blur_check", f"Laplacian variance: {variance:.1f}")


def run_blur_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs blur check. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("blur_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    return [check_blur(meta)]
"""
noise_check.py
Category 7 (OpenCV image quality): Noise estimation.

Uses the Immerkaer (1996) fast noise estimation method: convolves the
image with a kernel specifically constructed so that smooth regions and
real edges cancel out to near-zero, while random per-pixel noise does not.
This is more robust than a simple median-filter residual, which was found
(empirically, on this project's data) to be dominated by real scene texture
rather than actual noise -- see test_noise_calibration.py results, where
median-residual noisy defects (8.5-11.0) fell entirely inside the clean
tile range (1.6-21.7).
"""

import rasterio
import numpy as np
import cv2

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


# Immerkaer's noise-estimation kernel -- constructed so smooth gradients
# and most real edges convolve to ~0, while random noise does not.
_NOISE_KERNEL = np.array([
    [1, -2, 1],
    [-2, 4, -2],
    [1, -2, 1]
], dtype=np.float64)


def compute_noise_estimate(filepath: str) -> float:
    """
    Reads RGB bands or a single grayscale band, converts to normalized
    8-bit grayscale, and estimates the noise standard deviation using the
    Immerkaer method.
    """
    with rasterio.open(filepath) as src:
        if src.count < 3:
            gray = src.read(1).astype(np.float64)
        else:
            r = src.read(1).astype(np.float64)
            g = src.read(2).astype(np.float64)
            b = src.read(3).astype(np.float64)
            gray = 0.299 * r + 0.587 * g + 0.114 * b

    p2, p98 = np.percentile(gray, [2, 98])
    gray_stretched = np.clip((gray - p2) / (p98 - p2) * 255, 0, 255).astype(np.float64)

    h, w = gray_stretched.shape
    convolved = cv2.filter2D(gray_stretched, -1, _NOISE_KERNEL)

    sigma = np.sqrt(np.pi / 2) / (6 * (w - 2) * (h - 2)) * np.sum(np.abs(convolved))
    return float(sigma)


def check_noise(meta: RasterMetadata, max_noise_sigma: float = 4.2) -> CheckResult:
    """
    Flags images with estimated noise sigma above the threshold.
    Threshold requires empirical validation -- see manual test script.
    """
    noise_estimate = compute_noise_estimate(meta.filepath)

    if noise_estimate > max_noise_sigma:
        return fail_result(
            "noise_check",
            Severity.WARNING,
            f"Estimated noise sigma {noise_estimate:.3f} exceeds threshold {max_noise_sigma} — image appears noisy"
        )
    return pass_result("noise_check", f"Estimated noise sigma: {noise_estimate:.3f}")


def run_noise_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs noise check. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("noise_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    return [check_noise(meta)]
"""
metadata_checks.py
Category 2: Metadata checks — dimensions, dtype, resolution sanity.
Operates on a RasterMetadata object (already produced by RasterInspector).
"""

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


def check_dimensions(meta: RasterMetadata, expected_size: int = 512) -> CheckResult:
    """Are width and height exactly the expected tile size?"""
    if meta.width != expected_size or meta.height != expected_size:
        return fail_result(
            "dimensions",
            Severity.CRITICAL,
            f"Expected {expected_size}x{expected_size}, found {meta.width}x{meta.height}"
        )
    return pass_result("dimensions", f"{meta.width}x{meta.height}")


def check_dtype(meta: RasterMetadata, expected_dtype: str = "uint16") -> CheckResult:
    """Is the pixel data type what Sentinel-2 L2A data should be?"""
    if meta.dtype != expected_dtype:
        return fail_result(
            "dtype",
            Severity.WARNING,
            f"Expected dtype '{expected_dtype}', found '{meta.dtype}'"
        )
    return pass_result("dtype", f"dtype: {meta.dtype}")


def check_pixel_resolution(meta: RasterMetadata, expected_res: float = 10.0, tolerance: float = 0.01) -> CheckResult:
    """Is the pixel resolution ~10m, matching Sentinel-2 R10m bands?"""
    if meta.pixel_size_x is None or meta.pixel_size_y is None:
        return fail_result("pixel_resolution", Severity.CRITICAL, "Pixel size unavailable — no transform found")

    x_ok = abs(meta.pixel_size_x - expected_res) <= tolerance
    y_ok = abs(meta.pixel_size_y - expected_res) <= tolerance

    if not (x_ok and y_ok):
        return fail_result(
            "pixel_resolution",
            Severity.WARNING,
            f"Expected ~{expected_res}m pixels, found {meta.pixel_size_x}m x {meta.pixel_size_y}m"
        )
    return pass_result("pixel_resolution", f"{meta.pixel_size_x}m x {meta.pixel_size_y}m")


def check_square_pixels(meta: RasterMetadata, tolerance: float = 0.01) -> CheckResult:
    """Are pixel_size_x and pixel_size_y equal? Non-square pixels usually mean a resampling/warp error."""
    if meta.pixel_size_x is None or meta.pixel_size_y is None:
        return fail_result("square_pixels", Severity.CRITICAL, "Pixel size unavailable — no transform found")

    diff = abs(meta.pixel_size_x - meta.pixel_size_y)
    if diff > tolerance:
        return fail_result(
            "square_pixels",
            Severity.WARNING,
            f"Non-square pixels: {meta.pixel_size_x}m x {meta.pixel_size_y}m"
        )
    return pass_result("square_pixels")


def run_metadata_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs all metadata checks. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("metadata_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    return [
        check_dimensions(meta),
        check_dtype(meta),
        check_pixel_resolution(meta),
        check_square_pixels(meta),
    ]
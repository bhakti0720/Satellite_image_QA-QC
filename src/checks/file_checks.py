"""
file_checks.py
Category 1: File integrity checks.
Operates on a RasterMetadata object (already produced by RasterInspector).
"""

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


def check_file_opens(meta: RasterMetadata) -> CheckResult:
    """Was the file readable by rasterio at all?"""
    if not meta.is_valid:
        return fail_result(
            "file_opens",
            Severity.CRITICAL,
            f"File could not be opened: {meta.error_message}"
        )
    return pass_result("file_opens")


def check_file_size(meta: RasterMetadata, min_bytes: int = 1024) -> CheckResult:
    """Is the file suspiciously small (likely truncated/corrupt)?"""
    if meta.file_size_bytes < min_bytes:
        return fail_result(
            "file_size",
            Severity.CRITICAL,
            f"File size {meta.file_size_bytes} bytes is below minimum {min_bytes} bytes"
        )
    return pass_result("file_size", f"File size {meta.file_size_bytes} bytes")


def check_driver(meta: RasterMetadata, expected_driver: str = "GTiff") -> CheckResult:
    """Is the file actually a GeoTIFF, not some other format with a .tif extension?"""
    if not meta.is_valid:
        return fail_result("driver_check", Severity.CRITICAL, "Cannot check driver — file did not open")
    if meta.driver != expected_driver:
        return fail_result(
            "driver_check",
            Severity.WARNING,
            f"Expected driver '{expected_driver}', found '{meta.driver}'"
        )
    return pass_result("driver_check", f"Driver: {meta.driver}")


def check_band_count(meta: RasterMetadata, expected_bands: int = 3) -> CheckResult:
    """Does the file have the expected number of bands?"""
    if not meta.is_valid:
        return fail_result("band_count", Severity.CRITICAL, "Cannot check bands — file did not open")
    if meta.band_count != expected_bands:
        return fail_result(
            "band_count",
            Severity.CRITICAL,
            f"Expected {expected_bands} bands, found {meta.band_count}"
        )
    return pass_result("band_count", f"Bands: {meta.band_count}")


def run_file_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs all file integrity checks and returns the full list of results."""
    results = [check_file_opens(meta)]

    # If the file didn't even open, skip checks that need a valid raster —
    # they'd all just report the same failure redundantly.
    if not meta.is_valid:
        return results

    results.append(check_file_size(meta))
    results.append(check_driver(meta))
    results.append(check_band_count(meta))
    return results
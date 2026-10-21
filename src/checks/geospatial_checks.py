"""
geospatial_checks.py
Category 3: Geospatial validation — CRS correctness, transform sanity, extent checks.
Operates on a RasterMetadata object (already produced by RasterInspector).
"""

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


def check_crs_present(meta: RasterMetadata) -> CheckResult:
    """Does the file have any CRS defined at all?"""
    if meta.crs is None:
        return fail_result("crs_present", Severity.CRITICAL, "No CRS defined on this raster")
    return pass_result("crs_present", f"CRS: {meta.crs}")


def check_crs_matches_expected(meta: RasterMetadata, expected_crs: str = "EPSG:32642") -> CheckResult:
    """Is the CRS the one this project standardizes on (UTM 42N for Ahmedabad)?"""
    if meta.crs is None:
        return fail_result("crs_matches_expected", Severity.CRITICAL, "Cannot check — no CRS present")
    if meta.crs != expected_crs:
        return fail_result(
            "crs_matches_expected",
            Severity.CRITICAL,
            f"Expected {expected_crs}, found {meta.crs}"
        )
    return pass_result("crs_matches_expected", f"CRS matches: {meta.crs}")


def check_transform_valid(meta: RasterMetadata) -> CheckResult:
    """Is the affine transform non-degenerate (not all zeros / identity placeholder)?"""
    if meta.transform is None:
        return fail_result("transform_valid", Severity.CRITICAL, "No transform found")

    a, b, c, d, e, f = meta.transform
    # a and e are pixel width/height — if both are 0, the transform is meaningless
    if a == 0 and e == 0:
        return fail_result("transform_valid", Severity.CRITICAL, "Degenerate transform (zero pixel size)")
    return pass_result("transform_valid", "Transform is valid")


def check_no_rotation(meta: RasterMetadata, tolerance: float = 1e-6) -> CheckResult:
    """
    Are b and d (the rotation/shear terms) close to zero?
    Sentinel-2 tiles should be north-up with no rotation.
    """
    if meta.transform is None:
        return fail_result("no_rotation", Severity.CRITICAL, "No transform found")

    a, b, c, d, e, f = meta.transform
    if abs(b) > tolerance or abs(d) > tolerance:
        return fail_result(
            "no_rotation",
            Severity.WARNING,
            f"Unexpected rotation/shear in transform: b={b}, d={d}"
        )
    return pass_result("no_rotation")


def check_bounds_sane(meta: RasterMetadata) -> CheckResult:
    """Are the bounds a real, non-zero-area box?"""
    if meta.bounds is None:
        return fail_result("bounds_sane", Severity.CRITICAL, "No bounds found")

    left, bottom, right, top = meta.bounds
    width = right - left
    height = top - bottom

    if width <= 0 or height <= 0:
        return fail_result(
            "bounds_sane",
            Severity.CRITICAL,
            f"Degenerate bounds: width={width}, height={height}"
        )
    return pass_result("bounds_sane", f"Extent: {width}m x {height}m")


def run_geospatial_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs all geospatial checks. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("geospatial_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    return [
        check_crs_present(meta),
        check_crs_matches_expected(meta),
        check_transform_valid(meta),
        check_no_rotation(meta),
        check_bounds_sane(meta),
    ]
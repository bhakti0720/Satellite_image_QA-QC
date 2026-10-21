"""
cloud_check.py
Category 9: Cloud/scene analysis via SCL (Scene Classification Layer) bands.

Reads the SCL companion tile (saved alongside each RGB tile by raw_data.py,
named <tile_name>_scl.tif) and computes the fraction of pixels falling into
cloud, cloud-shadow, and no-data classes. SCL class codes reference:
  0=no data, 1=saturated/defective, 2=dark area, 3=cloud shadow,
  4=vegetation, 5=bare soil, 6=water, 7=cloud low prob, 8=cloud medium
  prob, 9=cloud high prob, 10=cirrus, 11=snow/ice
"""

import rasterio
import numpy as np
import os

from src.inspector.raster_inspector import RasterMetadata
from src.checks.base import CheckResult, Severity, pass_result, fail_result


# SCL class code groupings
SCL_NO_DATA = {0}
SCL_CLOUD = {7, 8, 9, 10}      # low/medium/high prob cloud + cirrus
SCL_CLOUD_SHADOW = {3}
SCL_SATURATED_DEFECTIVE = {1}


def get_scl_path(rgb_filepath: str) -> str:
    """Derives the SCL companion filepath from the RGB tile's filepath."""
    base, ext = os.path.splitext(rgb_filepath)
    return f"{base}_scl{ext}"


def compute_scl_class_fractions(rgb_filepath: str) -> dict:
    """
    Reads the SCL companion tile and returns the fraction of pixels in
    each relevant class grouping.
    """
    scl_path = get_scl_path(rgb_filepath)

    with rasterio.open(scl_path) as src:
        scl = src.read(1)

    total = scl.size
    cloud_frac = float(np.isin(scl, list(SCL_CLOUD)).sum()) / total
    shadow_frac = float(np.isin(scl, list(SCL_CLOUD_SHADOW)).sum()) / total
    nodata_frac = float(np.isin(scl, list(SCL_NO_DATA)).sum()) / total
    defective_frac = float(np.isin(scl, list(SCL_SATURATED_DEFECTIVE)).sum()) / total

    return {
        "cloud_frac": cloud_frac,
        "shadow_frac": shadow_frac,
        "nodata_frac": nodata_frac,
        "defective_frac": defective_frac,
    }


def check_scl_available(meta: RasterMetadata) -> CheckResult:
    """Confirms the SCL companion file actually exists before other checks run."""
    scl_path = get_scl_path(meta.filepath)
    if not os.path.exists(scl_path):
        return fail_result(
            "scl_available",
            Severity.WARNING,
            f"No SCL companion file found at {scl_path} — cloud checks skipped"
        )
    return pass_result("scl_available", f"SCL file found: {os.path.basename(scl_path)}")


def check_cloud_coverage(meta: RasterMetadata, max_cloud_fraction: float = 0.20) -> CheckResult:
    """
    Flags a tile with too much cloud coverage to be reliably usable.
    20% is a common general-purpose threshold in remote sensing pipelines,
    but this is a reasonable starting default, not empirically tuned
    against this project's specific tiles yet.
    """
    fractions = compute_scl_class_fractions(meta.filepath)
    cloud_frac = fractions["cloud_frac"]

    if cloud_frac > max_cloud_fraction:
        return fail_result(
            "cloud_coverage",
            Severity.WARNING,
            f"Cloud coverage {cloud_frac:.1%} exceeds threshold {max_cloud_fraction:.0%}"
        )
    return pass_result("cloud_coverage", f"Cloud coverage: {cloud_frac:.1%}")


def check_shadow_coverage(meta: RasterMetadata, max_shadow_fraction: float = 0.15) -> CheckResult:
    """Flags a tile with too much cloud-shadow coverage."""
    fractions = compute_scl_class_fractions(meta.filepath)
    shadow_frac = fractions["shadow_frac"]

    if shadow_frac > max_shadow_fraction:
        return fail_result(
            "shadow_coverage",
            Severity.WARNING,
            f"Cloud shadow coverage {shadow_frac:.1%} exceeds threshold {max_shadow_fraction:.0%}"
        )
    return pass_result("shadow_coverage", f"Shadow coverage: {shadow_frac:.1%}")


def check_scl_nodata_defective(meta: RasterMetadata, max_bad_fraction: float = 0.05) -> CheckResult:
    """
    Flags a tile where SCL itself reports a significant fraction of
    no-data or saturated/defective pixels -- an independent cross-check
    against your existing nodata_check.py, since this comes from the
    scene classification algorithm rather than raw zero-pixel counting.
    """
    fractions = compute_scl_class_fractions(meta.filepath)
    bad_frac = fractions["nodata_frac"] + fractions["defective_frac"]

    if bad_frac > max_bad_fraction:
        return fail_result(
            "scl_nodata_defective",
            Severity.CRITICAL,
            f"SCL reports {bad_frac:.1%} no-data/defective pixels (threshold {max_bad_fraction:.0%})"
        )
    return pass_result("scl_nodata_defective", f"SCL no-data/defective: {bad_frac:.1%}")


def run_cloud_checks(meta: RasterMetadata) -> list[CheckResult]:
    """Runs all cloud/scene checks. Assumes meta.is_valid is already True — caller's responsibility."""
    if not meta.is_valid:
        return [fail_result("cloud_checks", Severity.CRITICAL, "Cannot run — file did not open")]

    availability = check_scl_available(meta)
    if not availability.passed:
        # Can't run pixel-based checks without the SCL file — return early
        return [availability]

    return [
        availability,
        check_cloud_coverage(meta),
        check_shadow_coverage(meta),
        check_scl_nodata_defective(meta),
    ]
"""
test_qa_engine.py
Verifies the full QA pipeline correctly identifies each known defect type,
and correctly passes a clean tile. Acts as a regression guard -- if a
future change to any check module breaks detection of a known defect,
these tests will catch it.
"""

import pytest
from src.engine.qa_engine import run_qa


CLEAN_TILE = "data/dataset/scene2_tile_r6144_c5120.tif"


def test_clean_tile_passes():
    """A known-clean tile should pass overall QA."""
    result = run_qa(CLEAN_TILE)
    assert result.passed is True
    assert result.score > 0


def test_corrupt_file_fails_with_file_opens():
    """A corrupt/unreadable file should hard-fail on file_opens."""
    # Create a throwaway corrupt file for this test
    import os
    corrupt_path = "data/test/_pytest_corrupt.tif"
    with open(corrupt_path, "w") as f:
        f.write("not a real tif")

    result = run_qa(corrupt_path)
    assert result.passed is False
    critical_names = [c.check_name for c in result.critical_failures()]
    assert "file_opens" in critical_names

    os.remove(corrupt_path)


def test_wrong_crs_fails_with_crs_check():
    """A tile with the wrong CRS should hard-fail on crs_matches_expected."""
    result = run_qa("data/test/wrong_crs_2.tif")
    assert result.passed is False
    critical_names = [c.check_name for c in result.critical_failures()]
    assert "crs_matches_expected" in critical_names


def test_missing_data_fails_with_zero_pixel_fraction():
    """A tile with an injected dropout region should hard-fail on zero_pixel_fraction."""
    result = run_qa("data/test/missing_data_2.tif")
    assert result.passed is False
    critical_names = [c.check_name for c in result.critical_failures()]
    assert "zero_pixel_fraction" in critical_names


def test_black_line_fails_with_saturation_by_line():
    """A tile with an injected dropout line should hard-fail on saturation_by_line."""
    result = run_qa("data/test/black_line_2.tif")
    assert result.passed is False
    critical_names = [c.check_name for c in result.critical_failures()]
    assert "saturation_by_line" in critical_names


def test_blurred_tile_fails_blur_check():
    """A blurred tile should fail blur_check specifically (may still pass overall)."""
    result = run_qa("data/test/blurred_2.tif")
    check_names_failed = [c.check_name for c in result.all_checks if not c.passed]
    assert "blur_check" in check_names_failed
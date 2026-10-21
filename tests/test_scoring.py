"""
test_scoring.py
Verifies the two-tier scoring logic: critical failures hard-fail
regardless of other results, and weighted warnings correctly push the
score up or down against the passing threshold.
"""

from src.engine.results import QAResult
from src.engine.scoring import score_qa_result
from src.checks.base import CheckResult, Severity
from src.inspector.raster_inspector import RasterMetadata


def _make_fake_meta():
    return RasterMetadata(filepath="fake.tif", filename="fake.tif", file_size_bytes=1000, is_valid=True)


def test_clean_result_scores_100():
    result = QAResult(filepath="clean.tif", filename="clean.tif", metadata=_make_fake_meta(), all_checks=[
        CheckResult("dimensions", True, Severity.INFO, "OK"),
    ])
    score_qa_result(result)
    assert result.score == 100.0
    assert result.passed is True


def test_critical_failure_forces_zero_score():
    """A CRITICAL failure should hard-fail regardless of any passing checks."""
    result = QAResult(filepath="broken.tif", filename="broken.tif", metadata=_make_fake_meta(), all_checks=[
        CheckResult("band_count", False, Severity.CRITICAL, "Wrong band count"),
        CheckResult("blur_check", True, Severity.INFO, "OK"),
    ])
    score_qa_result(result)
    assert result.score == 0.0
    assert result.passed is False


def test_warnings_reduce_score_but_can_still_pass():
    result = QAResult(filepath="moderate.tif", filename="moderate.tif", metadata=_make_fake_meta(), all_checks=[
        CheckResult("dtype", False, Severity.WARNING, "Wrong dtype"),       # -5
        CheckResult("value_range", False, Severity.WARNING, "Out of range"), # -8
    ])
    score_qa_result(result)
    assert result.score == 87.0
    assert result.passed is True


def test_many_warnings_push_score_below_threshold():
    result = QAResult(filepath="bad.tif", filename="bad.tif", metadata=_make_fake_meta(), all_checks=[
        CheckResult("blur_check", False, Severity.WARNING, "Blurred"),        # -15
        CheckResult("noise_check", False, Severity.WARNING, "Noisy"),         # -10
        CheckResult("striping_check", False, Severity.WARNING, "Striped"),    # -12
        CheckResult("cloud_coverage", False, Severity.WARNING, "Too cloudy"), # -12
    ])
    score_qa_result(result)
    assert result.score == 51.0
    assert result.passed is False
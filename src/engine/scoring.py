"""
scoring.py
Two-tier QA scoring:
  Tier 1 (hard gate): any CRITICAL-severity failure anywhere -> auto-fail,
    regardless of everything else.
  Tier 2 (weighted score): for images that clear Tier 1, compute a 0-100
    score based on WARNING-severity failures, weighted by how much each
    check type matters to overall image usability.

Weights below are a first-pass judgment call, not empirically derived --
worth revisiting once you have more real-world images to validate against.
Candidate for moving into config/thresholds.yaml once that's built, so
weights are tunable without editing code.
"""

from src.engine.results import QAResult
from src.checks.base import Severity


# Points deducted from a starting score of 100 for each failed WARNING-level
# check, by check_name. A check not listed here falls back to DEFAULT_WEIGHT.
CHECK_WEIGHTS = {
    # metadata / geospatial
    "dtype": 5,
    "pixel_resolution": 8,
    "square_pixels": 5,

    # driver-level (file_checks)
    "driver_check": 5,

    # statistics
    "value_range": 8,
    "low_contrast": 10,

    # saturation
    "low_saturation": 8,
    "high_saturation": 8,

    # image quality (Day 3)
    "blur_check": 15,
    "noise_check": 10,
    "striping_check": 12,

    # nodata / spatial pattern
    "nodata_spatial_pattern": 10,

    # cloud / scene
    "cloud_coverage": 12,
    "shadow_coverage": 8,
}

DEFAULT_WEIGHT = 5  # fallback for any WARNING-level check not explicitly listed


def has_critical_failure(qa_result: QAResult) -> bool:
    """Tier 1 gate: does any check report a failed CRITICAL result?"""
    return len(qa_result.critical_failures()) > 0


def compute_weighted_score(qa_result: QAResult) -> float:
    """
    Tier 2: starts at 100, deducts weighted points for each failed
    WARNING-level check. INFO-level results and passed checks never
    affect the score. Floors at 0 (can't go negative).
    """
    score = 100.0
    for check in qa_result.all_checks:
        if not check.passed and check.severity == Severity.WARNING:
            weight = CHECK_WEIGHTS.get(check.check_name, DEFAULT_WEIGHT)
            score -= weight
    return max(0.0, score)


def score_qa_result(qa_result: QAResult, min_passing_score: float = 60.0) -> QAResult:
    """
    Applies the full two-tier scoring logic to a QAResult, mutating it
    in place (sets passed, score, fail_reason) and returning it for
    convenient chaining.
    """
    if has_critical_failure(qa_result):
        qa_result.passed = False
        qa_result.score = 0.0
        critical_names = [c.check_name for c in qa_result.critical_failures()]
        qa_result.fail_reason = f"Critical failure(s): {', '.join(critical_names)}"
        return qa_result

    score = compute_weighted_score(qa_result)
    qa_result.score = score

    if score < min_passing_score:
        qa_result.passed = False
        warning_names = [c.check_name for c in qa_result.warnings()]
        qa_result.fail_reason = f"Score {score:.1f} below threshold {min_passing_score} (warnings: {', '.join(warning_names)})"
    else:
        qa_result.passed = True
        qa_result.fail_reason = None

    return qa_result
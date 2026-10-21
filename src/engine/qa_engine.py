"""
qa_engine.py
The orchestrator: takes one filepath, runs RasterInspector, runs all nine
QA check categories against it, bundles everything into a QAResult, scores
it, and returns the final result. This is the single entry point the rest
of the project (batch processing, reporting) should call.
"""

from src.inspector.raster_inspector import RasterInspector
from src.engine.results import QAResult
from src.engine.scoring import score_qa_result

from src.checks.file_checks import run_file_checks
from src.checks.metadata_checks import run_metadata_checks
from src.checks.geospatial_checks import run_geospatial_checks
from src.checks.nodata_check import run_nodata_checks
from src.checks.statistics_check import run_statistics_checks
from src.checks.saturation_check import run_saturation_checks
from src.checks.blur_check import run_blur_checks
from src.checks.noise_check import run_noise_checks
from src.checks.blackline_check import run_blackline_checks
from src.checks.cloud_check import run_cloud_checks
from src.checks.anomaly_check import run_anomaly_checks

def run_qa(filepath: str, min_passing_score: float = 60.0) -> QAResult:
    """
    Runs the full nine-category QA pipeline against a single file and
    returns a scored QAResult.
    """
    meta = RasterInspector(filepath).inspect()

    all_checks = []

    # File checks run first and unconditionally -- everything else
    # depends on the file having opened successfully.
    file_results = run_file_checks(meta)
    all_checks.extend(file_results)

    # If the file didn't open, there's no point running checks that need
    # real metadata/pixel data -- they'd all crash or report nonsense.
    # Short-circuit here, same early-return pattern used throughout every
    # individual check module's run_*_checks() function.
    if not meta.is_valid:
        result = QAResult(
            filepath=filepath,
            filename=meta.filename,
            metadata=meta,
            all_checks=all_checks,
        )
        return score_qa_result(result, min_passing_score)

    # File opened successfully -- run the remaining eight categories.
    all_checks.extend(run_metadata_checks(meta))
    all_checks.extend(run_geospatial_checks(meta))
    all_checks.extend(run_nodata_checks(meta))
    all_checks.extend(run_statistics_checks(meta))
    all_checks.extend(run_saturation_checks(meta))
    all_checks.extend(run_blur_checks(meta))
    all_checks.extend(run_noise_checks(meta))
    all_checks.extend(run_blackline_checks(meta))
    all_checks.extend(run_cloud_checks(meta))
    all_checks.extend(run_anomaly_checks(meta)) 

    result = QAResult(
        filepath=filepath,
        filename=meta.filename,
        metadata=meta,
        all_checks=all_checks,
    )
    return score_qa_result(result, min_passing_score)
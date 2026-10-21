"""
batch_qa.py
Runs the full QA pipeline (all 10 check categories) across an entire
folder of tiles, and writes consolidated CSV + JSON reports covering
every file in one run.
"""

import sys
import time
from pathlib import Path

# Allow running this script directly (python scripts/batch_qa.py) by
# adding the project root to the import path -- needed because this
# script lives in scripts/, not the project root, so "from src..." 
# imports wouldn't resolve without this.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.engine.qa_engine import run_qa
from src.reporting.csv_report import write_csv_report
from src.reporting.json_report import write_json_report


def find_tiles(folder: str) -> list[str]:
    """
    Finds all QA-able tile files in a folder, excluding:
    - SCL companion files (*_scl.tif) -- these are single-band metadata
      files for cloud_check.py, not standalone images to QA
    - Full-scene reference files (*_RGB_full.tif) -- these are large
      reference scenes, not individual 512x512 tiles
    """
    folder_path = Path(folder)
    all_tifs = list(folder_path.glob("*.tif"))

    tiles = [
        str(p) for p in all_tifs
        if not p.name.endswith("_scl.tif") and not p.name.endswith("_RGB_full.tif")
    ]
    return sorted(tiles)


def run_batch_qa(
    input_folders: list[str],
    csv_output: str = "reports/csv/batch_qa_report.csv",
    json_output: str = "reports/json/batch_qa_report.json",
    min_passing_score: float = 60.0,
) -> list:
    """
    Runs QA across every tile in the given folders, prints progress,
    writes consolidated CSV + JSON reports, and returns the full list
    of QAResults for any further use.
    """
    all_tiles = []
    for folder in input_folders:
        found = find_tiles(folder)
        print(f"Found {len(found)} tiles in {folder}")
        all_tiles.extend(found)

    print(f"\nRunning QA on {len(all_tiles)} tiles total...\n")

    results = []
    start_time = time.time()

    for i, filepath in enumerate(all_tiles, start=1):
        result = run_qa(filepath, min_passing_score=min_passing_score)
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"[{i}/{len(all_tiles)}] {status} (score {result.score:.0f}) — {result.filename}")

    elapsed = time.time() - start_time
    print(f"\nCompleted {len(all_tiles)} tiles in {elapsed:.1f}s")

    # Summary stats
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    avg_score = sum(r.score for r in results) / len(results) if results else 0

    print(f"\n--- Summary ---")
    print(f"Passed: {passed_count}/{len(results)}")
    print(f"Failed: {failed_count}/{len(results)}")
    print(f"Average score: {avg_score:.1f}")

    write_csv_report(results, csv_output)
    write_json_report(results, json_output)

    return results


if __name__ == "__main__":
    run_batch_qa(
        input_folders=["data/dataset", "data/test"],
    )
from src.inspector.raster_inspector import RasterInspector
from src.checks.nodata_check import run_nodata_checks

test_files = [
    "data/dataset/scene1_tile_r5120_c1536.tif",       # clean tile
    "data/test/missing_data_1.tif",                   # replace with your actual missing_data defect filename
]

for path in test_files:
    meta = RasterInspector(path).inspect()
    results = run_nodata_checks(meta)
    print(f"\n--- {path} ---")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.check_name} ({r.severity.value}): {r.message}")
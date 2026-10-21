from src.inspector.raster_inspector import RasterInspector
from src.checks.geospatial_checks import run_geospatial_checks

test_files = [
    "data/dataset/scene1_tile_r5120_c1536.tif",   # your known-good tile
    "data/test/wrong_crs_2.tif",                  # should FAIL crs_matches_expected
]

for path in test_files:
    meta = RasterInspector(path).inspect()
    results = run_geospatial_checks(meta)
    print(f"\n--- {path} ---")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.check_name} ({r.severity.value}): {r.message}")
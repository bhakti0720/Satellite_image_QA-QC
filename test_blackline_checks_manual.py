from src.inspector.raster_inspector import RasterInspector
from src.checks.blackline_check import run_blackline_checks

test_files = [
    "data/dataset/scene2_tile_r6144_c5120.tif",
    "data/test/black_line_2.tif",
]

for path in test_files:
    meta = RasterInspector(path).inspect()
    results = run_blackline_checks(meta)
    print(f"\n--- {path} ---")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.check_name} ({r.severity.value}): {r.message}")
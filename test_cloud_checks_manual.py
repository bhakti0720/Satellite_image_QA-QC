from src.inspector.raster_inspector import RasterInspector
from src.checks.cloud_check import run_cloud_checks, compute_scl_class_fractions

test_files = [
    "data/dataset/scene2_tile_r6144_c5120.tif",   # has SCL companion
    "data/dataset/scene2_tile_r5120_c1536.tif",    # does NOT have SCL companion
]

for path in test_files:
    print(f"\n--- {path} ---")
    meta = RasterInspector(path).inspect()
    results = run_cloud_checks(meta)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.check_name} ({r.severity.value}): {r.message}")
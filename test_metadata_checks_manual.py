from src.inspector.raster_inspector import RasterInspector
from src.checks.metadata_checks import run_metadata_checks

test_files = [
    "data/dataset/scene1_tile_r5120_c1536.tif",       # replace with a real clean tile
    "data/test/wrong_crs_2.tif",# replace with your wrong_crs defect
]

for path in test_files:
    meta = RasterInspector(path).inspect()
    results = run_metadata_checks(meta)
    print(f"\n--- {path} ---")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.check_name} ({r.severity.value}): {r.message}")
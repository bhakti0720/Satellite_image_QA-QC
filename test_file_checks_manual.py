from src.inspector.raster_inspector import RasterInspector
from src.checks.file_checks import run_file_checks

test_files = [
    "data/dataset/scene1_tile_r512_c8192.tif",      # replace with a real clean tile
    "data/test/noisy_1.tif",   # replace with a real defective tile
]

for path in test_files:
    meta = RasterInspector(path).inspect()
    results = run_file_checks(meta)
    print(f"\n--- {path} ---")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.check_name} ({r.severity.value}): {r.message}")
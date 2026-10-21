from src.inspector.raster_inspector import RasterInspector
from src.checks.blur_check import run_blur_checks, compute_laplacian_variance

test_files = [
    "data/dataset/scene1_tile_r5120_c1536.tif",   # clean tile
    "data/test/blurred_1.tif",                     # replace with your actual blurred defect filename
]

for path in test_files:
    variance = compute_laplacian_variance(path)
    print(f"{path}: Laplacian variance = {variance:.1f}")

    meta = RasterInspector(path).inspect()
    results = run_blur_checks(meta)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.check_name} ({r.severity.value}): {r.message}")
from src.inspector.raster_inspector import RasterInspector
from src.checks.noise_check import run_noise_checks, compute_noise_estimate

test_files = [
    "data/dataset/scene1_tile_r5120_c1536.tif",   # clean tile
    "data/test/noisy_1.tif",                       # replace with your actual noisy defect filename
]

for path in test_files:
    estimate = compute_noise_estimate(path)
    print(f"{path}: noise estimate = {estimate:.2f}")

    meta = RasterInspector(path).inspect()
    results = run_noise_checks(meta)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.check_name} ({r.severity.value}): {r.message}")
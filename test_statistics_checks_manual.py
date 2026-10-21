from src.inspector.raster_inspector import RasterInspector
from src.checks.statistics_check import run_statistics_checks, compute_band_statistics

test_files = [
    "data/dataset/scene1_tile_r5120_c1536.tif",   # clean tile
    "data/test/blurred_2.tif",                     # replace with your actual blurred defect filename
]

for path in test_files:
    meta = RasterInspector(path).inspect()
    results = run_statistics_checks(meta)
    print(f"\n--- {path} ---")

    stats = compute_band_statistics(path)
    for s in stats:
        print(f"  Band {s.band_index}: min={s.min:.0f} max={s.max:.0f} mean={s.mean:.1f} std={s.std:.1f} p2={s.p2:.0f} p98={s.p98:.0f}")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.check_name} ({r.severity.value}): {r.message}")
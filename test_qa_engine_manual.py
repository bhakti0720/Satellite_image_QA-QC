from src.engine.qa_engine import run_qa

test_files = [
    "data/dataset/scene2_tile_r6144_c5120_scl.tif",
    "data/test/wrong_crs_2.tif",
    "data/test/blurred_2.tif",
]

for path in test_files:
    result = run_qa(path)
    print(f"\n=== {result.summary()} ===")
    print(f"Score: {result.score}")
    print(f"Fail reason: {result.fail_reason}")
    print("Failed checks:")
    for c in result.all_checks:
        if not c.passed:
            print(f"  [{c.severity.value}] {c.check_name}: {c.message}")

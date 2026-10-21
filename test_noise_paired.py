import json
from src.checks.noise_check import compute_noise_estimate

with open("data/test/manifest.json") as f:
    manifest = json.load(f)

print(f"{'Defect file':<25} {'Source noise':>12} {'Defect noise':>12} {'Delta':>8}")
print("-" * 60)

for defect_path, info in manifest.items():
    if info["defect"].startswith("noisy"):
        source_path = info["source"]
        source_noise = compute_noise_estimate(source_path)
        defect_noise = compute_noise_estimate(defect_path)
        delta = defect_noise - source_noise
        print(f"{info['defect']:<25} {source_noise:>12.2f} {defect_noise:>12.2f} {delta:>+8.2f}")
import glob
from src.checks.noise_check import compute_noise_estimate

clean_tiles = glob.glob("data/dataset/*.tif")
print(f"Checking {len(clean_tiles)} clean tiles...\n")

estimates = []
for path in clean_tiles:
    v = compute_noise_estimate(path)
    estimates.append(v)
    print(f"{path}: {v:.2f}")

print(f"\nMin: {min(estimates):.2f}")
print(f"Max: {max(estimates):.2f}")
print(f"Mean: {sum(estimates)/len(estimates):.2f}")
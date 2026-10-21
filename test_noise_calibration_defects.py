import glob
from src.checks.noise_check import compute_noise_estimate

noisy_tiles = glob.glob("data/test/*noisy*.tif")
print(f"Checking {len(noisy_tiles)} noisy defect tiles...\n")

estimates = []
for path in noisy_tiles:
    v = compute_noise_estimate(path)
    estimates.append(v)
    print(f"{path}: {v:.2f}")

print(f"\nMin: {min(estimates):.2f}")
print(f"Max: {max(estimates):.2f}")
print(f"Mean: {sum(estimates)/len(estimates):.2f}")
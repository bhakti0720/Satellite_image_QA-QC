import glob
import numpy as np
from src.checks.noise_check import compute_noise_estimate

clean_tiles = glob.glob("data/dataset/*.tif")
estimates = [compute_noise_estimate(p) for p in clean_tiles]

p90 = np.percentile(estimates, 90)
p95 = np.percentile(estimates, 95)
print(f"90th percentile: {p90:.2f}")
print(f"95th percentile: {p95:.2f}")
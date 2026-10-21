import rasterio
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

with rasterio.open("data/test/missing_data_2.tif") as src:
    r = src.read(1)
    g = src.read(2)
    b = src.read(3)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
bands = [("Red (band 1)", r, "red"), ("Green (band 2)", g, "green"), ("Blue (band 3)", b, "blue")]

for ax, (label, data, color) in zip(axes, bands):
    ax.hist(data.flatten(), bins=100, color=color)
    zero_count = np.sum(data == 0)
    ax.set_title(f"{label}\nzero count: {zero_count} ({zero_count/data.size:.1%})")

fig.tight_layout()
fig.savefig("debug_bands_separate.png", dpi=100)
print("Saved debug_bands_separate.png")
print(f"\nRed zero: {np.sum(r==0)} ({np.sum(r==0)/r.size:.1%})")
print(f"Green zero: {np.sum(g==0)} ({np.sum(g==0)/g.size:.1%})")
print(f"Blue zero: {np.sum(b==0)} ({np.sum(b==0)/b.size:.1%})")
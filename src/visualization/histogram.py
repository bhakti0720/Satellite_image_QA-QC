"""
histogram.py
Renders a per-band pixel value histogram for a tile, using Matplotlib.
Visual counterpart to statistics_check.py -- makes distribution shape,
clipping, and low-contrast issues visible at a glance rather than only
as numbers.
"""

import rasterio
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend -- required for saving
                        # figures to file without a display/GUI, which
                        # matters since this runs from scripts, not a
                        # notebook or interactive session.
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Union


BAND_COLORS = {1: "red", 2: "green", 3: "blue"}
BAND_LABELS = {1: "Red (B04)", 2: "Green (B03)", 3: "Blue (B02)"}


def save_histogram(filepath: str, output_path: Union[str, Path], bins: int = 100) -> Path:
    """
    Reads all three bands and plots an overlaid histogram, one color per
    band, on a single chart. Saves as PNG.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(filepath) as src:
        bands = {i: src.read(i) for i in range(1, src.count + 1)}

    fig, ax = plt.subplots(figsize=(6, 4))

    for band_idx, band_data in bands.items():
        color = BAND_COLORS.get(band_idx, "gray")
        label = BAND_LABELS.get(band_idx, f"Band {band_idx}")
        ax.hist(
            band_data.flatten(),
            bins=bins,
            color=color,
            alpha=0.5,
            label=label,
            histtype="stepfilled",
        )

    ax.set_xlabel("Pixel value (reflectance)")
    ax.set_ylabel("Pixel count")
    ax.set_title(f"Band value distribution — {Path(filepath).name}")
    ax.legend()
    fig.tight_layout()

    fig.savefig(output_path, dpi=100)
    plt.close(fig)  # important: releases the figure from memory

    return output_path
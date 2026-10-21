"""
anomaly_map.py
Renders a visual overlay showing the 8x8 grid of block means used by
anomaly_check.py, with the most anomalous block(s) highlighted. Visual
counterpart to check_spatial_anomaly's modified z-score (median + MAD)
outlier detection.
"""

import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path
from typing import Union

from src.visualization.image_preview import read_rgb_normalized
from src.checks.anomaly_check import compute_block_means


def save_anomaly_map(
    filepath: str,
    output_path: Union[str, Path],
    grid_size: int = 8,
    z_threshold: float = 3.5,
    max_size: int = 400,
) -> Path:
    """
    Saves a PNG showing the tile with a grid overlay -- anomalous blocks
    (those exceeding z_threshold, matching anomaly_check.py's logic
    exactly) are outlined in red, all other grid lines shown faintly.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rgb_array = read_rgb_normalized(filepath)  # (H, W, 3), uint8
    image = Image.fromarray(rgb_array, mode="RGB").convert("RGB")

    h, w = rgb_array.shape[:2]
    block_h, block_w = h // grid_size, w // grid_size

    # Recompute the same modified z-scores anomaly_check.py uses, so the
    # visual exactly matches what the actual check flagged -- not a
    # separate, potentially-inconsistent calculation.
    block_means = compute_block_means(filepath, grid_size)
    median = np.median(block_means)
    mad = np.median(np.abs(block_means - median))

    if mad < 1e-6:
        z_scores = np.zeros_like(block_means)
    else:
        z_scores = 0.6745 * np.abs(block_means - median) / mad

    draw = ImageDraw.Draw(image)

    for i in range(grid_size):
        for j in range(grid_size):
            y0, y1 = i * block_h, (i + 1) * block_h
            x0, x1 = j * block_w, (j + 1) * block_w

            is_anomalous = z_scores[i, j] > z_threshold
            color = (255, 0, 0) if is_anomalous else (255, 255, 255)
            width = 3 if is_anomalous else 1

            draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=color, width=width)

    if max(image.size) > max_size:
        image = image.resize((max_size, max_size), Image.LANCZOS)

    image.save(output_path, format="PNG")
    return output_path
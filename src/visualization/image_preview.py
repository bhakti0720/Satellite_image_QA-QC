"""
image_preview.py
Converts a uint16 GeoTIFF RGB tile into a standard 8-bit PNG thumbnail,
suitable for embedding in an HTML report. Reused as a building block by
other visualization modules (anomaly_map.py, nodata_map.py) that need to
show an image with an overlay on top.
"""

import rasterio
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Union


def read_rgb_normalized(filepath: str) -> np.ndarray:
    """
    Reads the RGB bands and normalizes each channel independently to 0-255
    using a 2nd-98th percentile stretch (same principle used throughout
    this project's check modules -- ignores outlier pixels so they don't
    compress the useful visual range).
    Returns an (H, W, 3) uint8 array, ready for PIL/image display.
    """
    with rasterio.open(filepath) as src:
        r = src.read(1).astype(np.float64)
        g = src.read(2).astype(np.float64)
        b = src.read(3).astype(np.float64)

    channels = []
    for band in (r, g, b):
        p2, p98 = np.percentile(band, [2, 98])
        # Guard against a degenerate (flat) band where p2 == p98, which
        # would otherwise cause a divide-by-zero.
        if p98 - p2 < 1e-6:
            stretched = np.zeros_like(band, dtype=np.uint8)
        else:
            stretched = np.clip((band - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)
        channels.append(stretched)

    # Stack into (H, W, 3) -- the standard image-array shape PIL expects,
    # as opposed to rasterio's native (bands, H, W) shape.
    rgb_image = np.dstack(channels)
    return rgb_image


def save_preview_png(filepath: str, output_path: Union[str, Path], max_size: int = 400) -> Path:
    """
    Reads a GeoTIFF tile, normalizes it, and saves it as a PNG thumbnail.
    max_size caps the longer dimension (keeps HTML reports lightweight --
    a full 512x512 PNG per tile across dozens of images would bloat the
    report file size unnecessarily).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rgb_array = read_rgb_normalized(filepath)
    image = Image.fromarray(rgb_array, mode="RGB")

    # Downscale if needed, preserving aspect ratio
    if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.LANCZOS)

    image.save(output_path, format="PNG")
    return output_path
"""
    Returns a 2D boolean mask, True where a pixel is zero in ANY of the
    three bands. Changed from "all three bands zero" (AND) to "any band
    zero" (OR) after empirical investigation on missing_data_2.tif showed
    the injected defect doesn't zero all bands uniformly -- Red/Green hit
    ~24.5% zero fraction while Blue only hit ~1%, with near-zero (0 or 1)
    values rather than consistent exact zeros. Using AND caught only 0.8%
    of the true dropout region; OR correctly captures the full ~24.9%
    extent, matching nodata_check.py's own zero-fraction findings.
    """


import rasterio
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Union

from src.visualization.image_preview import read_rgb_normalized


def compute_zero_mask(filepath: str) -> np.ndarray:
    """
    Returns a 2D boolean mask, True where a pixel is zero across ANY
    of the three bands (a "no data" pixel), matching the same definition
    used in nodata_check.py's zero-pixel logic.
    """
    with rasterio.open(filepath) as src:
        r = src.read(1)
        g = src.read(2)
        b = src.read(3)

    return (r == 0) | (g == 0) | (b == 0)


def save_nodata_map(
    filepath: str,
    output_path: Union[str, Path],
    max_size: int = 400,
    overlay_color: tuple = (255, 0, 0),
    overlay_alpha: float = 0.6,
) -> Path:
    """
    Saves a PNG showing the tile with zero-pixel regions highlighted in
    overlay_color (default: red), blended at overlay_alpha opacity so the
    underlying image content is still faintly visible beneath the highlight.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rgb_array = read_rgb_normalized(filepath)  # (H, W, 3), uint8
    zero_mask = compute_zero_mask(filepath)     # (H, W), bool

    # Blend: wherever zero_mask is True, mix the original pixel with the
    # overlay color at the given alpha. Elsewhere, keep the original pixel
    # unchanged. This is standard alpha-blending math done manually with
    # NumPy, since we're blending a solid color into specific pixels only.
    overlay = np.array(overlay_color, dtype=np.float64)
    result = rgb_array.astype(np.float64)

    result[zero_mask] = (
        result[zero_mask] * (1 - overlay_alpha) + overlay * overlay_alpha
    )
    result = np.clip(result, 0, 255).astype(np.uint8)

    image = Image.fromarray(result, mode="RGB")

    if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.LANCZOS)

    image.save(output_path, format="PNG")
    return output_path
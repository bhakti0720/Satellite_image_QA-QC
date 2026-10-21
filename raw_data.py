import rasterio
from rasterio.windows import Window
from rasterio.transform import Affine
import numpy as np
from pathlib import Path
import random

# --- settings ---
scenes = {
    # "scene1": r"D:\ISRO_projects\satellite-image-qa-qc\data\raw\Ahm_1\S2A_MSIL2A_20260627T054251_N0512_R005_T42QZL_20260627T103225.SAFE\GRANULE\L2A_T42QZL_A057517_20260627T055033\IMG_DATA\R10m",
    "scene2": r"D:\Satellite Data\Project_QA_QC_data\Ahm_2\S2C_MSIL2A_20260416T053641_N0512_R005_T42QZL_20260416T104257.SAFE\GRANULE\L2A_T42QZL_A008412_20260416T054353\IMG_DATA\R10m",
}

output_dir = Path("D:\ISRO_projects\satellite-image-qa-qc\data\dataset")
output_dir.mkdir(exist_ok=True)

tile_size = 512
tiles_needed_per_scene = 25
max_zero_fraction = 0.05
random.seed(42)


def find_band(folder, band_code):
    """Find a band file like *_B04_10m.jp2 in the given folder."""
    matches = list(Path(folder).glob(f"*_{band_code}_10m.jp2"))
    if not matches:
        raise FileNotFoundError(f"No {band_code} file found in {folder}")
    return matches[0]


def find_scl_band(r10m_folder):
    """
    SCL lives in the sibling R20m folder, not R10m. Derive that path from
    the R10m folder we already have, since both sit under the same
    scene's IMG_DATA directory.
    """
    r20m_folder = Path(r10m_folder).parent / "R20m"
    matches = list(r20m_folder.glob("*_SCL_20m.jp2"))
    if not matches:
        raise FileNotFoundError(f"No SCL file found in {r20m_folder}")
    return matches[0]


def load_and_upsample_scl(r10m_folder, target_height, target_width):
    """
    Reads the native 20m SCL band and upsamples it 2x via nearest-neighbor
    repeat to match the 10m RGB grid's exact pixel dimensions. Nearest-
    neighbor (not bilinear/cubic) is required here because SCL values are
    categorical class codes (e.g. 4=vegetation, 9=cloud) -- interpolating
    between them would produce meaningless in-between codes.
    """
    scl_path = find_scl_band(r10m_folder)
    with rasterio.open(scl_path) as src:
        scl = src.read(1)  # shape: (H/2, W/2) relative to RGB

    # np.repeat along each axis doubles resolution by duplicating each
    # pixel into a 2x2 block -- the standard nearest-neighbor upsample.
    scl_upsampled = np.repeat(np.repeat(scl, 2, axis=0), 2, axis=1)

    # Guard against off-by-one size mismatches (source dimensions don't
    # always divide/multiply perfectly) by cropping or padding to match
    # the RGB scene exactly.
    scl_upsampled = scl_upsampled[:target_height, :target_width]
    if scl_upsampled.shape != (target_height, target_width):
        padded = np.zeros((target_height, target_width), dtype=scl_upsampled.dtype)
        h, w = scl_upsampled.shape
        padded[:h, :w] = scl_upsampled
        scl_upsampled = padded

    return scl_upsampled


def build_rgb_stack(folder):
    """Read B04(Red), B03(Green), B02(Blue) and stack into one 3-band array."""
    red_path = find_band(folder, "B04")
    green_path = find_band(folder, "B03")
    blue_path = find_band(folder, "B02")

    with rasterio.open(red_path) as src:
        red = src.read(1)
        meta = src.meta.copy()
    with rasterio.open(green_path) as src:
        green = src.read(1)
    with rasterio.open(blue_path) as src:
        blue = src.read(1)

    rgb = np.stack([red, green, blue])  # (3, H, W)
    meta.update(count=3, dtype=rgb.dtype)
    return rgb, meta


def get_candidate_windows(width, height):
    candidates = []
    for row_off in range(0, height, tile_size):
        for col_off in range(0, width, tile_size):
            if row_off + tile_size <= height and col_off + tile_size <= width:
                candidates.append(Window(col_off, row_off, tile_size, tile_size))
    return candidates


def passes_nodata_filter(data):
    for band in data:
        zero_frac = np.sum(band == 0) / band.size
        if zero_frac > max_zero_fraction:
            return False
    return True


for scene_name, folder in scenes.items():
    folder = Path(folder)
    if not folder.exists():
        print(f"SKIP: {folder} not found")
        continue

    print(f"\nBuilding RGB stack for {scene_name}...")
    rgb, meta = build_rgb_stack(folder)
    height, width = rgb.shape[1], rgb.shape[2]

    # Save the full stacked scene once (optional, useful for reference/QGIS check)
    stacked_path = output_dir / f"{scene_name}_RGB_full.tif"
    with rasterio.open(stacked_path, "w", **meta) as dst:
        dst.write(rgb)
    print(f"  Saved full stack: {stacked_path.name} ({width}x{height})")

    # --- NEW: load + upsample SCL once per scene, same grid as RGB ---
    print(f"  Loading and upsampling SCL for {scene_name}...")
    scl_full = load_and_upsample_scl(folder, height, width)
    print(f"  SCL upsampled to {scl_full.shape[1]}x{scl_full.shape[0]}")

    candidates = get_candidate_windows(width, height)
    random.shuffle(candidates)

    kept = 0
    checked = 0
    for window in candidates:
        if kept >= tiles_needed_per_scene:
            break
        checked += 1

        row0, col0 = window.row_off, window.col_off
        tile_data = rgb[:, row0:row0 + tile_size, col0:col0 + tile_size]

        if not passes_nodata_filter(tile_data):
            continue

        base_transform = meta["transform"]
        tile_transform = base_transform * Affine.translation(col0, row0)

        out_meta = meta.copy()
        out_meta.update({
            "height": tile_size,
            "width": tile_size,
            "transform": tile_transform
        })

        out_name = f"{scene_name}_tile_r{row0}_c{col0}.tif"
        out_path = output_dir / out_name

        with rasterio.open(out_path, "w", **out_meta) as dst:
            dst.write(tile_data)

        # --- NEW: slice and save the matching SCL tile ---
        scl_tile = scl_full[row0:row0 + tile_size, col0:col0 + tile_size]

        scl_meta = out_meta.copy()
        scl_meta.update(count=1, dtype=scl_tile.dtype)

        scl_out_name = f"{scene_name}_tile_r{row0}_c{col0}_scl.tif"
        scl_out_path = output_dir / scl_out_name

        with rasterio.open(scl_out_path, "w", **scl_meta) as dst:
            dst.write(scl_tile, 1)

        kept += 1

    print(f"  {scene_name}: kept {kept}/{tiles_needed_per_scene} tiles "
          f"(checked {checked} of {len(candidates)} candidates)")

    if kept < tiles_needed_per_scene:
        print(f"  WARNING: not enough clean tiles. Lower tile_size or raise max_zero_fraction.")

print("\nDone. Check the 'tiled_dataset' folder.")
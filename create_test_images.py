import argparse
import json
from pathlib import Path
 
import numpy as np
import rasterio
from rasterio import CRS  # type: ignore
import cv2
 
 
# ---------------------------------------------------------------------------
# Individual defect generators
# Each takes (array, profile) from a SOURCE tile and returns a NEW
# (array, profile) pair. They never mutate the input in place.
# ---------------------------------------------------------------------------
 
def make_missing_data(array: np.ndarray, profile: dict) -> tuple[np.ndarray, dict]:
    """Blank out a large rectangular region with the NoData value."""
    arr = array.copy()
    profile = profile.copy()
 
    nodata_val = profile.get("nodata")
    if nodata_val is None:
        nodata_val = 0
        profile["nodata"] = nodata_val
 
    bands, height, width = arr.shape
    r0, r1 = height // 2, height          # bottom half
    c0, c1 = width // 2, width            # right half
    arr[:, r0:r1, c0:c1] = nodata_val
 
    return arr, profile
 
 
def make_noisy(array: np.ndarray, profile: dict, sigma: float = 25.0) -> tuple[np.ndarray, dict]:
    """Add Gaussian noise to every band, clipped to valid dtype range."""
    arr = array.astype(np.float32).copy()
    profile = profile.copy()
 
    noise = np.random.normal(loc=0.0, scale=sigma, size=arr.shape).astype(np.float32)
    arr += noise
 
    dtype = profile["dtype"]
    if np.issubdtype(np.dtype(dtype), np.integer):
        info = np.iinfo(dtype)
        arr = np.clip(arr, info.min, info.max)
    arr = arr.astype(dtype)
 
    return arr, profile
 
 
def make_blurred(array: np.ndarray, profile: dict, kernel_size: int = 15) -> tuple[np.ndarray, dict]:
    """Apply a strong Gaussian blur per band (simulates defocus/motion blur)."""
    arr = array.copy()
    profile = profile.copy()
 
    for b in range(arr.shape[0]):
        band = arr[b].astype(np.float32)
        blurred = cv2.GaussianBlur(band, (kernel_size, kernel_size), 0)
        arr[b] = blurred.astype(arr.dtype)
 
    return arr, profile
 
 
def make_black_line(array: np.ndarray, profile: dict, n_lines: int = 5) -> tuple[np.ndarray, dict]:
    """Zero out several full rows to simulate sensor striping/dropout."""
    arr = array.copy()
    profile = profile.copy()
 
    bands, height, width = arr.shape
    rng = np.random.default_rng(42)
    rows = rng.choice(height, size=min(n_lines, height), replace=False)
    arr[:, rows, :] = 0
 
    return arr, profile
 
 
def make_wrong_crs(array: np.ndarray, profile: dict) -> tuple[np.ndarray, dict]:
    """Keep pixel data identical but assign an incorrect/mismatched CRS."""
    arr = array.copy()
    profile = profile.copy()
    profile["crs"] = CRS.from_epsg(4326)  # wrong: your tiles are in UTM, not geographic
    return arr, profile
 
 
DEFECTS = {
    "missing_data_2.tif": make_missing_data,
    "noisy_2.tif": make_noisy,
    "blurred_2.tif": make_blurred,
    "black_line_2.tif": make_black_line,
    "wrong_crs_2.tif": make_wrong_crs,
}
 
 
# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------
 
def read_source(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as src:
        array = src.read()
        profile = src.profile.copy()
    return array, profile
 
 
def write_output(path: Path, array: np.ndarray, profile: dict) -> None:
    profile = profile.copy()
    profile.update(count=array.shape[0], height=array.shape[1], width=array.shape[2])
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array)
 
 
# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
 
def main(source_paths: list[Path], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = {}
 
    # Use the first source tile as the baseline for all defects.
    # (Pass multiple --source tiles if you want to spread defects across scenes.)
    base_source = source_paths[0]
    array, profile = read_source(base_source)
    print(f"Using baseline tile: {base_source.name}  shape={array.shape}  dtype={profile['dtype']}")
 
    for filename, defect_fn in DEFECTS.items():
        out_array, out_profile = defect_fn(array, profile)
        out_path = outdir / filename
        write_output(out_path, out_array, out_profile)
        manifest[str(out_path)] = {
            "defect": filename.replace(".tif", ""),
            "source": str(base_source),
        }
        print(f"  [defect] {filename} <- {base_source.name}")
 
    manifest_path = outdir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest written to {manifest_path}")
    print(f"Defective test images written to {outdir}")
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate defective test images from clean tiles in data/dataset/.")
    parser.add_argument(
        "--source",
        nargs="+",
        required=True,
        help="Path(s) to clean tile GeoTIFF(s) from data/dataset/, e.g. data/dataset/scene2_tile_r8192_c0.tif",
    )
    parser.add_argument(
        "--outdir",
        default="data/test",
        help="Output directory for defective images (default: data/test, per project blueprint)",
    )
    args = parser.parse_args()
 
    source_paths = [Path(p) for p in args.source]
    for p in source_paths:
        if not p.exists():
            raise FileNotFoundError(f"Source tile not found: {p}")
 
    main(source_paths, Path(args.outdir))
 
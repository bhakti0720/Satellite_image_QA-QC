# Detailed Check Module Documentation

This document explains every check module in `src/checks/`, function by function, in plain language. For each module: **what it's for, how the code works, what each threshold means, and how to debug it if something breaks.**

---

## Shared foundation: `src/checks/base.py`

Every check module builds on three shared pieces:

```python
class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class CheckResult:
    check_name: str
    passed: bool
    severity: Severity
    message: str

def pass_result(check_name, message="OK") -> CheckResult: ...
def fail_result(check_name, severity, message) -> CheckResult: ...
```

**Why this exists**: without a shared result shape, every check module would invent its own way of saying "pass/fail," and the scoring engine would need custom logic per module. `CheckResult` is the universal currency every check speaks — `qa_engine.py` and `scoring.py` only ever need to understand this one shape, regardless of which of the 10 categories produced it.

**Severity is an Enum, not a plain string** — this prevents typos (`Severity.CRITICAL` autocompletes and errors if misspelled; a string `"critcal"` would silently fail to match anywhere and break scoring without any error).

---

## 1. `file_checks.py` — File Integrity

**Purpose**: Answers "can we even trust this file exists and opened correctly?" This is the first line of defense — if these checks fail, nothing else downstream can be trusted either.

### Functions

**`check_file_opens(meta)`** — reads `meta.is_valid` (already computed by `RasterInspector`). If `False`, returns `CRITICAL` failure. This is the single most important check in the whole project — if the file didn't open, literally nothing else about it can be verified.

**`check_file_size(meta, min_bytes=1024)`** — flags files smaller than 1KB as likely truncated/corrupted downloads. `CRITICAL` severity, because a file this small can't possibly be a real 512×512×3-band image.

**`check_driver(meta, expected_driver="GTiff")`** — checks that `meta.driver` matches `"GTiff"`. `WARNING` severity (not critical) because a non-GTiff-but-still-valid raster can often still be read and used, just isn't in the expected format.
> **Known issue**: this check currently fails on 100% of this project's dataset, because `raw_data.py` copies metadata (including the `driver` field) directly from the source `.jp2` files without overriding it to `GTiff`. See the Challenges document for the full story.

**`check_band_count(meta, expected_bands=3)`** — confirms exactly 3 bands (R/G/B). `CRITICAL`, because every pixel-based check downstream assumes band 1=Red, band 2=Green, band 3=Blue — a wrong count breaks everything else.

**`run_file_checks(meta)`** — the entry point. Runs `check_file_opens` first; if it fails, returns immediately (skips the other three, since they'd all crash trying to read `None` values from an unopened file).

### How to debug this module
- If `check_file_opens` fails unexpectedly on a file you know is fine: check the file path is correct, check the file isn't locked by another program, try opening it manually with `rasterio.open(path)` in a Python shell to see the raw error.
- If `check_driver` fails on every file: this is the known driver bug — check `raw_data.py`'s `meta.update()` call for a missing `driver="GTiff"`.

---

## 2. `metadata_checks.py` — Dimensions, Dtype, Resolution

**Purpose**: Confirms the file's basic structural properties match what the project expects, *given that it already opened successfully*.

### Functions

**`check_dimensions(meta, expected_size=512)`** — confirms width and height are both 512. `CRITICAL`, because the entire pipeline (tiling logic, anomaly grid math, visualizations) assumes this exact size.

**`check_dtype(meta, expected_dtype="uint16")`** — confirms pixel data type. `WARNING`, because a dtype mismatch is real but often still workable (data can frequently still be converted/processed).

**`check_pixel_resolution(meta, expected_res=10.0, tolerance=0.01)`** — confirms ~10 meters per pixel. Uses `abs(actual - expected) <= tolerance` instead of `==` because floating-point numbers from geospatial transforms are almost never perfectly exact (you might get `9.9999999` instead of a clean `10.0` due to floating-point precision) — this is the standard "close enough" comparison pattern for any float comparison.

**`check_square_pixels(meta, tolerance=0.01)`** — confirms pixel width equals pixel height. Non-square pixels are a signature of a bad resampling/reprojection step somewhere upstream.

**`run_metadata_checks(meta)`** — assumes the caller already confirmed `meta.is_valid` (via `file_checks.py`); if somehow called on an invalid file anyway, it returns a single critical failure rather than crashing.

### How to debug this module
- `check_dimensions` failing on tiles that *should* be 512×512: check the tiling logic in `raw_data.py` for an off-by-one in the windowing loop.
- `check_pixel_resolution` failing unexpectedly: print `meta.transform` directly and check `transform.a` (pixel width) and `transform.e` (pixel height, usually negative) manually.

---

## 3. `geospatial_checks.py` — CRS and Transform Validity

**Purpose**: Confirms the file's location-on-Earth metadata is correct and internally consistent.

### Key concept: the affine transform
A GeoTIFF's transform is 6 numbers `(a, b, c, d, e, f)` that convert pixel row/column into real-world coordinates:
```
easting  = a * col + b * row + c
northing = d * col + e * row + f
```
- `a` = pixel width (meters per pixel, moving right)
- `e` = pixel height (usually negative, since row increases downward but northing increases upward)
- `b`, `d` = rotation/shear terms — should be exactly 0 for a normal north-up image
- `c`, `f` = real-world coordinate of the top-left pixel

### Functions

**`check_crs_present(meta)`** — confirms *any* CRS is defined. `CRITICAL` if missing entirely — usually means metadata got stripped somewhere.

**`check_crs_matches_expected(meta, expected_crs="EPSG:32642")`** — confirms it's specifically UTM Zone 42N (the project's chosen CRS for Ahmedabad). `CRITICAL` if wrong — this is a different failure signature than "no CRS at all" (usually means a reprojection step went wrong or got skipped).

**`check_transform_valid(meta)`** — confirms the transform isn't degenerate (both `a` and `e` being zero would mean no real pixel-to-coordinate mapping exists at all).

**`check_no_rotation(meta, tolerance=1e-6)`** — confirms `b` and `d` are essentially zero (no unexpected rotation/shear). Uses a much tighter tolerance (`1e-6`) than the pixel-size checks (`0.01`), because rotation terms should be *exactly* zero in well-formed north-up data — even tiny non-zero values are suspicious here, unlike pixel size where small floating-point noise is normal.

**`check_bounds_sane(meta)`** — confirms the bounding box has positive width and height (catches a truly degenerate case like `left > right`).

### How to debug this module
- `check_crs_matches_expected` failing on a file you believe is correct: run `rasterio.open(path).crs` directly and compare to `EPSG:32642` string exactly — CRS objects can sometimes represent the "same" projection with slightly different string formats.
- This check module has a hardcoded expected CRS (`EPSG:32642`) — if extending to a new region, this is one of the first places to update.

---

## 4. `nodata_check.py` — Missing Data Analysis

**Purpose**: Detects pixels that are "missing" — usually shown as zero values, since this dataset doesn't use a formal NoData flag.

### Key finding this module is built around
This project's Sentinel-2 data has **no formal NoData value set** in its metadata — missing/edge pixels just show up as `0`. So this check can't rely on `meta.nodata_value`; it has to actually read pixel data and count zeros.

### Functions

**`compute_zero_fraction_per_band(filepath)`** — reads each band, counts how many pixels equal exactly `0`, divides by total pixel count. Returns a list, one fraction per band.

**`check_nodata_declared(meta)`** — purely informational (always passes). Just documents whether a formal NoData value exists, since we already know it typically doesn't for this dataset.

**`check_zero_pixel_fraction(meta, max_zero_fraction=0.05)`** — flags a tile if *any* band exceeds 5% zero pixels. `CRITICAL`. This threshold mirrors the exact same filter used during dataset creation in `raw_data.py`, just applied again at QA time.

**`check_nodata_spatial_pattern(meta, block_threshold=0.15)`** — distinguishes *scattered* zero pixels (often harmless sensor noise) from a *contiguous block* of zeros (a real structural defect). Splits the image into a 4×4 grid, checks if any single grid cell is mostly zero. `WARNING` (it's a heuristic, not a definitive detection).

### Why the spatial pattern check exists (the reasoning, explained)
Imagine two tiles both with 5% zero pixels total. In Tile A, those zeros are scattered randomly across the whole image (probably just sensor noise). In Tile B, all the zeros are clustered in one corner (probably a real dropout region). A flat percentage check treats both identically — it can't tell the difference. The 4×4 grid check catches this: a contiguous dropout concentrates its zeros into one or two grid cells, which will spike well above the average, even if the total image-wide percentage stays low.

### How to debug this module
- If it's not catching a defect you expect it to: check the actual zero-fraction number directly with `compute_zero_fraction_per_band()` before assuming the threshold is wrong.
- Overlaps intentionally with `saturation_check.py`'s zero-pixel logic — this is by design (see that module's notes), not a bug.

---

## 5. `statistics_check.py` — Pixel Distribution Health

**Purpose**: Checks the overall statistical health of each band's pixel values — catches flat/constant bands, values wildly outside the expected range, and low-contrast images.

### Functions

**`compute_band_statistics(filepath)`** — reads each band, casts to `float64` (important — `uint16` arithmetic can silently misbehave for std/mean calculations due to overflow/casting issues), computes min/max/mean/std/2nd percentile/98th percentile. Returns a `BandStatistics` dataclass per band.

**`check_constant_bands(meta, std_threshold=1.0)`** — flags a band with almost zero standard deviation (essentially a flat, single-value band). `CRITICAL` — real image data always has *some* natural variation; a truly flat band means corrupted or blank data.

**`check_value_range(meta, min_valid=0, max_valid=10000)`** — flags values far outside the expected Sentinel-2 L2A reflectance range (roughly 0–10,000, representing 0–100%+ reflectance). `WARNING` — a moderately out-of-range value is suspicious but doesn't necessarily make the image unusable.

**`check_low_contrast(meta, min_dynamic_range=100.0)`** — checks the spread between the 2nd and 98th percentile. A narrow spread means low contrast (possibly blur, haze, fog) even if `std` looks normal (since `std` can be misled by a single outlier pixel keeping it artificially high).

### Why percentiles instead of raw min/max?
A single stray sensor-noise pixel can blow out the raw min or max, making the image look like it has huge dynamic range when it actually doesn't. The 2nd–98th percentile ignores the extreme 2% tails on each end and measures the spread of the *bulk* of real data — a more robust signal.

### How to debug this module
- `check_constant_bands` false-triggering: verify with `compute_band_statistics()` directly — check if `std` really is near-zero, or if there's a units/casting issue.
- Note: blur does **not** reliably trigger `check_low_contrast` — blur removes fine detail but often keeps the overall value range wide (confirmed empirically in this project). Blur needs `blur_check.py`, not this module.

---

## 6. `saturation_check.py` — Over/Under-Exposure Detection

**Purpose**: Detects pixels clipped at the extremes — pure black (dropout) or pinned at a high plateau (overexposed).

### Functions

**`compute_saturation_fractions(filepath, high_threshold=10000)`** — per band, computes the fraction of pixels at exactly 0 ("low") and the fraction at or above `high_threshold` ("high").

**`check_low_saturation(meta, max_low_fraction=0.05)`** — flags bands with too many zero pixels. `WARNING`. Note: this measures the *same underlying pixels* as `nodata_check.py`'s zero-fraction check, but frames it differently — NoData check treats it as "missing data" (critical), this treats it as an "exposure" issue (warning). Both are kept because they serve different reporting purposes, not because of a bug.

**`check_high_saturation(meta, high_threshold=10000, max_high_fraction=0.02)`** — flags bands with too many pixels at/above the reflectance ceiling (overexposure, e.g. sun glint, bright rooftops). More lenient threshold (2%) than the low end, since bright surfaces are a normal part of real scenes.

**`check_saturation_by_line(meta, line_fraction_threshold=0.4)`** — detects a row or column with a high concentration of zero pixels, the signature of a sensor dropout line/strip.

### Important calibration story (interview-worthy)
This threshold was originally set to `0.8` (expecting a full-width dropout line), but empirical testing against the real `black_line` defect showed the injected lines were only **partial-width** (~50–58% of the row), not full-width. The check initially missed the defect entirely. After debugging with a dedicated script that printed row/column zero-fractions directly, the threshold was corrected to `0.4` — comfortably below the observed 50-58% range, comfortably above the 0% seen on clean tiles.

### Key NumPy pattern used here
```python
row_fractions = zero_mask.mean(axis=1)   # fraction of zeros in each row
col_fractions = zero_mask.mean(axis=0)   # fraction of zeros in each column
```
`.mean(axis=1)` collapses each row into one number (its own zero-fraction); `.mean(axis=0)` does the same per column. This is a much more targeted technique than a coarse grid check for detecting thin, full-length lines.

### How to debug this module
- If a known line defect isn't being caught: run a debug script printing the actual max row/column zero-fraction directly, compare against the threshold, adjust based on real numbers (don't guess).

---

## 7. `blur_check.py` — Sharpness Detection

**Purpose**: Detects blurred images using Laplacian variance, a standard, widely-used image-sharpness metric.

### The core concept
A sharp image has lots of high-frequency detail (edges, fine texture). A blurred image smooths that out. The **Laplacian operator** is an edge-detection filter that measures how much each pixel differs from its neighbors. Apply it to an image, then take the **variance** of the result:
- Sharp image → strong edges → high variance
- Blurred image → weak/no edges → low variance

### Functions

**`compute_laplacian_variance(filepath)`**:
1. Reads R/G/B bands, converts to grayscale using the standard luminance formula: `0.299*R + 0.587*G + 0.114*B` (these weights reflect human eye sensitivity — most sensitive to green, least to blue)
2. Normalizes to 8-bit (0-255) using a 2nd-98th percentile stretch (same principle as `statistics_check.py` — ignores outlier pixels so they don't compress the useful range)
3. Applies `cv2.Laplacian(image, cv2.CV_64F)` — the `CV_64F` output type matters because Laplacian output can be negative (edges are both "rising" and "falling"), and an unsigned 8-bit type can't hold negative numbers
4. Returns the variance of that filtered image

**`check_blur(meta, min_variance=100.0)`** — flags images below the threshold. `WARNING`.

### Why normalize to 8-bit first?
Without normalization, raw `uint16` variance would scale with whatever raw reflectance range each tile happens to have — a tile with naturally higher reflectance values would show artificially higher Laplacian variance without actually being sharper. Normalizing puts every tile on the same comparable 0–255 scale first.

### Calibration result (empirically confirmed)
Clean tile: variance ≈ 1109.8. Blurred defect tile: variance ≈ 19.8. A 50x+ separation — one of the cleanest, most reliable checks in the whole project, with high confidence in the threshold.

### How to debug this module
- If flagging clean images as blurry: check if the tile is genuinely low-texture content (water, uniform field) — run the calibration script across your whole clean dataset to see the natural variance range before assuming the threshold is wrong.

---

## 8. `noise_check.py` — Sensor Noise Detection

**Purpose**: Detects random, grainy pixel-to-pixel variation that isn't real image content — sensor noise.

### The concept, and why it's different from blur
Blur *removes* high-frequency detail. Noise *adds* random high-frequency variation. Confusingly, both can affect naive edge-detection metrics similarly, so blur-detection techniques can't be reused directly for noise.

### The technique used: Immerkær (1996) fast noise estimation
```python
_NOISE_KERNEL = np.array([
    [1, -2, 1],
    [-2, 4, -2],
    [1, -2, 1]
])
```
This kernel is mathematically constructed so that smooth gradients and most real edges convolve to near-zero, while random per-pixel noise does not cancel out. The formula:
```
sigma ≈ sqrt(pi/2) / (6 * (W-2) * (H-2)) * sum(|convolved_image|)
```

### Why this replaced an earlier median-filter approach
**Original approach**: apply a median filter (smooths noise but preserves edges better than mean blur), measure the standard deviation of the difference between original and filtered image.

**Why it failed**: tested against real data, this approach was dominated by genuine scene texture (urban areas naturally have more local pixel variation than farmland), not actual injected noise. A calibration run across 52 clean tiles showed noise estimates ranging from 1.58 to 21.66 — and the known noisy defect tiles (8.51–10.97) fell entirely *inside* that clean range. No threshold could separate them. This was a real, documented failure, not a minor tuning issue.

**Why Immerkær's method is better**: it's specifically designed to cancel out real image structure (both smooth areas and edges), leaving mostly just noise — much more targeted than "smooth and measure the difference."

### Functions

**`compute_noise_estimate(filepath)`** — grayscale conversion + percentile stretch (same pattern as blur_check), convolve with the noise kernel, apply the Immerkær formula.

**`check_noise(meta, max_noise_sigma=4.2)`** — flags images above the threshold. `WARNING`.

### Known limitation (be upfront about this in an interview)
Even after switching to the better technique, only **one** paired clean/noisy sample was available for calibration (source tile noise: 3.81 → noisy version: 4.45, a real but modest +0.63 increase). A percentile-based threshold approach was tested and rejected (the 90th percentile of clean tiles, 6.03, would have let the known noisy defect pass entirely). The final threshold (4.2) was chosen specifically to catch the one known sample, at the cost of likely flagging some naturally high-texture clean tiles as false positives — an explicit, documented tradeoff, not a silent gap.

### How to debug this module
- If seeing lots of false positives: this is expected given the documented limitation above — the fix would be generating more noisy calibration samples, not just adjusting the number blindly.

---

## 9. `blackline_check.py` — Sensor Striping Detection

**Purpose**: Detects rows/columns that are anomalously *uniform* compared to their neighbors — the signature of sensor calibration drift/striping, as distinct from zero-value dropout (which belongs to `saturation_check.py`).

### Why this is a separate check from `saturation_check.py`'s line detector
A "black line" in real satellite data isn't always a zero-value dropout — sometimes a detector reads a constant, uniform value across a whole row (not necessarily zero) due to calibration drift. `saturation_check.py`'s check only catches exact-zero lines; this check catches the more general "unusually flat compared to its neighbors" pattern.

### Functions

**`compute_row_col_uniformity(filepath)`** — computes the standard deviation *within* each row and *within* each column of band 1. A normal row has real spatial variation; a striped row is anomalously flat.

**`check_striping(meta, low_std_ratio=0.15)`** — flags a row/column whose internal std is less than 15% of the *median* row/column std. Uses the image's own median as the reference point (not a fixed global number), because "normal" internal variation differs hugely by scene content — this makes the check self-calibrating per image.

### Empirical finding
When tested against the `black_line` defect (which is actually a zero-dropout, not true constant-value striping), this check **also** fired — because a row that's 50%+ zero has reduced internal variance as a side effect, even without being a "pure" striping artifact. This is a good outcome (two independent checks converging on the same real defect from different statistical angles), but it also means this check has never been validated against a *dedicated* striping defect — that remains a known, documented gap.

### How to debug this module
- If you build a dedicated striping defect later (constant, non-zero value across a row), test against it directly and re-calibrate `low_std_ratio` based on real numbers, same pattern as every other threshold in this project.

---

## 10. `cloud_check.py` — Cloud/Scene Analysis

**Purpose**: Uses Sentinel-2's SCL (Scene Classification Layer) band to detect excessive cloud or shadow coverage.

### Background: what is SCL, and the resolution mismatch problem
SCL classifies every pixel into a category (vegetation, water, cloud, shadow, no-data, etc.) using codes 0–11. It ships at 20m resolution, while this project's RGB bands are 10m resolution — meaning one SCL pixel covers 4x the ground area of one RGB pixel. To use SCL alongside RGB tiles, it had to be **upsampled 2x using nearest-neighbor** repetition (`np.repeat` on both axes) — nearest-neighbor specifically because SCL values are categorical class codes; any smoothing/interpolation method would create meaningless in-between codes.

This required going back into `raw_data.py` (the original Day 1 tiling script) to add SCL extraction and save a companion `_scl.tif` file alongside each RGB tile.

### SCL class code reference
| Code | Meaning |
|---|---|
| 0 | No data |
| 1 | Saturated/defective |
| 2 | Dark area pixels |
| 3 | Cloud shadow |
| 4 | Vegetation |
| 5 | Bare soils |
| 6 | Water |
| 7–9 | Cloud (low/medium/high probability) |
| 10 | Cirrus |
| 11 | Snow/ice |

### Functions

**`get_scl_path(rgb_filepath)`** — derives the companion SCL filename by string substitution (`tile.tif` → `tile_scl.tif`).

**`compute_scl_class_fractions(rgb_filepath)`** — reads the SCL companion file, computes the fraction of pixels in each relevant class grouping (cloud, shadow, no-data, defective) using `np.isin()` — a NumPy function that checks membership against a *set* of values (e.g., "is this pixel any of {7, 8, 9, 10}"), as opposed to `==` which only checks one value.

**`check_scl_available(meta)`** — a defensive check confirming the companion file actually exists before trying to read it. If missing (common for tiles created before the SCL pipeline was added), gracefully reports this instead of crashing.

**`check_cloud_coverage(meta, max_cloud_fraction=0.20)`** — flags tiles with more than 20% cloud coverage. `WARNING`.

**`check_shadow_coverage(meta, max_shadow_fraction=0.15)`** — same idea for shadow. `WARNING`.

**`check_scl_nodata_defective(meta, max_bad_fraction=0.05)`** — flags tiles where SCL itself reports significant no-data/defective classification. `CRITICAL` — this is an independent cross-check against `nodata_check.py`'s own zero-pixel logic, using ESA's own classification algorithm as a second, different signal.

### How to debug this module
- If `scl_available` always fails: check whether that specific tile's scene was regenerated with the updated `raw_data.py` (only `scene2` tiles have SCL companions in this project — `scene1` predates the pipeline update).

---

## 11. `anomaly_check.py` — Spatial Anomaly Detection

**Purpose**: Detects localized statistical outlier regions anywhere in the image — not just zero-pixel dropout (that's `nodata_check.py`'s job), but any unusual patch (bright spot, texture anomaly, artifact) confined to one area.

### The technique
1. Split the image into an 8×8 grid of blocks
2. Compute each block's mean pixel value
3. Compare each block's mean against the overall distribution using a **modified z-score**

### Why median + MAD instead of mean + standard deviation
Originally built using plain mean + std (a standard z-score). This **failed badly** when tested against the `missing_data` defect — because that defect covers 25% of the grid (16 out of 64 blocks), which is large enough to drag the mean and inflate the std of the *whole image*, making the actual zero-blocks look statistically "normal" relative to a now-contaminated baseline. Confirmed with real numbers: overall std ballooned from 466.5 (clean) to 1051.9 (defective) — more than double — because the anomaly itself corrupted its own measuring stick.

The fix: **median** and **MAD (median absolute deviation)** are far more resistant to this, because median is a positional measure (the middle value) rather than a magnitude-sensitive average — a large cluster of extreme values doesn't drag it around nearly as much.
```python
median = np.median(block_means)
mad = np.median(np.abs(block_means - median))
modified_z_scores = 0.6745 * np.abs(block_means - median) / mad
```
The `0.6745` constant is a standard scale factor from robust statistics that makes MAD comparable in scale to a normal distribution's standard deviation.

### Known, documented limitation (important for interviews)
Even after the median/MAD fix, this check still degrades when an anomaly covers a *large* fraction of the grid. Confirmed empirically: the real dropout defect scored a modified z-score of only 2.42, while a genuinely clean tile scored 3.27 (uncomfortably close to the 3.5 threshold, and actually *higher* than the real defect). This proves that robust statistics tolerate contamination well only up to a point — at ~25% contamination, even median/MAD starts to break down. A full batch run across the whole dataset confirmed this generalizes badly: `scene1` tiles (with more naturally varied terrain) triggered very high false-positive z-scores (10–30), while `scene2` tiles stayed low.

**Honest conclusion documented in code**: this check is best suited to *small, localized* anomalies (a few blocks, not a quarter of the grid). Large contiguous dropouts are better and more reliably caught by `nodata_check.py`'s dedicated spatial pattern check.

### Functions

**`compute_block_means(filepath, grid_size=8)`** — splits band 1 into a grid, returns a 2D array of block means.

**`check_spatial_anomaly(meta, grid_size=8, z_threshold=3.5)`** — computes modified z-scores, flags if any block exceeds the threshold. `WARNING`.

### How to debug this module
- If getting lots of false positives on clean tiles with varied real content: this is the documented limitation, not a new bug. Would require either a fundamentally different technique (e.g., ignoring the largest contiguous outlier cluster before computing the baseline) or restricting this check's scope to genuinely small anomalies only.

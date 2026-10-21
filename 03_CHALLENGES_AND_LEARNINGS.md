# Challenges Faced & How They Were Overcome

This document lists every real problem hit during this project, how it was diagnosed, and what was actually done to fix it (or why it was consciously left as a documented limitation). Written so you can explain each one confidently in an interview or recall the debugging process if something breaks again later.

Each entry follows the same structure: **What happened → How we found out → What we did → What we learned.**

---

## Challenge 1: Stale `__pycache__` causing "function not found" errors

**What happened**: After editing `nodata_check.py` to add a new function `run_nodata_checks`, importing it failed with `ImportError: cannot import name 'run_nodata_checks'` — even though the function was clearly present in the file.

**How we found out**: Ran `python -c "import src.checks.nodata_check as m; print(m.__file__); print(dir(m))"` to confirm exactly which file Python was loading and what it actually contained. This proved the *correct* file existed with the *correct* function.

**What we did**: Cleared the `__pycache__` folder (`Remove-Item -Recurse -Force src\checks\__pycache__`) and re-ran. Python caches compiled bytecode (`.pyc` files) and can sometimes load a stale cached version instead of re-reading updated source — clearing the cache forces a fresh read.

**What we learned**: When Python behaves like it's running "old code" despite a confirmed correct save, clear `__pycache__` before assuming anything more complicated is wrong. This became a standard first debugging step for the rest of the project.

---

## Challenge 2: A near-identical bug that looked the same but wasn't

**What happened**: Right after fixing the cache issue above, a very similar-looking error appeared again: `ImportError: cannot import name 'run_nodata_check'` (note: no trailing "s").

**How we found out**: Read the exact error message character by character instead of assuming it was the same cache problem. The function name in the error was singular (`run_nodata_check`), while the real function was plural (`run_nodata_checks`).

**What we did**: Fixed a simple typo in the test script's import line.

**What we learned**: Two errors can look almost identical on the surface but have completely different causes. Always read error messages precisely rather than pattern-matching to "the last bug I just fixed" — this is a core debugging discipline.

---

## Challenge 3: Wrong assumption about a defect's shape (saturation-by-line threshold)

**What happened**: `check_saturation_by_line` (in `saturation_check.py`) was built assuming a "black line" defect would be a **full-width** dropout line (threshold set to 80% of a row/column being zero). When tested against the real defect file, it didn't trigger at all.

**How we found out**: Instead of guessing at a new threshold, wrote a debug script to directly print the actual max row/column zero-fraction and the top 5 rows/columns by zero-fraction. This revealed the real defect was **partial-width** — around 50–58% of a row's pixels, not close to 100%, and spread across *multiple* rows (5 different rows, not just one).

**What we did**: Lowered the threshold from 0.8 to 0.4 — comfortably below the observed 50-58% range, comfortably above the 0% seen on clean tiles. Documented the reasoning directly in the code comment so future readers understand *why* 0.4 was chosen, not just that it was.

**What we learned**: Never guess a threshold based on an assumption about what a defect "should" look like — always verify the actual defect's characteristics with real data first, then set thresholds based on evidence.

---

## Challenge 4: A check technique that fundamentally didn't work (noise detection)

**What happened**: The first noise-detection approach (median filter residual: smooth the image, measure the standard deviation of the difference from the original) produced numbers that didn't separate clean from noisy tiles at all. Worse — running it across the full 52-tile clean dataset showed a natural range of 1.58 to 21.66, and the known noisy defects (8.51–10.97) fell entirely *inside* that range. No threshold, however tuned, could have worked.

**How we found out**: 
1. First noticed the single test pair (clean vs noisy) had a very small, ambiguous gap.
2. Ran a calibration script across the *entire* clean dataset (not just one sample) to check whether one tile was just a natural outlier — this revealed the clean tiles themselves varied hugely (busy urban tiles naturally have more local pixel variation than flat farmland).
3. Concluded the technique itself was being dominated by real scene texture, not actual injected noise.

**What we did**: Switched to the **Immerkær (1996) fast noise estimation method** — a kernel-based technique from established image-processing literature, specifically designed so that smooth gradients and real edges cancel out to near-zero in the convolution, leaving mostly genuine noise behind. This is a fundamentally different, more targeted approach than "smooth and compare."

**What we learned**: When a metric can't separate two populations no matter how you tune the threshold, the problem usually isn't the number — it's the underlying technique. Sometimes you need to look for a better-established method rather than keep tweaking a flawed one. Also learned the importance of testing against the *whole* population, not just one pair, before trusting any threshold.

**Residual limitation (still honest about this)**: Even after switching techniques, only one true paired clean/noisy sample existed for calibration. The final threshold was deliberately set to catch that one known sample (accepting some false positives on naturally busy clean tiles) rather than pretending high confidence that doesn't exist. Documented explicitly in code and README rather than hidden.

---

## Challenge 5: A visualization silently misrepresenting data it was supposed to show (NoData map)

**What happened**: The NoData map (highlighting zero-pixel regions in red) showed a large defect region as almost entirely **black with no red**, only scattered red speckles at the edges — even though `nodata_check.py` had already correctly reported ~24.7% zero pixels in that region.

**How we found out**: Investigated why the visual didn't match the numeric finding. The map's `compute_zero_mask()` function required **all three bands** (R, G, B) to be exactly zero simultaneously (`r==0 & g==0 & b==0`) before highlighting a pixel. A debug script checking each band separately revealed: Red was 24.4% zero, Green was 24.7% zero, but **Blue was only 1.1% zero** (and even those weren't always exactly 0 — sometimes 1). This meant the strict "all three bands zero" condition only caught 0.8% of pixels — the rare overlap — while the true dropout region spanned 24.9% of the image.

**What we did**: Changed the mask logic from AND (`&`, all three bands must be zero) to OR (`|`, any single band being zero counts), which correctly captured the full 24.9% dropout extent, matching the numeric check almost exactly.

**What we learned**: A synthetic defect generator doesn't necessarily zero out every band uniformly or consistently — real-world (or realistically-simulated) defects can be messier than a clean textbook assumption. Also: a visualization bug is arguably more dangerous than a check bug, because it can visually mislead a human reviewer into underestimating a real problem even when the underlying detection logic was already correct.

---

## Challenge 6: A statistical technique breaking down when the anomaly is too large (spatial anomaly detection)

**What happened**: `anomaly_check.py`'s original design used a standard z-score (mean + standard deviation) across an 8×8 grid of block means to detect localized anomalies. When tested, it completely failed to catch the known `missing_data` defect — even though that defect covers a full 4×4 sub-block of contiguous zero-value blocks (25% of the grid).

**How we found out**: Printed the raw 8×8 grid of block means directly for both a clean tile and the defective tile. This revealed the actual numbers: the defective tile's overall standard deviation had inflated from 466.5 (clean) to 1051.9 — more than double — because the large cluster of zero-blocks was itself distorting the very baseline being used to judge "normal."

**What we did**: Switched to **median + MAD (median absolute deviation)** instead of mean + standard deviation — a well-established "robust statistics" technique specifically designed to resist being dragged around by large clusters of outliers, since median is a positional measure rather than a magnitude-sensitive average.

**What we learned (and this is the deeper lesson)**: Even after switching to a more robust technique, it *still* wasn't good enough — testing showed the real defect scored a modified z-score of only 2.42, while a genuinely clean tile scored 3.27 (higher than the actual defect, and uncomfortably close to the 3.5 threshold). Robust statistics techniques generally tolerate outlier contamination well only up to a point (often cited around 25-50%) — and this defect's 25% contamination sat right at the edge of where even a robust technique starts to break down. A full batch run across the whole dataset confirmed this generalizes badly across different scene content.

**Final decision**: Rather than force-fit a threshold that doesn't reflect genuine statistical separation (which would just create false confidence), this was documented honestly as a known limitation: this check is well-suited to *small*, localized anomalies, but large contiguous defects are more reliably caught by the dedicated NoData spatial pattern check instead. This is a real, defensible engineering decision — sometimes the right answer is "this technique has a scope, and we should be honest about where that scope ends," rather than pretending false precision.

---

## Challenge 7: A metadata bug that silently affected every single file in the project (driver bug)

**What happened**: Every generated `.tif` file, when inspected, reported its internal format as `JP2OpenJPEG` instead of `GTiff` — despite having a `.tif` file extension. This was discovered because `driver_check` (in `file_checks.py`) was failing on **100% of files**, including clean tiles from the project's own dataset.

**How we found out**: Ran `rasterio.open(path).driver` directly and printed the full metadata dictionary. This confirmed the file's internal `driver` field genuinely said `JP2OpenJPEG`. Traced this back to `raw_data.py`'s `build_rgb_stack()` function, which does:
```python
with rasterio.open(red_path) as src:   # red_path is a .jp2 file
    meta = src.meta.copy()             # copies metadata FROM the jp2 source
meta.update(count=3, dtype=rgb.dtype)  # only updates count and dtype, not driver
```
The metadata dictionary — including the `driver` field — was copied directly from the original `.jp2` source band files and never explicitly overridden before being used to write the output. Rasterio trusts the `driver` field to decide the *actual internal write format*, regardless of what file extension you give it.

**What we did**: Identified the one-line fix (`meta.update(count=3, dtype=rgb.dtype, driver="GTiff")`) but made a deliberate decision **not** to immediately regenerate the entire dataset, given project time constraints. Documented this clearly as tracked technical debt rather than silently ignoring it or pretending it didn't exist.

**What we learned**: Copying metadata dictionaries wholesale from a source file (`.copy()`) is convenient but dangerous — it silently carries over *every* field, including ones you didn't think about, unless you explicitly override them. This is a good general lesson about defensive coding: when reusing another object's configuration, be explicit about every field you actually intend to keep versus override, rather than assuming a partial `.update()` call handles everything.

---

## Challenge 8: A chart that visually contradicted its own underlying data (histogram color bug)

**What happened**: An overlaid histogram chart (showing Red/Green/Blue pixel value distributions on one plot) showed a large spike at pixel-value zero rendered in **blue** — but direct numeric measurement had already confirmed Red and Green had the highest zero-fractions (~24%), while Blue had the lowest (~1%).

**How we found out**: This was flagged but not fully root-caused within the project's time budget — it was documented as an open, unresolved issue rather than guessed at and potentially "fixed" incorrectly. A debug script was prepared (splitting the overlaid chart into three separate side-by-side subplots, one per band, to remove any ambiguity from alpha-blended overlapping colors) but not executed to conclusion.

**What we did**: Made a conscious decision to flag this clearly as a known, unresolved bug rather than ship a visualization that might mislead a viewer, and moved on to higher-priority remaining work given the project timeline.

**What we learned**: Not every bug needs to be fixed immediately — sometimes the right engineering call is to clearly document a known issue and prioritize other work, as long as the documentation is honest and specific enough that someone (including future-you) can pick it up later without starting from scratch. This is different from ignoring a problem; it's a scoped, deliberate deferral.

---

## Challenge 9: Windows-specific and environment-specific issues

**What happened**: Several unrelated small issues traced back to the Windows/PowerShell environment specifically:
- `SyntaxWarning: invalid escape sequence` from a Windows file path string without an `r` prefix (raw string)
- Character encoding mismatches (`—` em-dashes appearing as `â€"` mojibake) when reading UTF-8 content on a Windows terminal defaulting to a different encoding
- CSV files needing `newline=""` when opened for writing on Windows, to avoid Python's `csv` module double-adding line endings
- A `ModuleNotFoundError: No module named 'rasterio'` inside `pytest`, caused by a virtual environment (`.venv`) that hadn't had the project's dependencies installed into it, separate from the global Python environment used for everything else

**How we found out**: Each surfaced naturally during testing — encoding issues were visible directly in terminal/CSV output; the pytest import error showed a clear traceback pointing to the missing module.

**What we did**: 
- Used raw strings (`r"D:\path\to\file"`) for Windows paths
- Set `ensure_ascii=True` in JSON output to force safe ASCII-only encoding regardless of terminal quirks
- Added `newline=""` to all file-writing `open()` calls
- Installed the full dependency list directly into the active `.venv`

**What we learned**: Cross-platform quirks (especially Windows-specific ones around paths, encoding, and line endings) are a real, recurring category of bugs distinct from logic bugs — worth checking for specifically when something behaves strangely despite the code logic looking correct. Also: always confirm *which* Python environment/interpreter is actually active before debugging a "missing module" error — `python -c "import sys; print(sys.executable)"` is a fast way to check.

---

## Summary: the meta-lesson across all these challenges

The single biggest recurring pattern across every challenge in this project: **never trust a threshold or a technique until you've tested it against real, known data — and when it fails, investigate with a targeted debug script rather than guessing at a fix.** Nearly every real bug in this project (saturation-by-line, noise detection, spatial anomaly, the NoData map) was found and correctly diagnosed by the same basic process:
1. Notice a result doesn't match expectations
2. Write a small, focused debug script that prints the actual underlying numbers directly
3. Compare those numbers against what was assumed
4. Fix based on evidence, not guesswork
5. Document the reasoning in code comments so the "why" isn't lost later

This is a transferable debugging discipline, not something specific to satellite imagery — it applies to almost any data-driven software project.

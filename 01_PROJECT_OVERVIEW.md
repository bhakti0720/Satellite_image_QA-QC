# Satellite Image QA/QC Pipeline — Project Overview

A beginner-friendly, interview-ready explanation of what this project does, how it's built, and why every major decision was made.

---

## 1. What problem does this project solve?

When you download satellite images (Sentinel-2, in this case), not every image is usable. Some tiles are corrupted, some have clouds covering everything, some are blurry, some have missing data patches, some are in the wrong coordinate system. If you feed bad images into a mapping or analysis pipeline, you get bad results — and there's no way to check hundreds of images by eye.

This project is an **automated inspector**. You give it a satellite image tile, and it runs the image through 9 categories of quality checks and gives you back:
- A **pass/fail verdict**
- A **0–100 quality score**
- A **list of exactly what's wrong**, with severity levels

Think of it like a factory quality-control line, except the "product" is a satellite image tile instead of a physical part.

---

## 2. What is the input data, exactly?

- **Source**: Sentinel-2 L2A satellite imagery (a European Space Agency satellite product)
- **Region**: Ahmedabad, Gujarat, India
- **Format**: GeoTIFF files, 512×512 pixels, 3 bands (Red/Green/Blue — bands B04/B03/B02), `uint16` data type, 10-meter resolution
- **Coordinate system**: UTM Zone 42N (EPSG:32642) — this is just a way of representing real-world locations as flat X/Y meter coordinates instead of latitude/longitude, chosen because it's accurate for this specific region of the world

**Why `uint16` and not a normal 0–255 image?** Satellite sensors measure "reflectance" — how much light bounces off the ground — with much finer precision than a normal photo. Values roughly range 0–10,000+ (representing 0–100%+ reflectance). `uint16` (unsigned 16-bit integer) can hold values from 0 to 65,535, which is plenty of room for this data. A normal image (`uint8`) can only hold 0–255, which isn't precise enough for scientific measurement.

---

## 3. High-level architecture (the "big picture" flow)

```
                    ┌─────────────────────┐
                    │   Raw .SAFE folder    │  (Sentinel-2 original download)
                    └──────────┬───────────┘
                               │  raw_data.py: extract bands, tile into 512x512
                               ▼
                    ┌─────────────────────┐
                    │  data/dataset/        │  (clean tiles + SCL companion files)
                    │  data/test/           │  (synthetic defective tiles)
                    └──────────┬───────────┘
                               │  RasterInspector: open file, extract metadata
                               ▼
                    ┌─────────────────────┐
                    │   9 Check Modules     │  (file, metadata, geospatial, nodata,
                    │   (src/checks/)       │   statistics, saturation, blur, noise,
                    │                       │   blackline, cloud, anomaly)
                    └──────────┬───────────┘
                               │  each check returns CheckResult(s)
                               ▼
                    ┌─────────────────────┐
                    │   QAResult            │  (bundles all check results for 1 image)
                    │   (src/engine/)       │
                    └──────────┬───────────┘
                               │  scoring.py: critical gate + weighted score
                               ▼
                    ┌─────────────────────┐
                    │  Scored QAResult      │  passed=True/False, score=0-100
                    └──────────┬───────────┘
                               │
                  ┌────────────┴────────────┐
                  ▼                         ▼
          ┌───────────────┐       ┌───────────────────┐
          │  CSV / JSON     │       │  Visualizations     │
          │  reports        │       │  (thumbnails, maps) │
          └───────────────┘       └───────────────────┘
```

**In plain words**: raw satellite data gets cut into tiles → each tile gets inspected → each tile runs through 9 categories of automated checks → all the results get bundled into one scorecard per image → that scorecard gets turned into a pass/fail decision and a report you can read.

---

## 4. Why this specific architecture? (design philosophy)

### 4.1 Separation of concerns
Every piece of this project has exactly one job:
- `RasterInspector` — only opens files and reads metadata. Never judges anything.
- Check modules (`src/checks/`) — only judge whether something is right or wrong. Never open files themselves (they receive already-extracted metadata).
- `qa_engine.py` — only orchestrates (calls things in the right order). Contains no detection logic itself.
- `scoring.py` — only turns a list of results into a verdict. Doesn't know or care *how* those results were produced.
- `reporting/` — only turns a verdict into a file format (CSV/JSON). Doesn't run any checks.

**Why does this matter?** If a bug shows up, you know exactly which layer to look in. If "the CRS check is wrong," you look in `geospatial_checks.py` — you don't need to understand scoring or reporting at all. This is called **separation of concerns**, a core software engineering principle, and it's the single biggest reason this project stayed manageable as it grew to 10 check modules.

### 4.2 One consistent function signature everywhere
Every check module has a function shaped exactly like this:
```python
def run_XXX_checks(meta: RasterMetadata) -> list[CheckResult]:
```

This uniformity is what makes `qa_engine.py` so simple — it just calls all nine `run_*_checks(meta)` functions in a row and appends every result to one big list. No special-casing, no "if this category, do X; if that category, do Y." This is a common interview talking point: **consistent interfaces reduce complexity at the integration point.**

### 4.3 Two-tier scoring instead of one flat score
Some problems are so severe that no amount of "good" scores elsewhere should rescue the image (e.g., wrong CRS makes an image geographically useless even if it's perfectly sharp). Other problems are more like "this reduces quality but the image is still usable" (e.g., slightly blurry). The two-tier system reflects this real-world difference:
- **Tier 1 (hard gate)**: any `CRITICAL` failure → automatic fail, score = 0
- **Tier 2 (weighted score)**: for everything else, start at 100 and subtract points per failed check, weighted by how much that failure actually matters to usability

### 4.4 Dataclasses instead of dictionaries everywhere
Throughout this project, information is passed around using Python **dataclasses** (`RasterMetadata`, `CheckResult`, `QAResult`, `BandStatistics`) instead of plain dictionaries. Reasons:
- Autocomplete in your editor (`result.width` vs `result["width"]` — the second one has zero typo protection)
- Type hints act as documentation
- A dataclass has a fixed, known shape — you can't accidentally have one object missing a field that another has

---

## 5. Walking through the full pipeline, function by function

### Step 1 — `RasterInspector.inspect()`
Opens the file with `rasterio` and extracts a `RasterMetadata` object: width, height, band count, dtype, CRS, transform, bounds, nodata value, driver, file size. If the file can't be opened, it doesn't crash — it returns a `RasterMetadata` with `is_valid=False` and an error message.

**Key design idea**: every downstream module trusts that `RasterInspector` already handled the "can we even open this" question, so nothing else needs to repeat that logic.

### Step 2 — Nine check modules run against the metadata
Each module receives the same `RasterMetadata` object and independently decides pass/fail for its category. A module's `run_XXX_checks()` function:
1. Checks if `meta.is_valid` — if not, returns early with a single critical failure (no point checking things that need data that doesn't exist)
2. Calls each of its individual `check_XXX()` functions
3. Returns the full list of `CheckResult` objects

### Step 3 — `qa_engine.run_qa(filepath)` orchestrates everything
```python
meta = RasterInspector(filepath).inspect()
all_checks = []
all_checks.extend(run_file_checks(meta))
all_checks.extend(run_metadata_checks(meta))
... (all 10 categories)
result = QAResult(filepath, filename, meta, all_checks)
return score_qa_result(result)
```
This is intentionally "boring" code — it doesn't need to be clever, because all the real logic already lives inside the check modules.

### Step 4 — `scoring.py` turns results into a verdict
```python
def score_qa_result(qa_result, min_passing_score=60.0):
    if has_critical_failure(qa_result):
        qa_result.passed = False
        qa_result.score = 0.0
        return qa_result

    score = compute_weighted_score(qa_result)   # starts at 100, subtracts weighted penalties
    qa_result.score = score
    qa_result.passed = score >= min_passing_score
    return qa_result
```

### Step 5 — Reporting
`csv_report.py` and `json_report.py` both take a `list[QAResult]` and serialize it. CSV packs all failed checks into one semicolon-separated text column per image (human-skimmable, one row per image). JSON preserves full nested structure (every individual check as its own object — better for programmatic use later, like an HTML report or dashboard).

---

## 6. Common interview questions and how to answer them

**Q: Walk me through what happens when I call `run_qa("tile.tif")`.**
> It opens the file with `RasterInspector`, which reads structural and geospatial metadata without loading full pixel data unless needed. That metadata gets passed to all 10 check modules in sequence, each returning a list of `CheckResult` objects (pass/fail + severity + message). All results get bundled into one `QAResult` object. Then `scoring.py` checks: if any result has `CRITICAL` severity and failed, the whole image auto-fails with score 0. Otherwise, it starts at 100 points and subtracts a weighted penalty for each failed `WARNING`-level check, and compares the final score against a passing threshold (default 60).

**Q: Why did you split checks into 10 separate modules instead of one big function?**
> Single Responsibility Principle — each module owns one category of judgment, which makes the codebase easier to test, debug, and extend. If I need to add an 11th check category, I don't touch any existing code, I just add a new module and one line in the engine.

**Q: How do you decide if something is CRITICAL vs WARNING severity?**
> CRITICAL is reserved for failures that make the image fundamentally unusable regardless of anything else — file won't open, wrong CRS (geographically meaningless), core data structurally missing. WARNING is for quality issues that reduce usability but don't invalidate the image outright — blur, noise, minor saturation. This mirrors how real QA/QC systems work: some defects are showstoppers, others are quality-of-service issues.

**Q: What was the hardest part of this project?**
> Calibrating thresholds empirically. Several of my check thresholds (noise, spatial anomaly) initially looked reasonable on paper but failed when tested against real paired clean/defective samples — I had to build debug scripts to compare actual clean vs. defective values, discover the real separation (or lack of it), and in a couple of cases discover the *technique itself* wasn't well suited to the specific type of defect, not just the threshold. (See the Challenges document for full examples.)

**Q: How would you extend this to a new region or satellite?**
> Most of the geospatial assumptions (CRS `EPSG:32642`, `10000` reflectance ceiling) are currently hardcoded as function defaults rather than pulled from a config file. To extend to a new region, you'd update `geospatial_checks.py`'s expected CRS and potentially `statistics_check.py`'s reflectance range if using a different sensor. I built (but didn't fully wire in) a `config/thresholds.yaml` file specifically to make this kind of change centralized rather than requiring code edits across multiple files.

**Q: What would you do differently / what's technical debt in this project?**
> Three main things, all explicitly documented in the README: (1) a driver bug where files are saved internally as JP2 format despite having a `.tif` extension, because the tiling script copied metadata directly from the source JP2 files without overriding the driver field; (2) the noise and spatial-anomaly checks were calibrated on very limited sample sizes (sometimes just one paired clean/defective example) and a full batch run showed real false-positive rates that would need more data to fix properly; (3) thresholds live as hardcoded function defaults rather than being read from the `config/thresholds.yaml` file I built as a reference.

---

## 7. Key vocabulary (in case you get asked to define terms)

| Term | Simple definition |
|---|---|
| **GeoTIFF** | A TIFF image file with extra embedded metadata about real-world location (CRS, transform, bounds) |
| **CRS (Coordinate Reference System)** | A system for mapping pixel positions to real-world locations (like UTM Zone 42N) |
| **Affine transform** | 6 numbers that convert pixel row/column into real-world coordinates |
| **Reflectance** | How much light a surface bounces back — what satellite sensors actually measure |
| **NoData** | Pixels with no real data (often at image edges, or from sensor gaps) |
| **SCL (Scene Classification Layer)** | A companion band from Sentinel-2 that classifies each pixel as cloud, shadow, vegetation, water, etc. |
| **Severity (CRITICAL/WARNING/INFO)** | How serious a failed check is — CRITICAL always fails the image, WARNING only lowers the score |
| **Z-score** | A statistical measure of "how many standard deviations away from average is this value" |
| **Percentile stretch** | A way to normalize pixel values for display, ignoring extreme outlier pixels |
| **Laplacian variance** | A measure of image sharpness — high = sharp, low = blurry |
| **Dataclass** | A Python class designed purely to hold structured data, with auto-generated boilerplate |

---

## 8. What's genuinely complete vs. what's a known gap

**Fully working and tested:**
- Data pipeline (tiling, defect generation, SCL extraction)
- All 10 check categories
- Engine (orchestration + two-tier scoring)
- CSV and JSON reporting
- Batch processing across the full dataset
- Automated pytest test suite (10 tests, all passing)
- Two visualization tools (image preview, NoData map)

**Known, documented gaps** (see Challenges document for the full story on each):
- Driver bug (files internally JP2, not true GeoTIFF)
- Noise check — thin calibration data
- Spatial anomaly check — breaks down on large-area defects
- Striping check — never tested against a dedicated striping defect
- Histogram visualization — has a color-mapping bug
- HTML reporting — descoped due to time
- `config/thresholds.yaml` — built as reference, not fully wired into the check modules

# Satellite Image QA/QC Pipeline

An automated quality assurance pipeline for Sentinel-2 L2A multispectral imagery, built for a project with ISRO. Validates 512×512 GeoTIFF tiles over the Ahmedabad region (UTM Zone 42N, EPSG:32642) across nine quality check categories, producing a scored pass/fail verdict per image.

## What it does

Given a folder of satellite image tiles, the pipeline runs each tile through 10 independent check categories and produces:
- A **hard pass/fail verdict** (any critical failure — e.g. corrupt file, wrong CRS, missing data — fails the tile outright)
- A **0–100 quality score** for tiles that pass the critical gate, based on weighted warnings (blur, noise, saturation, etc.)
- **CSV and JSON reports** summarizing results across an entire dataset

## Check categories

| # | Category | What it catches |
|---|----------|------------------|
| 1 | File integrity | Corrupt files, wrong driver, wrong band count |
| 2 | Metadata | Wrong dimensions, dtype, pixel resolution |
| 3 | Geospatial | Wrong/missing CRS, invalid transform, unexpected rotation |
| 4 | NoData analysis | Missing-data regions, zero-pixel fraction |
| 5 | Pixel statistics | Flat/constant bands, out-of-range values, low contrast |
| 6 | Saturation | Over/under-exposed pixels, sensor dropout lines |
| 7 | Image quality | Blur (Laplacian variance), noise (Immerkær estimator) |
| 8 | Visual artifacts | Sensor striping, spatial anomalies |
| 9 | Cloud/scene analysis | Cloud and shadow coverage via SCL classification |

## Quick start

```powershell
# Install dependencies
pip install rasterio numpy opencv-python Pillow PyYAML pytest matplotlib

# Run QA on a single file
python -c "from src.engine.qa_engine import run_qa; print(run_qa('path/to/tile.tif').summary())"

# Run QA across your full dataset, generate CSV + JSON reports
python scripts\batch_qa.py

# Run the automated test suite
python -m pytest -v
```

## Project structure

See folder tree in the repo. Key entry points:
- `src/engine/qa_engine.py` — main orchestrator (`run_qa(filepath)`)
- `scripts/batch_qa.py` — batch runner across a full dataset
- `src/checks/` — the 10 individual check modules
- `src/reporting/` — CSV/JSON report generation
- `src/visualization/` — thumbnail, NoData map, histogram, anomaly map generation

## Known limitations

This project was built under a 5-day timeline with deliberate scope decisions. The following are documented, tracked issues — not oversights:

1. **Driver bug (dataset-wide)**: All tiles are internally saved as `JP2OpenJPEG` format despite the `.tif` extension, due to `raw_data.py` copying source metadata (including the `driver` field) directly from the original `.jp2` band files. `driver_check` correctly flags every file in the current dataset as a result. **Fix**: add `driver="GTiff"` to the metadata update in `raw_data.py` and the defect-generation script, then regenerate the dataset.

2. **`noise_check` threshold**: calibrated against only one paired clean/noisy sample. A full batch run showed frequent false positives. Documented as a soft heuristic in `src/checks/noise_check.py`.

3. **`anomaly_check` (spatial anomaly)**: uses median + MAD (robust statistics) instead of mean + std, but was found to still degrade when an anomaly covers a large fraction (~25%+) of the tile — exactly the case for large dropout regions. A full batch run showed high false-positive rates on `scene1` tiles. Best suited to small, localized anomalies; large contiguous defects are more reliably caught by `nodata_check.py`'s dedicated spatial pattern check. Documented in `src/checks/anomaly_check.py`.

4. **`blackline_check` (striping)**: not yet validated against a dedicated constant-value striping defect (only indirectly, via the zero-dropout `black_line` defect, which it also correctly flags as a side effect).

5. **`histogram.py`**: has a known color-mapping bug where the rendered chart doesn't reliably match which band a spike belongs to. Flagged for future investigation; not currently used in any automated report.

6. **HTML reporting**: descoped given the project timeline. CSV and JSON reports (`src/reporting/`) provide complete, validated coverage instead.

7. **`config/thresholds.yaml`**: exists as a reference document centralizing every threshold and known limitation used across the check modules, but check modules currently still read thresholds from their own hardcoded defaults rather than this file. Wiring this in is a natural next step for anyone extending this project.

## Testing

`tests/test_qa_engine.py` and `tests/test_scoring.py` provide automated regression coverage — verifying each known synthetic defect type is correctly caught, and the two-tier scoring logic behaves correctly. Run with `python -m pytest -v`.

## Author's note

Built as a learning project in the geospatial/remote sensing domain, with an emphasis on calibrating every threshold against real data rather than trusting assumed defaults — several checks (noise, anomaly, saturation-line detection) were revised after empirical testing revealed the initial assumptions didn't hold on real Sentinel-2 tiles. Known limitations above are left honestly documented rather than hidden, consistent with that approach throughout.
import rasterio
import numpy as np

path = "data/test/black_line_2.tif"  # confirm this matches your real filename

with rasterio.open(path) as src:
    band1 = src.read(1)

zero_mask = (band1 == 0)
print(f"Total zero pixels: {np.sum(zero_mask)} / {zero_mask.size} ({np.sum(zero_mask)/zero_mask.size:.2%})")

row_fractions = zero_mask.mean(axis=1)
col_fractions = zero_mask.mean(axis=0)

print(f"\nMax row zero-fraction: {row_fractions.max():.2%} at row {row_fractions.argmax()}")
print(f"Max col zero-fraction: {col_fractions.max():.2%} at col {col_fractions.argmax()}")

# Show top 5 rows/cols by zero-fraction, to see the actual shape of the defect
print(f"\nTop 5 rows by zero fraction:")
top_rows = np.argsort(row_fractions)[-5:][::-1]
for r in top_rows:
    print(f"  row {r}: {row_fractions[r]:.2%}")

print(f"\nTop 5 cols by zero fraction:")
top_cols = np.argsort(col_fractions)[-5:][::-1]
for c in top_cols:
    print(f"  col {c}: {col_fractions[c]:.2%}")
    
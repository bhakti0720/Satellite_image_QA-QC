from src.visualization.histogram import save_histogram

test_files = [
    "data/dataset/scene2_tile_r6144_c5120.tif",   # clean
    "data/test/blurred_2.tif",                      # blurred (from earlier stats, similar range but should look visually different)
    "data/test/missing_data_2.tif",                 # heavy zero-pixel spike expected
]

for path in test_files:
    name = path.split("/")[-1].replace(".tif", "_histogram.png")
    out_path = save_histogram(path, f"reports/figures/{name}")
    print(f"Saved: {out_path}")
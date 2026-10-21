from src.visualization.image_preview import save_preview_png

test_files = [
    "data/dataset/scene2_tile_r6144_c5120.tif",
    "data/test/black_line_2.tif",
    "data/test/wrong_crs_2.tif",
]

for path in test_files:
    name = path.split("/")[-1].replace(".tif", ".png")
    out_path = save_preview_png(path, f"reports/figures/{name}")
    print(f"Saved: {out_path}")
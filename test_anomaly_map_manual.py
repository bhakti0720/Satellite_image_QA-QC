from src.visualization.anomaly_map import save_anomaly_map

test_files = [
    "data/dataset/scene2_tile_r6144_c5120.tif",
    "data/test/missing_data_2.tif",
]

for path in test_files:
    name = path.split("/")[-1].replace(".tif", "_anomaly_map.png")
    out_path = save_anomaly_map(path, f"reports/figures/{name}")
    print(f"Saved: {out_path}")
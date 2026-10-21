from src.inspector.raster_inspector import RasterInspector

# TODO: replace these with real filenames from your dataset/test folders
test_files = [
    "data/dataset/scene1_tile_r512_c6656.tif",       # replace with a real clean tile
    "data/test/wrong_crs_2.tif",    # replace with a real defective tile
]

for path in test_files:
    result = RasterInspector(path).inspect()
    print(f"\n--- {path} ---")
    print(f"Valid: {result.is_valid}")
    if result.is_valid:
        print(f"Size: {result.width}x{result.height}, Bands: {result.band_count}, Dtype: {result.dtype}")
        print(f"CRS: {result.crs}")
        print(f"Pixel size: {result.pixel_size_x}, {result.pixel_size_y}")
        print(f"NoData: {result.nodata_value}")
    else:
        print(f"Error: {result.error_message}")

# Test with a corrupt/garbage file too
with open("data/test/corrupt_test.tif", "w") as f:
    f.write("this is not a valid tif")

result = RasterInspector("data/test/corrupt_test.tif").inspect()
print(f"\n--- corrupt_test.tif ---")
print(f"Valid: {result.is_valid}")
print(f"Error: {result.error_message}")
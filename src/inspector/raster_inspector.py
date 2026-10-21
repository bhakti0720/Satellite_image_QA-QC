"""
raster_inspector.py
Opens a raster file and extracts structural + geospatial metadata.
"""

import rasterio
from rasterio.errors import RasterioIOError
from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class RasterMetadata:
    filepath: str
    filename: str
    file_size_bytes: int
    is_valid: bool
    error_message: Optional[str] = None

    # Structural
    width: Optional[int] = None
    height: Optional[int] = None
    band_count: Optional[int] = None
    dtype: Optional[str] = None

    # Geospatial
    crs: Optional[str] = None
    transform: Optional[tuple] = None
    pixel_size_x: Optional[float] = None
    pixel_size_y: Optional[float] = None
    bounds: Optional[tuple] = None

    # NoData
    nodata_value: Optional[float] = None

    # Driver / format
    driver: Optional[str] = None


class RasterInspector:
    """Opens a raster and extracts metadata without loading full pixel data."""

    def __init__(self, filepath: str):
        self.filepath = filepath

    def inspect(self) -> RasterMetadata:
        filename = os.path.basename(self.filepath)

        if not os.path.exists(self.filepath):
            return RasterMetadata(
                filepath=self.filepath,
                filename=filename,
                file_size_bytes=0,
                is_valid=False,
                error_message="File does not exist"
            )

        file_size = os.path.getsize(self.filepath)

        try:
            with rasterio.open(self.filepath) as src:
                return RasterMetadata(
                    filepath=self.filepath,
                    filename=filename,
                    file_size_bytes=file_size,
                    is_valid=True,
                    width=src.width,
                    height=src.height,
                    band_count=src.count,
                    dtype=src.dtypes[0],
                    crs=str(src.crs) if src.crs else None,
                    transform=tuple(src.transform)[:6],
                    pixel_size_x=abs(src.transform.a),
                    pixel_size_y=abs(src.transform.e),
                    bounds=tuple(src.bounds),
                    nodata_value=src.nodata,
                    driver=src.driver,
                )
        except RasterioIOError as e:
            return RasterMetadata(
                filepath=self.filepath,
                filename=filename,
                file_size_bytes=file_size,
                is_valid=False,
                error_message=f"RasterioIOError: {str(e)}"
            )
        except Exception as e:
            return RasterMetadata(
                filepath=self.filepath,
                filename=filename,
                file_size_bytes=file_size,
                is_valid=False,
                error_message=f"Unexpected error: {str(e)}"
            )
import numpy as np
from typing import TYPE_CHECKING

from scripts.rasterio_support import ensure_rasterio_proj_data

if TYPE_CHECKING:
    from typing import Any


async def read_raster_as_json(raster_bytes: bytes):

    from rasterio.io import MemoryFile

    ensure_rasterio_proj_data()

    if not raster_bytes:
        raise FileNotFoundError("Failed to open file")

    with MemoryFile(raster_bytes) as memory_file:
        with memory_file.open() as dataset:
            data = dataset.read(1)
            transform = dataset.transform
            nodata_value = dataset.nodata if dataset.nodata is not None else -9999

            x_size, y_size = dataset.width, dataset.height
            x_index, y_index = np.meshgrid(np.arange(x_size), np.arange(y_size))

            lons = transform.c + (x_index + 0.5) * transform.a
            lats = transform.f + (y_index + 0.5) * transform.e

            lons = lons.flatten()
            lats = lats.flatten()
            values = data.flatten()

            valid_mask = values != nodata_value
            lons = lons[valid_mask]
            lats = lats[valid_mask]
            values = values[valid_mask]

            origin = {
                'lat': transform.f,
                'lng': transform.c,
            }
            pixel_size = {
                'lat': abs(transform.e),
                'lng': abs(transform.a),
            }

            data_dict = {
                f"{lat:.5f} {lon:.5f}": round(float(val), 2)
                for lat, lon, val in zip(lats, lons, values)
            }

            return {
                'data': data_dict,
                'origin': origin,
                'pixel_size': pixel_size,
            }

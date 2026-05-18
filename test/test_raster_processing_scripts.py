import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from schemas.feature import Feature
from scripts.create_raster_obj import read_raster_as_json
from scripts.geo_processing import clip_and_get_pixel_values
from scripts.rasterio_support import ensure_rasterio_proj_data


def build_raster_bytes(values: np.ndarray) -> bytes:
    ensure_rasterio_proj_data()

    with MemoryFile() as memory_file:
        with memory_file.open(
            driver="GTiff",
            height=values.shape[0],
            width=values.shape[1],
            count=1,
            dtype="float32",
            crs="EPSG:4674",
            transform=from_origin(10, 20, 0.5, 0.5),
            nodata=-9999,
        ) as dataset:
            dataset.write(values.astype("float32"), 1)

        return memory_file.read()


@pytest.mark.asyncio
async def test_read_raster_as_json_returns_expected_origin_pixel_size_and_values():
    raster_bytes = build_raster_bytes(np.array([[1, 2], [3, 4]], dtype="float32"))

    result = await read_raster_as_json(raster_bytes)

    assert result["origin"] == {"lat": 20.0, "lng": 10.0}
    assert result["pixel_size"] == {"lat": 0.5, "lng": 0.5}
    assert result["data"] == {
        "19.75000 10.25000": 1.0,
        "19.75000 10.75000": 2.0,
        "19.25000 10.25000": 3.0,
        "19.25000 10.75000": 4.0,
    }


@pytest.mark.asyncio
async def test_clip_and_get_pixel_values_returns_sorted_values_for_polygon():
    raster_bytes = build_raster_bytes(np.array([[1, 2], [3, 4]], dtype="float32"))
    feature = Feature.model_validate(
        {
            "type": "Feature",
            "properties": {"name": "Test area"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [10.0, 20.0],
                        [11.0, 20.0],
                        [11.0, 19.0],
                        [10.0, 19.0],
                        [10.0, 20.0],
                    ]
                ],
            },
        }
    )

    result = await clip_and_get_pixel_values(feature, raster_bytes, "solar_test")

    assert result == {
        "type": "ResponseData",
        "properties": {
            "pixelValues": [[4.0, 3.0, 2.0, 1.0]],
            "size": 1.0,
            "name": "Test area",
        },
    }
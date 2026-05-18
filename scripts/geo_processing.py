import json
from typing import TYPE_CHECKING

import numpy as np
from shapely.geometry import shape, mapping

from schemas.feature import Feature
from scripts.rasterio_support import ensure_rasterio_proj_data

if TYPE_CHECKING:
    from typing import Any


async def clip_and_get_pixel_values(feature: Feature, raster_bytes: bytes, raster_name: str):

    from rasterio.io import MemoryFile
    from rasterio.mask import mask

    ensure_rasterio_proj_data()

    if not raster_bytes:
        raise RuntimeError("Could not open source dataset")

    pixel_values_list = []

    geometry = shape(feature.geometry.model_dump())

    if raster_name.split('_')[0] == 'wind':
        buffered_geom = geometry.buffer(.35356/111.11) # .35356 = .25 * sqrt(2) ; .25 = distancia entre pixels / 2 ; sqrt(2) = diagonal do quadrado
    elif raster_name.split('_')[0] == 'ghi':
        buffered_geom = geometry.buffer(.35356/111.11)
    else:
        buffered_geom = geometry

    with MemoryFile(raster_bytes) as memory_file:
        with memory_file.open() as source_dataset:
            nodata_value = source_dataset.nodata if source_dataset.nodata is not None else -9999
            masked_array, _ = mask(
                source_dataset,
                [mapping(buffered_geom)],
                crop=False,
                filled=False,
            )

    band = np.ma.masked_invalid(masked_array[0])
    filtered_array = np.ma.masked_equal(band, nodata_value)
    pixel_values = filtered_array.compressed().tolist()
    pixel_values_sorted_desc = sorted(pixel_values, reverse=True)
    pixel_values_list.append(pixel_values_sorted_desc)

    return {'type': 'ResponseData', 'properties': {
        'pixelValues': pixel_values_list, 'size': len(pixel_values_list[0])/4, 'name': feature.properties.name}}
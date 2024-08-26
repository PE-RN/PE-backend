import json

import numpy as np
from asyncer import asyncify
from osgeo import gdal, ogr, osr
from osgeo.gdal import Dataset

from schemas.feature import Feature


async def clip_and_get_pixel_values(feature: Feature, src_ds: Dataset):

    if not src_ds:
        raise RuntimeError("Could not open source dataset")

    srcband = src_ds.GetRasterBand(1)

    pixel_values_list = []

    geometry = json.dumps(feature.geometry.model_dump())
    # Convert GeoJSON to an OGR geometry
    geom = await asyncify(ogr.CreateGeometryFromJson)(geometry)
    # Prepare an in-memory raster for the mask
    mem_driver = await asyncify(gdal.GetDriverByName)('MEM')
    mask_ds = mem_driver.Create('', src_ds.RasterXSize, src_ds.RasterYSize, 1, gdal.GDT_Byte)
    mask_ds.SetGeoTransform(src_ds.GetGeoTransform())
    mask_ds.SetProjection(src_ds.GetProjection())

    # Prepare an in-memory vector layer to hold the geometry
    geom_srs = osr.SpatialReference()
    await asyncify(geom_srs.ImportFromEPSG)(4674)  # adjust as needed
    driver = await asyncify(ogr.GetDriverByName)('Memory')
    geom_ds = await asyncify(driver.CreateDataSource)('geom_ds')
    geom_layer = await asyncify(geom_ds.CreateLayer)('geom_layer', srs=geom_srs)
    geom_defn = geom_layer.GetLayerDefn()
    geom_feature = ogr.Feature(geom_defn)
    geom_feature.SetGeometry(geom)
    await asyncify(geom_layer.CreateFeature)(geom_feature)

    # Rasterize directly using the geometry
    await asyncify(gdal.RasterizeLayer)(mask_ds, [1], geom_layer, burn_values=[1])

    # Create a masked array
    src_array = await asyncify(srcband.ReadAsArray)()
    raster_band = await asyncify(mask_ds.GetRasterBand)(1)
    mask_array = await asyncify(raster_band.ReadAsArray)()
    masked_array = np.ma.masked_where(mask_array == 0, src_array)

    # Filter out specific pixel values, e.g., -9999
    filtered_array = np.ma.masked_equal(masked_array, -9999)

    # Extract pixel values excluding -9999
    pixel_values = filtered_array.compressed().tolist()
    pixel_values_sorted_desc = sorted(pixel_values, reverse=True)
    pixel_values_list.append(pixel_values_sorted_desc)

    return {'type': 'ResponseData', 'properties': {
        'pixelValues': pixel_values_list, 'size': len(pixel_values_list[0]) / 4, 'name': feature.properties.name}}

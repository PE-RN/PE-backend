import sys
import json
from osgeo import gdal, ogr, osr
import numpy as np
from models.feature import FeatureModel


async def clip_and_get_pixel_values(features: list[FeatureModel], input_tiff_path):
    
    # Load the source raster
    src_ds = gdal.Open(input_tiff_path)
    if not src_ds:
        raise RuntimeError("Could not open source dataset")

    srcband = src_ds.GetRasterBand(1)

    pixel_values_list = []
    
    for feature in features:
        geometry  = json.dumps(feature.geometry.model_dump())
        # Convert GeoJSON to an OGR geometry
        geom = ogr.CreateGeometryFromJson(geometry)
        # Prepare an in-memory raster for the mask
        mem_driver = gdal.GetDriverByName('MEM')
        mask_ds = mem_driver.Create('', src_ds.RasterXSize, src_ds.RasterYSize, 1, gdal.GDT_Byte)
        mask_ds.SetGeoTransform(src_ds.GetGeoTransform())
        mask_ds.SetProjection(src_ds.GetProjection())

        # Prepare an in-memory vector layer to hold the geometry
        geom_srs = osr.SpatialReference()
        geom_srs.ImportFromEPSG(4674)  # adjust as needed
        geom_ds = ogr.GetDriverByName('Memory').CreateDataSource('geom_ds')
        geom_layer = geom_ds.CreateLayer('geom_layer', srs=geom_srs)
        geom_defn = geom_layer.GetLayerDefn()
        geom_feature = ogr.Feature(geom_defn)
        geom_feature.SetGeometry(geom)
        geom_layer.CreateFeature(geom_feature)

        # Rasterize directly using the geometry
        gdal.RasterizeLayer(mask_ds, [1], geom_layer, burn_values=[1])

        # Create a masked array
        src_array = srcband.ReadAsArray()
        mask_array = mask_ds.GetRasterBand(1).ReadAsArray()
        masked_array = np.ma.masked_where(mask_array == 0, src_array)

        # Filter out specific pixel values, e.g., -9999
        filtered_array = np.ma.masked_equal(masked_array, -9999)

        # Extract pixel values excluding -9999
        pixel_values = filtered_array.compressed().tolist()
        pixel_values_sorted_desc = sorted(pixel_values, reverse=True)
        pixel_values_list.append(pixel_values_sorted_desc)

    
    return [{'type': 'FeatureCollection','features': [], 'properties': { 'pixelValues': values}} for values in pixel_values_list]
    

""" if __name__ == "__main__":
    geojson_file_path = sys.argv[1]
    input_tiff_path = sys.argv[2]

    with open(geojson_file_path, 'r') as file:
        geojson_input = json.load(file)['geometry']

    result = clip_and_get_pixel_values(geojson_input, input_tiff_path)
    print(json.dumps(result))
 """
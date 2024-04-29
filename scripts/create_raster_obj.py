from osgeo import gdal
import numpy as np


async def read_raster_as_json(input_tiff_path):
    # Open the raster file
    ds = gdal.Open(input_tiff_path)
    if not ds:
        raise FileNotFoundError(f"Failed to open file: {input_tiff_path}")

    # Get the first band
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray()

    # Get transform to calculate geographic coordinates
    transform = ds.GetGeoTransform()

    # Prepare meshgrid for coordinates
    x_size, y_size = band.XSize, band.YSize
    x_index, y_index = np.meshgrid(np.arange(x_size), np.arange(y_size))

    # Calculate the geographic coordinates of the center of each pixel
    lons = transform[0] + (x_index + 0.5) * transform[1]
    lats = transform[3] + (y_index + 0.5) * transform[5]

    # Flatten arrays
    lons = lons.flatten()
    lats = lats.flatten()
    values = data.flatten()

    # Filter out no-data values (assuming -9999 as no-data value)
    valid_mask = (values != -9999)
    lons = lons[valid_mask]
    lats = lats[valid_mask]
    values = values[valid_mask]

    # Use the first valid pixel's coordinates as the origin
    origin = {
        'lat': transform[3],
        'lng': transform[0]
    }

    # Assuming pixel size from transform
    pixel_size = {
        'lat': -transform[5],  # Usually negative
        'lng': -transform[1]
    }

    # Round the coordinates and values, and create dictionary
    data_dict = {f"{lat:.5f} {lon:.5f}": round(float(val), 2) for lat, lon, val in zip(lats, lons, values)}

    return {
        'data': data_dict,
        'origin': origin,
        'pixel_size': pixel_size
    }

from shapely.geometry import shape, mapping, LineString, Point, MultiLineString, MultiPoint
from shapely.ops import unary_union, transform
from pyproj import CRS, Transformer
import numpy as np
import pyproj
from shapely.ops import transform
from functools import partial


async def calculate_mean_of_vectors(vectors):

    array = np.array(vectors)
    return np.round(np.mean(array, axis=0), 2)

async def area_in_km2(geom):
    # Define the source and target coordinate reference systems
    source_crs = CRS('EPSG:4326')  # WGS84
    target_crs = CRS('EPSG:6933')  # Equal Area projection

    # Create a transformer that performs the projection transformation
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)

    # Transform the geometry using the transformer
    projected_geom = transform(transformer.transform, geom)

    # Calculate the area in square kilometers
    return round(projected_geom.area / 1e6, 2)  # convert square meters to square kilometers


async def mean_stats(geojson_loaded_from_db, geojson_sent_by_user, energy_type):

    # Convert GeoJSON features to Shapely geometries
    geometries1 = [(shape(feature['geometry']), feature['properties']) for feature in geojson_loaded_from_db['features']]
    user_geometry = shape(geojson_sent_by_user.geometry.dict())

    # Handle LineStrings: Calculate length instead of area
    if isinstance(user_geometry, LineString):
        user_statistic = user_geometry.length * 111.11  # Calculate length in km for LineString
        stat_label = 'length'
    else:
        user_statistic = await area_in_km2(user_geometry)  # Calculate area for other geometries
        stat_label = 'area'

    is_wind = False
    # Apply a buffer to ensure intersections are captured
    if energy_type.split('_')[0] == 'wind':
        buffered_geom = user_geometry.buffer(1.5/111.11, join_style='mitre')
        is_wind = True
    elif energy_type.split('_')[0] == 'ghi':
        buffered_geom = user_geometry.buffer(.5/111.11, join_style='mitre')

    # Clip geometries from the first GeoJSON with the union of the second GeoJSON
    clipped_features = []
    num_pixels = 0
    for geometry, properties in geometries1:
        clipped_geometry = geometry.intersection(buffered_geom)
        if not clipped_geometry.is_empty:
            clipped_features.append({
                "type": "Feature",
                "geometry": mapping(clipped_geometry),
                "properties": properties
            })
            num_pixels += 1
    # Extract all unique properties from clipped features and their units
    all_properties = set()
    for feature in clipped_features:
        for prop in feature['properties'].keys():
            all_properties.add(prop)

    means = {}
    # Calculate the mean values for each property and update the properties of the clipped features
    for prop in all_properties:
        vectors = [feature['properties'][prop] for feature in clipped_features if prop in feature['properties']]
        if vectors:
            if prop in ['c']:
                c_min = np.array(vectors).min()
                k_min_pos = vectors.index(c_min)
                c_max = np.array(vectors).max()
                k_max_pos = vectors.index(c_max)
            elif prop in ['k']:
                k_list = np.array(vectors)
            else:
                mean_value = await calculate_mean_of_vectors(vectors)
                mean_value = mean_value.tolist()
                means[prop] = mean_value
        else:
            means[prop] = None

    if is_wind:
        k_min = k_list[k_min_pos].item()
        k_max = k_list[k_max_pos].item()
        # Create the final JSON object with the calculated means
        return {'type': 'ResponseData', 'properties': {
                        'name': geojson_sent_by_user.properties.name,
                        'regionValues': means,
                        'pixels': num_pixels,
                        'C_max': c_max,
                        'K_max': k_max,
                        'C_min': c_min,
                        'K_min': k_min,
                        stat_label: user_statistic}
        }
    else:
        return {'type': 'ResponseData', 'properties': {
                'name': geojson_sent_by_user.properties.name,
                'regionValues': means,
                'pixels': num_pixels,
                stat_label: user_statistic}
        }

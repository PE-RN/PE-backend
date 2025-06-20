from shapely.geometry import shape, mapping, LineString, Polygon, MultiLineString, MultiPolygon, MultiLineString
from shapely.ops import unary_union, transform
from pyproj import CRS, Transformer
import numpy as np
import pyproj
from shapely.ops import transform
from functools import partial
import math


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
    # Convert GeoJSON features to Shapely geometries from the database features
    geometries1 = [(shape(feature['geometry']), feature['properties']) for feature in geojson_loaded_from_db['features']]
    
    # Process user geometry as a FeatureCollection or a single Feature
    user_geometries = []
    properties_list = []
    if geojson_sent_by_user.type == "FeatureCollection":
        for feature in geojson_sent_by_user.features:
            user_geometries.append(shape(feature['geometry']))
            properties_list.append(feature['properties'])
    else:
        user_geometries = [shape(geojson_sent_by_user.geometry.dict())]
        properties_list = [geojson_sent_by_user.properties.dict()]

    flattened_line_geometries = []
    for geom in user_geometries:
        if isinstance(geom, LineString):
            flattened_line_geometries.append(geom)
        elif isinstance(geom, MultiLineString):
            # Unpack each LineString from the MultiLineString and add to the list
            flattened_line_geometries.extend(geom.geoms)

    # Combine geometries and determine whether they are lines or polygons
    if isinstance(user_geometries[0], Polygon) or isinstance(user_geometries[0], MultiPolygon):
        user_geometry = unary_union(user_geometries)  # Union of all polygons
        user_statistic = await area_in_km2(user_geometry)  # Calculate area
        stat_label = 'area'
    elif isinstance(user_geometries[0], LineString):
        user_geometry = MultiLineString(user_geometries)  # Combine all lines into MultiLineString
        user_statistic = user_geometry.length * 111.111  # Total length in km
        stat_label = 'length'
    else:
        user_geometry = MultiLineString(flattened_line_geometries)
        user_statistic = sum(line.length * 111.111 for line in flattened_line_geometries)  # Total length in km
        stat_label = 'length'

    # Buffer configuration based on energy type
    is_wind = energy_type.startswith('wind')
    buffer_distance = 1.5 / 111.111 if is_wind else 0.5 / 111.111
    buffered_geom = user_geometry.buffer(buffer_distance, join_style='mitre') if user_geometry else None

    # Clip database geometries using buffered user geometry and calculate means
    clipped_features = []
    num_pixels = 0
    for geometry, properties in geometries1:
        clipped_geometry = geometry.intersection(buffered_geom) if buffered_geom else geometry
        if not clipped_geometry.is_empty:
            clipped_features.append({"type": "Feature", "geometry": mapping(clipped_geometry), "properties": properties})
            num_pixels += 1

    # Extract all unique properties and compute combined means
    all_properties = set()
    for feature in clipped_features:
        all_properties.update(feature['properties'].keys())

    means = {}
    c_min, c_max, k_min, k_max = None, None, None, None
    # Precompute c and k min/max values if they exist in properties
    c_values = [feature['properties']['c'] for feature in clipped_features if 'c' in feature['properties']]
    k_values = [feature['properties']['k'] for feature in clipped_features if 'k' in feature['properties']]

    if c_values:
        c_min = np.min(c_values)
        c_max = np.max(c_values)
        k_min_pos = c_values.index(c_min)
        k_max_pos = c_values.index(c_max)

        # Check if k_values are available and if k_min_pos and k_max_pos are within bounds
        if k_values and k_min_pos < len(k_values) and k_max_pos < len(k_values):
            k_list = np.array(k_values)
            k_min = k_list[k_min_pos].item()
            k_max = k_list[k_max_pos].item()
        else:
            k_min = None
            k_max = None
    else:
        c_min = None
        c_max = None
        k_min = None
        k_max = None

    # Weibull PDF function and arrays for wind energy
    def weibull_pdf(x, c, k):
        if x < 0 or c <= 0 or k <= 0:
            return 0
        return (k / c) * ((x / c) ** (k - 1)) * math.exp(-((x / c) ** k))

    if is_wind and all(v is not None for v in [c_min, k_min, c_max, k_max]):
        x_values = [round(i * 0.1, 2) for i in range(int(c_max * 20))]
        y_values_min = [weibull_pdf(x, c_min, k_min) for x in x_values]
        y_values_max = [weibull_pdf(x, c_max, k_max) for x in x_values]
    else:
        x_values = []
        y_values_min = []
        y_values_max = []

    # Now loop over all properties and calculate mean values for other properties
    for prop in all_properties:
        vectors = [feature['properties'][prop] for feature in clipped_features if prop in feature['properties']]
        if vectors:
            if prop not in ['c', 'k']:  # 'c' and 'k' are already processed
                mean_value = await calculate_mean_of_vectors(vectors)
                means[prop] = mean_value.tolist()
        else:
            means[prop] = None


    # Prepare and return final response
    response_data = {
        'type': 'ResponseData',
        'properties': {
            'name': "Área Agregada",
            'regionValues': means,
            'pixels': num_pixels,
            stat_label: user_statistic
        }
    }

    if is_wind:
        response_data['properties'].update({
            'C_max': c_max,
            'K_max': k_max,
            'C_min': c_min,
            'K_min': k_min,
            'weibull_x': x_values,
            'weibull_y_min': y_values_min,
            'weibull_y_max': y_values_max
        })

    return response_data

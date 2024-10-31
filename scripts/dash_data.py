from shapely.geometry import shape, mapping, LineString, Point, MultiLineString, MultiPoint, MultiPolygon, MultiLineString
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

    # Combine geometries and determine whether they are lines or polygons
    if all(geom.geom_type == 'Polygon' for geom in user_geometries):
        user_geometry = unary_union(user_geometries)  # Union of all polygons
        user_statistic = await area_in_km2(user_geometry)  # Calculate area
        stat_label = 'area'
    elif all(geom.geom_type == 'LineString' for geom in user_geometries):
        user_geometry = MultiLineString(user_geometries)  # Combine all lines into MultiLineString
        user_statistic = sum(line.length * 111.11 for line in user_geometries)  # Total length in km
        stat_label = 'length'
    else:
        # Handle mixed cases (combine polygons and lines if necessary)
        polygon_geometries = [geom for geom in user_geometries if geom.geom_type == 'Polygon']
        line_geometries = [geom for geom in user_geometries if geom.geom_type == 'LineString']
        user_geometry = unary_union(polygon_geometries) if polygon_geometries else None
        user_statistic = sum(line.length * 111.11 for line in line_geometries)  # Total length for lines
        stat_label = 'area'  # Indicates a combined area and length calculation

    # Buffer configuration based on energy type
    is_wind = energy_type.startswith('wind')
    buffer_distance = 1.5 / 111.11 if is_wind else 0.5 / 111.11
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
    for prop in all_properties:
        vectors = [feature['properties'][prop] for feature in clipped_features if prop in feature['properties']]
        if vectors:
            if prop == 'c':
                c_min = np.min(vectors)
                c_max = np.max(vectors)
                k_min_pos = vectors.index(c_min)
                k_max_pos = vectors.index(c_max)
            elif prop == 'k':
                k_list = np.array(vectors)
                k_min = k_list[k_min_pos].item()
                k_max = k_list[k_max_pos].item()
            else:
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
            'K_min': k_min
        })
    print(response_data)
    return response_data

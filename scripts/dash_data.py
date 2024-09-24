from shapely.geometry import shape, mapping
from shapely.ops import transform
import numpy as np
from pyproj import CRS, Transformer
from shapely.ops import transform


async def calculate_mean_of_vectors(vectors):

    array = np.array(vectors)
    return np.round(np.mean(array, axis=0), 2)


async def calculate_mean_of_2d_vectors(vectors):

    array = np.array(vectors)
    return np.round(np.mean(array, axis=0), 2).tolist()


async def calculate_sum_data(vectors):

    array = np.array(vectors)
    return np.round(np.sum(array, axis=0), 2)


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


async def mean_stats(geojson_loaded_from_db, geojson_sent_by_user):

    # Convert GeoJSON features to Shapely geometries
    geometries1 = [(shape(feature['geometry']), feature['properties']) for feature in geojson_loaded_from_db['features']]
    geometries2 = shape(geojson_sent_by_user.geometry.dict())

    num_pixels = len(geojson_sent_by_user.geometry.coordinates[0])
    user_area_km2 = await area_in_km2(geometries2)

    # Clip geometries from the first GeoJSON with the union of the second GeoJSON
    clipped_features = []
    num_pixels = 0
    for geometry, properties in geometries1:
        clipped_geometry = geometry.intersection(geometries2)
        if not clipped_geometry.is_empty:
            clipped_features.append({
                "type": "Feature",
                "geometry": mapping(clipped_geometry),
                "properties": properties
            })
            num_pixels += 1

    # Extract all unique properties from clipped features and their units
    property_units = {}
    all_properties = set()
    for feature in clipped_features:
        for prop, value in feature['properties'].items():
            all_properties.add(prop)
            property_units[prop] = value.get('unit', '')

    means = {}
    # Calculate the mean values for each property and update the properties of the clipped features
    for prop in all_properties:
        vectors = [feature['properties'][prop]['values'] for feature in clipped_features if prop in feature['properties']]
        if vectors:
            if prop == 'total_energy_production':
                mean_value = await calculate_sum_data(vectors)
                mean_value = mean_value.tolist()
            elif prop in ['speed_probability', 'power_density_probability']:
                mean_value = await calculate_mean_of_2d_vectors(vectors)
            else:
                mean_value = await calculate_mean_of_vectors(vectors)
                mean_value = mean_value.tolist()
            means[prop] = {
                "value": mean_value,
                "unit": property_units[prop]
            }
        else:
            means[prop] = {
                "value": None,
                "unit": property_units[prop]
            }

    # Create the final JSON object with the calculated means
    return {'type': 'ResponseData', 'properties': {
                    'name': geojson_sent_by_user.properties.name,
                    'regionValues': means,
                    'pixels': num_pixels,
                    'area': user_area_km2}
            }

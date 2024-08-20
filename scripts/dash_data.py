from shapely.geometry import shape, mapping
import numpy as np


async def calculate_mean_of_vectors(vectors):

    array = np.array(vectors)
    return np.mean(array, axis=0).round(2).astype(np.float16)


async def calculate_mean_of_2d_vectors(vectors):

    array = np.array(vectors)
    return np.round(np.mean(array, axis=0), 2).tolist()


async def mean_stats(geojson_loaded_from_db, geojson_sent_by_user):

    # Convert GeoJSON features to Shapely geometries
    geometries1 = [(shape(feature['geometry']), feature['properties']) for feature in geojson_loaded_from_db['features']]
    geometries2 = shape(geojson_sent_by_user.geometry.dict())

    num_pixels = len(geojson_sent_by_user.geometry.coordinates[0])

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
            if prop in ['speed_probability', 'power_density_probability']:
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
                    'pixels': num_pixels}
            }

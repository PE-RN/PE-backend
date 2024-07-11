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

    # Clip geometries from the first GeoJSON with the union of the second GeoJSON
    clipped_features = []
    for geometry, properties in geometries1:
        clipped_geometry = geometry.intersection(geometries2)
        if not clipped_geometry.is_empty:
            clipped_features.append({
                "type": "Feature",
                "geometry": mapping(clipped_geometry),
                "properties": properties
            })

    # Extract and calculate mean for each property
    properties_to_average = [
        'hourly_mean_speed',
        'hourly_mean_direction',
        'monthly_mean_speed',
        'monthly_mean_direction',
        'speed_probability',
        'power_density_probability',
        'direction_probability',
        'mean_yearly_speed',
        'mean_speed',
        'mean_power_density'
    ]

    # Define units for each property
    property_units = {
        'hourly_mean_speed': 'm/s',
        'hourly_mean_direction': 'degrees',
        'monthly_mean_speed': 'm/s',
        'monthly_mean_direction': 'degrees',
        'speed_probability': '%',
        'power_density_probability': '%',
        'direction_probability': '%',
        'mean_yearly_speed': 'm/s',
        'mean_speed': 'm/s',
        'mean_power_density': 'W/m²'
    }

    means = {}
    # Calculate the mean values for each property and update the properties of the clipped features
    for prop in properties_to_average:
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
                    'regionValues': means}
            }

from schemas.geojson import GeoJSON


async def hydrogen_costs(geoJSON: GeoJSON):
    return {'cost_per_year': 1000}

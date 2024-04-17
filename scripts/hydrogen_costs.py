from models.geojson import GeoJSONModel


async def hydrogen_costs(geoJSON: GeoJSONModel):
    return {'cost_per_year': 1000}

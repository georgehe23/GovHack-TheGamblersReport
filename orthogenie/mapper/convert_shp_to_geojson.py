import geopandas as gpd

# Path to the shapefile
shp_path = "vic_lga_boundaries.geojson.shp"
geojson_path = "vic_lga_boundaries.geojson"

gdf = gpd.read_file(shp_path)
gdf.to_file(geojson_path, driver="GeoJSON")
print(f"Converted to {geojson_path}")

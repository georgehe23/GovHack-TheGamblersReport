import geopandas as gpd

# Path to the shapefile
shp_path = "Order_KI6BGO/ll_gda2020/esrishape/whole_of_dataset/victoria/VMADMIN/AD_LGA_AREA_POLYGON.shp"
geojson_path = "datasets/vic_lga_boundaries.geojson"

gdf = gpd.read_file(shp_path)
gdf.to_file(geojson_path, driver="GeoJSON")
print(f"Converted to {geojson_path}")

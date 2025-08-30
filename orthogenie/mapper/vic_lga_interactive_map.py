import pandas as pd
import folium
import json

# Load LGA boundaries GeoJSON
geojson_path = "datasets/vic_lga_boundaries.geojson"
with open(geojson_path, "r") as f:
    lga_geojson = json.load(f)

# Load expenditure per LGA (from previous script)
data_path = "datasets/yearly_density_statistical_release_nov_24_csv/Detail_Data_2023-24.csv"
df = pd.read_csv(data_path)


lga_2023_24_columns = [
    'LGA Name', 'LGA', 'Region', 'TOTAL Net Expenditure ($)',
    'SEIFA DIS Score', 'SEIFADIS Rank State', 'SEIFA DIS RANK COUNTRY',
    'SEIFA DIS RANK METRO', 'SEIFA ADVDIS Score', 'SEIFA ADVDIS Rank State',
    'SEIFA ADVDIS RANK COUNTRY', 'SEIFA ADVDIS RANK METRO',
    'Adult Population 2022', 'Adults per Venue 2022',
    'EGMs per 1,000 Adults 2022', 'EXP per Adult 2022',
    'Unemployed Workforce as at June 2022', 'as at June 2022',
    'Unemployment rate as at June 2022'
]
df.columns = lga_2023_24_columns
lga_col = 'LGA Name'
exp_col = 'Expenditure 01 Jul 24 - 30 Jun 25'
egm_col = 'Average EGM Numbers in June 2025'

# Remove rows with missing or zero EGM
df = df[(df[egm_col].notnull()) & (df[egm_col].astype(float) > 0)]
df[exp_col] = pd.to_numeric(df[exp_col], errors='coerce')
df[egm_col] = pd.to_numeric(df[egm_col], errors='coerce')


# Standardize LGA names to match GeoJSON 'NAME' property
def clean_lga_name(name):
    name = name.upper().replace('CITY OF ', '').replace('SHIRE OF ', '').replace('RURAL CITY OF ', '').replace('BOROUGH OF ', '').replace(' (CITY)', '').replace(' (SHIRE)', '').replace(' (RURAL CITY)', '').replace(' (BOROUGH)', '').strip()
    # Remove trailing/leading whitespace and extra spaces
    name = ' '.join(name.split())
    return name

df['LGA_NAME_CLEAN'] = df[lga_col].apply(clean_lga_name)

# Group by cleaned LGA name
lga_group = df.groupby('LGA_NAME_CLEAN').agg({exp_col: 'sum', egm_col: 'sum'})
lga_group['Expenditure per EGM'] = lga_group[exp_col] / lga_group[egm_col]
lga_group = lga_group.reset_index()

# Create folium map centered on Victoria
vic_center = [-37.4713, 144.7852]
m = folium.Map(location=vic_center, zoom_start=6, tiles='cartodbpositron')

# Add choropleth for expenditure per EGM
folium.Choropleth(
    geo_data=lga_geojson,
    name='choropleth',
    data=lga_group,
    columns=['LGA_NAME_CLEAN', 'Expenditure per EGM'],
    key_on='feature.properties.NAME',
    fill_color='YlOrRd',
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name='Expenditure per EGM ($)',
    nan_fill_color='white',
    highlight=True
).add_to(m)

# Add tooltip for LGA name
folium.GeoJson(
    lga_geojson,
    name="LGA Names",
    style_function=lambda x: {"fillOpacity": 0, "color": "#00000000", "weight": 0},
    tooltip=folium.GeoJsonTooltip(fields=["NAME"], aliases=["LGA Name:"])
).add_to(m)

folium.LayerControl().add_to(m)

# Save to HTML
m.save("datasets/vic_lga_expenditure_per_egm_map.html")
print("Interactive map saved to datasets/vic_lga_expenditure_per_egm_map.html")

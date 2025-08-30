import pandas as pd
import folium
import json
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import tempfile
import shutil
import os

app = FastAPI()

# Load LGA boundaries GeoJSON (assume relative to this script)
geojson_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../vic_lga_boundaries.geojson"))
with open(geojson_path, "r") as f:
    lga_geojson = json.load(f)

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

# Standardize LGA names to match GeoJSON 'NAME' property
def clean_lga_name(name):
    name = name.upper().replace('CITY OF ', '').replace('SHIRE OF ', '').replace('RURAL CITY OF ', '').replace('BOROUGH OF ', '').replace(' (CITY)', '').replace(' (SHIRE)', '').replace(' (RURAL CITY)', '').replace(' (BOROUGH)', '').strip()
    name = ' '.join(name.split())
    return name

@app.post("/upload")
def upload_csv(file: UploadFile = File(...)):
    # Save uploaded file to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    
    # Read CSV
    df = pd.read_csv(tmp_path)
    df.columns = lga_2023_24_columns

    # Column assignments for overlays
    lga_col = 'LGA Name'
    exp_col = 'TOTAL Net Expenditure ($)'
    egm_col = 'EGMs per 1,000 Adults 2022'
    unemp_col = 'Unemployment rate as at June 2022'
    adults_col = 'Adult Population 2022'

    # Convert columns to numeric
    df[exp_col] = pd.to_numeric(df[exp_col], errors='coerce')
    df[egm_col] = pd.to_numeric(df[egm_col], errors='coerce')
    df[unemp_col] = pd.to_numeric(df[unemp_col], errors='coerce')
    df[adults_col] = pd.to_numeric(df[adults_col], errors='coerce')
    df = df[(df[adults_col].notnull()) & (df[adults_col] > 0)]

    df['LGA_NAME_CLEAN'] = df[lga_col].apply(clean_lga_name)

    lga_group = df.groupby('LGA_NAME_CLEAN').agg({
        exp_col: 'sum',
        egm_col: 'mean',
        unemp_col: 'mean',
        adults_col: 'sum'
    })
    lga_group['Expenditure per EGM'] = lga_group[exp_col] / (lga_group[adults_col] * lga_group[egm_col] / 1000)
    lga_group['Unemployment Rate'] = lga_group[unemp_col]
    lga_group['EGMs per 1000 Adults'] = lga_group[egm_col]
    lga_group = lga_group.reset_index()

    vic_center = [-37.4713, 144.7852]
    m = folium.Map(location=vic_center, zoom_start=6, tiles='cartodbpositron')

    folium.GeoJson(
        lga_geojson,
        name="LGA Names",
        style_function=lambda x: {"fillOpacity": 0, "color": "#00000000", "weight": 0},
        tooltip=folium.GeoJsonTooltip(fields=["NAME"], aliases=["LGA Name:"])
    ).add_to(m)

    folium.Choropleth(
        geo_data=lga_geojson,
        name='Expenditure per EGM',
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

    folium.Choropleth(
        geo_data=lga_geojson,
        name='Unemployment Rate',
        data=lga_group,
        columns=['LGA_NAME_CLEAN', 'Unemployment Rate'],
        key_on='feature.properties.NAME',
        fill_color='PuBu',
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name='Unemployment Rate (%)',
        nan_fill_color='white',
        highlight=True
    ).add_to(m)

    folium.Choropleth(
        geo_data=lga_geojson,
        name='EGMs per 1000 Adults',
        data=lga_group,
        columns=['LGA_NAME_CLEAN', 'EGMs per 1000 Adults'],
        key_on='feature.properties.NAME',
        fill_color='BuGn',
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name='EGMs per 1000 Adults',
        nan_fill_color='white',
        highlight=True
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # Save to a temp HTML file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as tmp_html:
        m.save(tmp_html.name)
        html_path = tmp_html.name

    # Clean up uploaded CSV
    os.remove(tmp_path)

    return FileResponse(html_path, filename="vic_lga_expenditure_per_egm_map.html", media_type="text/html")

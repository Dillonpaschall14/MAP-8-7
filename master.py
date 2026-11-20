import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import Search

# =========================================================
# FILE NAMES
# =========================================================
CSV_FILE = "Zip Code 4-7-26.csv"
SHAPEFILE = "tl_2020_us_zcta520.shp"
DIVIDER_FILE = "territory_divider_line.geojson"
OUTPUT_HTML = "index.html"

# =========================================================
# LOAD CSV
# =========================================================
df = pd.read_csv(CSV_FILE)
df.columns = df.columns.str.strip()

# Rename first column to ZIP Code
df.rename(columns={df.columns[0]: "ZIP Code"}, inplace=True)
df["ZIP Code"] = df["ZIP Code"].astype(str).str.strip().str.zfill(5)

# Clean numeric fields
df["Average Property Value"] = pd.to_numeric(df["Average Property Value"], errors="coerce")
df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

# Drop bad rows
df = df[df["Average Property Value"].notnull()]
df = df[df["Latitude"].notnull() & df["Longitude"].notnull()]

# =========================================================
# LOAD SHAPEFILE AND DIVIDER
# =========================================================
zips = gpd.read_file(SHAPEFILE, engine="pyogrio")
divider = gpd.read_file(DIVIDER_FILE, engine="pyogrio")

zips["ZCTA5CE20"] = zips["ZCTA5CE20"].astype(str).str.strip().str.zfill(5)

# Only keep ZIPs from your spreadsheet
zips = zips[zips["ZCTA5CE20"].isin(df["ZIP Code"])]

# =========================================================
# MERGE CSV TO SHAPEFILE
# =========================================================
merged = zips.merge(df, left_on="ZCTA5CE20", right_on="ZIP Code", how="inner")

# =========================================================
# PROJECT FOR CENTROID / SPATIAL CALCS
# =========================================================
merged_proj = merged.to_crs(epsg=3857)
divider_proj = divider.to_crs(epsg=3857)

divider_line = divider_proj.geometry.iloc[0]
merged_proj["centroid_geom"] = merged_proj.geometry.centroid

# Territory assignment using projected centroid vs projected divider line
merged_proj["side"] = merged_proj["centroid_geom"].apply(
    lambda pt: pt.y > divider_line.interpolate(divider_line.project(pt)).y
)

merged_proj["Territory"] = merged_proj["side"].map({
    True: "PM1 - Landry Paschall",
    False: "PM2 - Michael Paschall"
})

# =========================================================
# MANUAL ZIP OVERRIDES
# =========================================================
landry_override_zips = {
    "75042", "75423", "75041", "75043", "75088",
    "75089", "75048", "75040", "75087", "75189",
    "75243", "75032", "75044", "76188",
    "76020", "76179"
}

michael_override_zips = {
    "75702", "75701", "75709"
}

merged_proj.loc[merged_proj["ZIP Code"].isin(landry_override_zips), "Territory"] = "PM1 - Landry Paschall"
merged_proj.loc[merged_proj["ZIP Code"].isin(michael_override_zips), "Territory"] = "PM2 - Michael Paschall"

# =========================================================
# CONVERT CENTROIDS BACK TO LAT/LON FOR LABELS
# =========================================================
centroids_geo = gpd.GeoSeries(merged_proj["centroid_geom"], crs=merged_proj.crs).to_crs(epsg=4326)
merged_proj["centroid_lat"] = centroids_geo.y.values
merged_proj["centroid_lon"] = centroids_geo.x.values

# Convert polygons back to WGS84 for folium display
merged_final = merged_proj.to_crs(epsg=4326)

merged_final["centroid_lat"] = merged_proj["centroid_lat"].values
merged_final["centroid_lon"] = merged_proj["centroid_lon"].values
merged_final["Territory"] = merged_proj["Territory"].values

# =========================================================
# STYLE SETTINGS
# =========================================================
def get_fill_color(row):
    value = float(row["Average Property Value"])
    territory = row["Territory"]

    if territory == "PM1 - Landry Paschall":
        if value < 200000:
            return "#e5f5e0"
        elif value < 350000:
            return "#a1d99b"
        elif value < 500000:
            return "#74c476"
        elif value < 700000:
            return "#31a354"
        else:
            return "#006d2c"
    else:
        if value < 200000:
            return "#deebf7"
        elif value < 350000:
            return "#9ecae1"
        elif value < 500000:
            return "#6baed6"
        elif value < 700000:
            return "#3182bd"
        else:
            return "#08519c"

border_colors = {
    "PM1 - Landry Paschall": "#2ca02c",
    "PM2 - Michael Paschall": "#1f77b4"
}

merged_final["fillColor"] = merged_final.apply(get_fill_color, axis=1)
merged_final["Avg Value"] = merged_final["Average Property Value"].apply(lambda v: f"${int(v):,}")
merged_final["borderColor"] = merged_final["Territory"].map(border_colors)

if "centroid_geom" in merged_final.columns:
    merged_clean = merged_final.drop(columns=["centroid_geom"])
else:
    merged_clean = merged_final.copy()

# =========================================================
# CREATE MAP
# =========================================================
m = folium.Map(location=[32.7767, -96.7970], zoom_start=9, tiles=None)

# Standard OpenStreetMap background; browser defaults preserve referrer and caching.
folium.TileLayer(
    tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    name="OpenStreetMap",
    max_zoom=20,
    max_native_zoom=19
).add_to(m)

# =========================================================
# ADD ZIP POLYGONS
# =========================================================
geojson_layer = folium.GeoJson(
    merged_clean,
    name="ZIPs",
    style_function=lambda feature: {
        "fillColor": feature["properties"]["fillColor"],
        "color": feature["properties"]["borderColor"],
        "weight": 2,
        "fillOpacity": 0.5
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["ZIP Code", "Avg Value", "Territory"],
        aliases=["ZIP Code:", "Avg Value:", "Territory:"],
        sticky=True
    )
)
geojson_layer.add_to(m)

# =========================================================
# SEARCH BAR
# =========================================================
Search(
    layer=geojson_layer,
    geom_type="Polygon",
    search_label="ZIP Code",
    placeholder="Search ZIP Code",
    collapsed=False
).add_to(m)

# =========================================================
# CITY LABELS
# =========================================================
for _, row in merged_clean.iterrows():
    city = str(row["City"]).strip() if pd.notnull(row["City"]) else ""
    lat = row["centroid_lat"]
    lon = row["centroid_lon"]

    if city:
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(html=f"""
                <div style="
                    font-size:10px;
                    font-weight:bold;
                    color:#222;
                    text-align:center;
                    text-shadow: 0 0 2px #fff;
                    white-space: nowrap;
                ">
                    {city}
                </div>
            """)
        ).add_to(m)

# =========================================================
# PCG WAREHOUSE
# Address pin from PCG's published Google Maps address link.
# =========================================================
m.get_root().header.add_child(folium.Element('''
<style>
.pcg-warehouse-label {font-weight: 700; font-size: 12px; color: #991b1b; border: 1px solid #b91c1c; background: #fff; padding: 5px 8px;}
</style>
'''))
folium.Marker(
    location=[32.9011982, -96.576295],
    title="PCG Warehouse",
    alt="PCG Warehouse",
    z_index_offset=1000,
    icon=folium.Icon(color="red", icon="home", prefix="fa"),
    tooltip=folium.Tooltip("PCG Warehouse", permanent=True, direction="right",
                          offset=(12, -26), class_name="pcg-warehouse-label"),
    popup=folium.Popup("<strong>PCG Warehouse</strong><br>2802 Singleton St<br>Rowlett, TX 75088")
).add_to(m)

# =========================================================
# LEGEND
# =========================================================
legend_html = """
<div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    width: 230px;
    border: 2px solid #ccc;
    background-color: white;
    z-index: 9999;
    font-size: 12px;
    padding: 10px;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    line-height: 1.4;
">
<b>Shading by PM & Property Value</b><br><br>

<b style="color:#2ca02c;">Landry Paschall (Green)</b><br>
<div style="margin-left:10px;">
  <i style="background:#e5f5e0;width:18px;height:12px;float:left;margin-right:6px;"></i>&lt; $200k<br>
  <i style="background:#a1d99b;width:18px;height:12px;float:left;margin-right:6px;"></i>$200k–349k<br>
  <i style="background:#74c476;width:18px;height:12px;float:left;margin-right:6px;"></i>$350k–499k<br>
  <i style="background:#31a354;width:18px;height:12px;float:left;margin-right:6px;"></i>$500k–699k<br>
  <i style="background:#006d2c;width:18px;height:12px;float:left;margin-right:6px;"></i>≥ $700k<br>
</div><br>

<b style="color:#1f77b4;">Michael Paschall (Blue)</b><br>
<div style="margin-left:10px;">
  <i style="background:#deebf7;width:18px;height:12px;float:left;margin-right:6px;"></i>&lt; $200k<br>
  <i style="background:#9ecae1;width:18px;height:12px;float:left;margin-right:6px;"></i>$200k–349k<br>
  <i style="background:#6baed6;width:18px;height:12px;float:left;margin-right:6px;"></i>$350k–499k<br>
  <i style="background:#3182bd;width:18px;height:12px;float:left;margin-right:6px;"></i>$500k–699k<br>
  <i style="background:#08519c;width:18px;height:12px;float:left;margin-right:6px;"></i>≥ $700k<br>
</div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# =========================================================
# LAYER CONTROL
# =========================================================
folium.LayerControl().add_to(m)

# =========================================================
# SAVE MAP
# =========================================================
m.save(OUTPUT_HTML)
print("Map saved successfully as index.html")
print("Landry manual overrides applied:", sorted(landry_override_zips))
print("Michael manual overrides applied:", sorted(michael_override_zips))
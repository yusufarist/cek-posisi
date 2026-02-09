import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import re
from shapely.geometry import shape, Point, mapping
import os

st.set_page_config(layout="wide", page_title="Boundary Checker")

@st.cache_data
def load_data():
    # Use relative paths for portability (Deployment ready)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    paths = {
        "sls": os.path.join(current_dir, "data", "5271sls.geojson"),
        "lingkungan": os.path.join(current_dir, "data", "boundaries_lingkungan.geojson"),
        "kelurahan": os.path.join(current_dir, "data", "boundaries_kelurahan.geojson")
    }
    
    data = {}
    for key, path in paths.items():
        if os.path.exists(path):
            with open(path, 'r') as f:
                data[key] = json.load(f)
        else:
            st.error(f"File not found: {path}")
            data[key] = None
            
    return data

def extract_coords(url):
    # Regex to capture @lat,lon or ?q=lat,lon
    # Example: @-8.6229077,116.0834501
    pattern = r'@(-?\d+\.\d+),(-?\d+\.\d+)'
    match = re.search(pattern, url)
    if match:
        return float(match.group(1)), float(match.group(2))
    
    # Fallback for ?q=
    pattern_q = r'q=(-?\d+\.\d+),(-?\d+\.\d+)'
    match_q = re.search(pattern_q, url)
    if match_q:
        return float(match_q.group(1)), float(match_q.group(2))
        
    return None, None

def find_containing_feature(point, geojson_data):
    if not geojson_data:
        return None
    
    for feature in geojson_data['features']:
        try:
            polygon = shape(feature['geometry'])
            if polygon.contains(point):
                return feature
        except Exception:
            continue
    return None

def create_map(center_lat, center_lon, feature, title, name_key):
    m = folium.Map(location=[center_lat, center_lon], zoom_start=18)
    
    # Add Marker for the point
    folium.Marker(
        [center_lat, center_lon],
        tooltip="Lokasi Google Maps",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)
    
    found_name = "Tidak ditemukan"
    
    if feature:
        # Add Polygon
        folium.GeoJson(
            feature,
            style_function=lambda x: {'fillColor': 'blue', 'color': 'blue', 'weight': 2, 'fillOpacity': 0.3}
        ).add_to(m)
        
        props = feature['properties']
        found_name = props.get(name_key, "Nama tidak tersedia")
        
        # Fit bounds to polygon (Zooming automatically)
        bounds = shape(feature['geometry']).bounds  # (minx, miny, maxx, maxy) -> (min_lon, min_lat, max_lon, max_lat)
        # Folium expects [[lat_min, lon_min], [lat_max, lon_max]]
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        
    st.subheader(f"{title}")
    # Copy-friendly text
    if found_name != "Tidak ditemukan":
        st.code(found_name, language="text")
    else:
        st.error(found_name)

    st_folium(m, height=400, width=None, key=f"map_{title}")

def main():
    st.title("📍 Cek Posisi SLS / Lingkungan / Kelurahan")
    st.markdown("Masukkan Link Google Maps untuk melihat posisi administratif.")
    
    url = st.text_input("Paste Link Google Maps di sini", placeholder="https://www.google.com/maps/place/...")
    
    if url:
        lat, lon = extract_coords(url)
        
        if lat is not None and lon is not None:
            col_lat, col_lon = st.columns(2)
            with col_lat:
                st.code(f"{lat}", language="text")
            with col_lon:
                st.code(f"{lon}", language="text")
            
            data = load_data()
            point = Point(lon, lat)
            
            # Find features
            feat_sls = find_containing_feature(point, data['sls'])
            feat_ling = find_containing_feature(point, data['lingkungan'])
            feat_kel = find_containing_feature(point, data['kelurahan'])
            
            # Display Columns
            col1, col2, col3 = st.columns(3)
            
            with col1:
                create_map(lat, lon, feat_sls, "SLS", "nmsls")
                
            with col2:
                create_map(lat, lon, feat_ling, "Lingkungan", "lingkungan")
                
            with col3:
                create_map(lat, lon, feat_kel, "Kelurahan", "nmdesa")
                
        else:
            st.warning("Tidak dapat mengekstrak koordinat dari Link tersebut. Pastikan format link mengandung @lat,lon")

if __name__ == "__main__":
    main()

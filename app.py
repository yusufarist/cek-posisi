import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import re
from shapely.geometry import shape, Point
import os
import pandas as pd
import requests
import io

st.set_page_config(layout="wide", page_title="Boundary Checker & Coverage Analysis")

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
            # st.error(f"File not found: {path}")
            data[key] = None
            
    return data

@st.cache_data
def load_remote_csv(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_csv(io.StringIO(response.text))
    except Exception as e:
        return None

def normalize_sls_name(name):
    """
    Normalize SLS name to match between GeoJSON and Spreadsheet.
    GeoJSON: "RT 009 LINGKUNGAN GATEP"
    Sheet: "RT 09 LINGKUNGAN PONDOK PRASI" or "RT 001 ..."
    Target format: "RT {03d} {LINGKUNGAN X}"
    """
    if not isinstance(name, str):
        return ""
    
    name = name.upper().strip()
    
    # Regex to capture RT number and Environment name
    # Matches: RT 001 LINGKUNGAN X, RT 1 LINGKUNGAN X, RT 01 LINGKUNGAN X
    match = re.search(r'RT\s+(\d+)\s+(.*)', name)
    if match:
        rt_num = int(match.group(1))
        env_name = match.group(2).strip()
        # Reconstruct with 3-digit padding
        return f"RT {rt_num:03d} {env_name}"
        
    return name

def extract_coords(url):
    # Regex to capture @lat,lon or ?q=lat,lon
    pattern = r'@(-?\d+\.\d+),(-?\d+\.\d+)'
    match = re.search(pattern, url)
    if match:
        return float(match.group(1)), float(match.group(2))
    
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

def create_single_map(center_lat, center_lon, feature, title, name_key):
    m = folium.Map(location=[center_lat, center_lon], zoom_start=18)
    
    folium.Marker(
        [center_lat, center_lon],
        tooltip="Lokasi Google Maps",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)
    
    found_name = "Tidak ditemukan"
    
    if feature:
        folium.GeoJson(
            feature,
            style_function=lambda x: {'fillColor': 'blue', 'color': 'blue', 'weight': 2, 'fillOpacity': 0.3}
        ).add_to(m)
        
        props = feature['properties']
        found_name = props.get(name_key, "Nama tidak tersedia")
        
        bounds = shape(feature['geometry']).bounds
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        
    st.subheader(f"{title}")
    if found_name != "Tidak ditemukan":
        st.code(found_name, language="text")
    else:
        st.error(found_name)

    st_folium(m, height=400, width=None, key=f"map_{title}")

def create_coverage_map(geojson_data, covered_names, name_key, title):
    if not geojson_data:
        st.error("GeoJSON data not available.")
        return

    # Calculate centroid for initial map view (Kota Mataram)
    center_lat, center_lon = -8.5833, 116.1167 
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    # Prepare style function
    def style_function(feature):
        name = normalize_sls_name(feature['properties'].get(name_key, ""))
        is_covered = name in covered_names
        
        return {
            'fillColor': '#00FF00' if is_covered else '#FF0000', # Green if covered, Red if not
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.6 if is_covered else 0.4
        }
        
    # Add Legend (High Contrast)
    legend_html = '''
     <div style="position: fixed; 
     bottom: 50px; left: 50px; width: 220px; height: 120px; 
     border:3px solid black; z-index:9999; font-size:16px;
     background-color:white; opacity: 1.0; padding: 10px; box-shadow: 5px 5px 10px rgba(0,0,0,0.5); color: black;">
     <b style="font-size:18px; text-decoration: underline;">LEGENDA</b><br>
     <div style="margin-top:10px;">
     <div style="display:flex; align-items:center; margin-bottom:5px;">
         <div style="background:#00FF00;width:20px;height:20px;border:2px solid black;margin-right:10px;"></div>
         <b>Sudah Disisir</b>
     </div>
     <div style="display:flex; align-items:center;">
         <div style="background:#FF0000;width:20px;height:20px;border:2px solid black;margin-right:10px;"></div>
         <b>Belum Disisir</b>
     </div>
     </div>
     </div>
     '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # Add GeoJSON
    folium.GeoJson(
        geojson_data,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(fields=[name_key], aliases=['Nama:'])
    ).add_to(m)
    
    st_folium(m, height=600, width=None, key=f"cov_map_{title}")

def main():
    st.title("🗺️ MatchaPro Analysis Dashboard")
    
    tabs = st.tabs(["📍 Cek Posisi (Single)", "📊 Analisis Cakupan (Coverage)"])
    
    data = load_data()

    # --- TAB 1: Single Check ---
    with tabs[0]:
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
                
                point = Point(lon, lat)
                
                feat_sls = find_containing_feature(point, data['sls'])
                feat_ling = find_containing_feature(point, data['lingkungan'])
                feat_kel = find_containing_feature(point, data['kelurahan'])
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    create_single_map(lat, lon, feat_sls, "SLS", "nmsls")
                with col2:
                    create_single_map(lat, lon, feat_ling, "Lingkungan", "lingkungan")
                with col3:
                    create_single_map(lat, lon, feat_kel, "Kelurahan", "nmdesa")
            else:
                st.warning("Tidak dapat mengekstrak koordinat. Pastikan format link mengandung @lat,lon")

    # --- TAB 2: Coverage Analysis ---
    with tabs[1]:
        col_head, col_btn = st.columns([0.8, 0.2])
        with col_head:
            st.header("Analisis Sebaran Data (Gap Analysis)")
        with col_btn:
            if st.button("🔄 Refresh Data", type="secondary"):
                load_remote_csv.clear()
                try:
                    st.rerun()
                except AttributeError:
                    st.experimental_rerun()
        
        # Input Source (Hidden)
        default_csv_url = "https://docs.google.com/spreadsheets/d/1vA7kgO_3zcAcWbdlyLAnFNiFZiYrlYCNSatKK-jdhsE/export?format=csv&gid=1577962926"
        
        with st.spinner("Memuat Peta Sebaran..."):
            df_input = load_remote_csv(default_csv_url)
            
            if df_input is not None:
                # Automatic Column Selection
                sls_col = df_input.columns[0]
                if 'SLS' in df_input.columns:
                    sls_col = 'SLS'
                elif len(df_input.columns) > 1:
                    sls_col = df_input.columns[1] # Common fallback
                
                # 1. Normalize Input Names
                input_names = set(df_input[sls_col].dropna().apply(normalize_sls_name))
                
                # 2. Visualization
                create_coverage_map(data['sls'], input_names, 'nmsls', "Peta Sebaran SLS")
                
            else:
                st.error("Gagal memuat data. Silakan cek koneksi internet.")

if __name__ == "__main__":
    main()

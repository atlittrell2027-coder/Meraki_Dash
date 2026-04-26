import json
import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import meraki
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh
import altair as alt
import base64

# ⏱ APP REFRESH (Meraki Grab): Refreshes the Python backend every 60 seconds
st_autorefresh(interval=60000, limit=None, key="meraki_refresh_timer")

# Page Configuration
st.set_page_config(page_title="Network NOC Dashboard", layout="wide")

# --- TIME CALCULATION ---
pst_tz = pytz.timezone('America/Los_Angeles')
current_pst = datetime.now(pst_tz)

# --- SESSION STATE TRACKING ---
if 'dashboard_page' not in st.session_state:
    st.session_state.dashboard_page = 0
if 'current_status' not in st.session_state:
    st.session_state.current_status = None
if 'status_since' not in st.session_state:
    st.session_state.status_since = None

# Shared traffic state persistence across visitors
state_file = Path(__file__).resolve().parent / 'traffic_state.json'

def load_traffic_state():
    if state_file.exists():
        try:
            raw = json.loads(state_file.read_text())
            ts = raw.get('traffic_state_start')
            return {
                'traffic_active': bool(raw.get('traffic_active', False)),
                'traffic_state_start': datetime.fromisoformat(ts) if ts else current_pst
            }
        except Exception:
            pass
    return {'traffic_active': False, 'traffic_state_start': current_pst}


def save_traffic_state(state):
    try:
        state_file.write_text(json.dumps({
            'traffic_active': bool(state['traffic_active']),
            'traffic_state_start': state['traffic_state_start'].astimezone(pst_tz).isoformat()
        }))
    except Exception:
        pass

traffic_state = load_traffic_state()
if not state_file.exists():
    save_traffic_state(traffic_state)

# CSS: Advanced styling for Layout and Background
st.markdown("""
    <style>
    /* ⭐️ HIDE THE STREAMLIT DEFAULT TOP HEADER BAR & TOOLBAR */
    [data-testid="stHeader"], [data-testid="stToolbar"], footer { 
        display: none !important; 
        visibility: hidden !important; 
    }

    /* ⭐️ PREVENT STREAMLIT FLASHING */
    [data-testid="stAppViewContainer"], 
    [data-testid="stAppViewBlockContainer"], 
    .stApp { 
        opacity: 1 !important; 
        transition: none !important; 
        filter: none !important; 
        animation: none !important;
    }
    div[data-testid="stStatusWidget"] { 
        display: none !important; 
        visibility: hidden !important; 
    }

    html, body { overflow-y: auto !important; }

    /* ⭐️ SMOOTH BACKGROUND GRADIENT ANIMATION */
    @keyframes gradientShift {
        0% { background-image: linear-gradient(135deg, rgb(3, 53, 116), rgb(0, 30, 60), rgb(3, 53, 116)); }
        20% { background-image: linear-gradient(135deg, rgb(0, 80, 140), rgb(0, 30, 60), rgb(0, 80, 140)); }
        40% { background-image: linear-gradient(135deg, rgb(0, 120, 180), rgb(0, 30, 60), rgb(0, 120, 180)); }
        60% { background-image: linear-gradient(135deg, rgb(255, 215, 0), rgb(184, 134, 11), rgb(255, 215, 0)); }
        80% { background-image: linear-gradient(135deg, rgb(0, 80, 140), rgb(0, 30, 60), rgb(0, 80, 140)); }
        100% { background-image: linear-gradient(135deg, rgb(3, 53, 116), rgb(0, 30, 60), rgb(3, 53, 116)); }
    }

    .block-container { 
        padding-top: 0rem !important; 
        margin-top: -3rem !important; 
        padding-left: 1rem !important; 
        padding-right: 1rem !important; 
        padding-bottom: 20px !important; 
        max-width: 100% !important; 
        background-image: linear-gradient(135deg, rgb(3, 53, 116), rgb(0, 30, 60), rgb(3, 53, 116)) !important;
        background-size: 200% 200% !important;
        animation: gradientShift 3s ease infinite !important;
        background-attachment: fixed;
    }

    /* ⭐️ Metric Cards Custom Color */
    [data-testid="stMetric"] { 
        display: flex; 
        flex-direction: column; 
        align-items: flex-start; 
        text-align: left; 
        padding: 15px; 
        background: rgb(14, 17, 24); 
        border: 1px solid rgb(159, 142, 99); 
        border-radius: 8px; 
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.3);
        margin-bottom: 15px !important; 
    }

    /* ⭐️ COMBINED Chart Area Custom Color */
    div[data-testid="stHorizontalBlock"]:has([data-testid="stVegaLiteChart"]) {
        background: rgb(14, 17, 24); 
        border: 1px solid rgb(159, 142, 99); 
        border-radius: 8px; 
        padding: 20px; 
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.3);
        margin-top: 0px !important; 
        margin-bottom: 15px !important;
    }

    /* ⭐️ KILL INVISIBLE WRAPPERS TAKING UP HEIGHT */
    div.element-container:has(.top-box-wrapper),
    div.element-container:has(.bottom-box-wrapper),
    div.element-container:has(.pag-aligner) {
        height: 0px !important;
        min-height: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
    }

    /* ⭐️ TOP STATUS BOX STYLING */
    div[data-testid="stVerticalBlock"]:has(> div.element-container .top-box-wrapper) {
        background: rgb(14, 17, 24); 
        border: 1px solid rgb(159, 142, 99); 
        border-radius: 8px; 
        padding: 12px 20px !important; 
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.3);
        margin-bottom: 15px !important; 
    }
    
    div[data-testid="stVerticalBlock"]:has(> div.element-container .top-box-wrapper) [data-testid="column"] {
        padding: 0 !important;
        margin: 0 !important;
    }

    div[data-testid="stVerticalBlock"]:has(> div.element-container .top-box-wrapper) div.element-container,
    div[data-testid="stVerticalBlock"]:has(> div.element-container .top-box-wrapper) p {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }

    /* ⭐️ BOTTOM COMBINED BOX */
    div[data-testid="stVerticalBlock"]:has(> div.element-container .bottom-box-wrapper) {
        background: rgb(14, 17, 24); 
        border: 1px solid rgb(159, 142, 99); 
        border-radius: 8px; 
        padding: 20px; 
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.3);
        margin-bottom: 0px !important; 
    }
    
    .header-widget { 
        text-align: right; 
        margin-top: 10px; 
        font-size: 26px; 
    } 
    
    .weather-text { color: #29b5e8; font-weight: bold; font-size: 30px; }
    .custom-legend { text-align: right; padding-top: 5px; font-size: 15px; font-weight: bold; }
    
    /* ⭐️ TEXT ALIGNMENT */
    .op-center-row { 
        display: flex; 
        align-items: center; 
        justify-content: center; 
        width: 100%; 
        font-size: 1.5rem; 
        font-weight: bold; 
        line-height: 1 !important; 
        margin: 0 !important; 
        padding: 0 !important; 
        transform: translateY(-15px); 
        position: relative;
    }
    .top-status-center { display: flex; align-items: center; gap: 0.75rem; justify-content: center; max-width: calc(100% - 280px); white-space: nowrap; font-size: 1.7rem; }
    .top-status-right { position: absolute; right: 20px; top: 50%; transform: translateY(-50%); display: flex; align-items: center; gap: 0.45rem; font-size: 1.1rem; color: #ffeb3b; white-space: nowrap; }
    .top-status-right span { min-width: 64px; text-align: right; }
    .top-status-center span, .top-status-right span { line-height: 1.1; }
    .refresh-alert { color: #ff4b4b !important; }
    #refresh-icon { width: 20px; height: 20px; border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; animation: spin 1.2s linear infinite; }
    img.top-logo { width: 26px; height: 26px; object-fit: contain; }
    
    .status-timer { color: #21c354; font-family: monospace; }
    
    /* TRUE FLICKERING ANIMATION FOR OFFLINE STATUS */
    @keyframes blinker {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .status-offline { 
        color: #ff4b4b; 
        font-family: monospace;
        animation: blinker 2s ease-in-out infinite;
    }
    
    /* ⭐️ GLOBAL BUTTON BASE */
    div.stButton > button { 
        background-color: #ff4b4b !important; 
        color: white !important; 
        font-weight: bold !important; 
        border-radius: 5px; 
        border: none; 
        padding: 8px 0 !important; 
        margin: 0 !important;
    }

    /* ⭐️ FIX PAGINATION ARROWS */
    div.element-container:has(.pag-aligner) + div[data-testid="stHorizontalBlock"] div.stButton > button {
        height: 50px !important; 
        font-size: 24px !important; 
        border-radius: 8px !important; 
        padding: 0 !important;
        margin-top: 10px !important;
    }
    
    .centered-title { display: block; text-align: center !important; width: 100%; margin-bottom: 15px; font-size: 1.75rem; font-weight: 600; }
    .graph-title-shift { padding-left: 38px; font-size: 1.75rem; font-weight: bold; }
    [data-testid="column"] { display: flex; align-items: center; }
    </style>
""", unsafe_allow_html=True)

# Helper for Padding and Pagination
def get_paged_data(df, page_num, page_size=5):
    start = page_num * page_size
    end = start + page_size 
    paged_df = df.iloc[start:end].copy()
    while len(paged_df) < page_size:
        empty_row = {col: "—" for col in df.columns}
        paged_df = pd.concat([paged_df, pd.DataFrame([empty_row])], ignore_index=True)
    return paged_df

def color_status(val):
    val_str = str(val).upper()
    if 'ONLINE' in val_str:
        return 'background-color: #0e3d2f; color: #21c354; border: 1px solid #21c354; border-radius: 4px; font-weight: bold; padding: 2px 8px;'
    elif 'OFFLINE' in val_str:
        return 'background-color: #3d0e0e; color: #ff4b4b; border: 1px solid #ff4b4b; border-radius: 4px; font-weight: bold; padding: 2px 8px;'
    elif 'NOT CONNECTED' in val_str:
        return 'background-color: #2b2b2b; color: #a0a0a0; border: 1px solid #a0a0a0; border-radius: 4px; font-weight: bold; padding: 2px 8px;'
    elif 'ALERT' in val_str:
        return 'background-color: #4d3d0e; color: #ffeb3b; border: 1px solid #ffeb3b; border-radius: 4px; font-weight: bold; padding: 2px 8px;'
    return ''

current_time_str = current_pst.strftime("%A, %B %d, %Y | %I:%M:%S %p")

try:
    try:
        with open("images/MDTV_Logo.png", "rb") as img_file:
            logo_data = base64.b64encode(img_file.read()).decode()
        logo_html = f"<img src='data:image/png;base64,{logo_data}' class='top-logo' alt='MDTV logo'/>"
    except Exception:
        logo_html = "📍"

    api_key = st.secrets["MERAKI_API_KEY"]
    dashboard = meraki.DashboardAPI(api_key, suppress_logging=True)
    org_id = dashboard.organizations.getOrganizations()[0]['id']
    network_id = dashboard.organizations.getOrganizationNetworks(org_id)[0]['id']

    # --- DIRECT API FETCH ---
    devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
    clients_list = dashboard.networks.getNetworkClients(network_id, timespan=2592000)
    try: uplink_usage = dashboard.appliance.getNetworkApplianceUplinksUsageHistory(network_id, timespan=7200, resolution=60)
    except: uplink_usage = []
    try: traffic_data = dashboard.networks.getNetworkTraffic(network_id, timespan=7200)
    except: traffic_data = []

    net_devices = [d for d in devices if d['networkId'] == network_id]
    mx_device = next((d for d in net_devices if 'MX85' in d.get('model', '').upper()), None)

    # --- TRAFFIC GATHERING FOR TIMER LOGIC ---
    graph_data = []
    if uplink_usage:
        for entry in uplink_usage:
            dl_sum = sum(((i.get('received') or 0) / 1e6) for i in entry.get('byInterface', []))
            ul_sum = sum(((i.get('sent') or 0) / 1e6) for i in entry.get('byInterface', []))
            graph_data.append({"Time": entry['startTime'], "Download (MB)": dl_sum, "Upload (MB)": ul_sum})

    # --- ZERO-START DYNAMIC TIMER LOGIC ---
    is_mx_online = False
    if graph_data:
        latest_traffic = graph_data[-1]["Download (MB)"] + graph_data[-1]["Upload (MB)"]
        is_mx_online = latest_traffic > 0
    else:
        is_mx_online = mx_device.get('status').lower() == 'online' if mx_device else False

    if st.session_state.current_status is None:
        st.session_state.current_status = is_mx_online
        st.session_state.status_since = current_pst
    elif st.session_state.current_status != is_mx_online:
        st.session_state.current_status = is_mx_online
        st.session_state.status_since = current_pst

    current_traffic_active = latest_traffic > 0 if graph_data else is_mx_online
    if traffic_state['traffic_active'] != current_traffic_active:
        traffic_state['traffic_active'] = current_traffic_active
        traffic_state['traffic_state_start'] = current_pst
        save_traffic_state(traffic_state)

    state_timestamp = traffic_state['traffic_state_start']
    elapsed = current_pst - state_timestamp
    if elapsed < timedelta(0): elapsed = timedelta(0)

    if traffic_state['traffic_active']:
        status_class, status_label, prefix = "status-timer", "SYSTEM UPTIME:", ""
    else:
        status_class, status_label, prefix = "status-offline", "SYSTEM DOWNTIME:", "-"

    days, hours_rem = divmod(elapsed.total_seconds(), 86400)
    hours, mins_rem = divmod(hours_rem, 3600)
    minutes, seconds = divmod(mins_rem, 60)
    uptime_display = f"{prefix}{int(days)}d {int(hours):02}h {int(minutes):02}m {int(seconds):02}s"

    # Apply red background during downtime
    if status_class == 'status-offline':
        st.markdown("<style>.block-container { background: linear-gradient(135deg, rgb(139, 0, 0), rgb(50, 0, 0), rgb(139, 0, 0)) !important; animation: none !important; }</style>", unsafe_allow_html=True)

    # --- TOP HEADER ---
    header_col1, header_col2 = st.columns([3, 2])
    with header_col1:
        st.title("Network Operations Center")

    with header_col2:
        try:
            w_res = requests.get("https://wttr.in/Chula+Vista?format=%c+%t+|+💧+%h", timeout=3)
            weather = w_res.content.decode('utf-8').strip().replace("+", "")
        except: weather = "🌤️ --°F | 💧 --%" 
        st.markdown(f"<div class='header-widget'><div><strong id='live-clock'>{current_time_str}</strong></div><div class='weather-text'>{weather}</div></div>", unsafe_allow_html=True)

    # ⭐️ SHORT SPACER: Reduced from 45px to 10px
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # --- ⭐️ PERFECTLY CENTERED TOP STATUS BOX ---
    with st.container():
        st.markdown("<div class='top-box-wrapper'></div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='op-center-row'><div class='top-status-center'><span>{logo_html}</span><span>MDTV Intranet Usage |</span><span class='{status_class}'>{status_label} <span id='live-timer'>{uptime_display}</span></span></div><div class='top-status-right'><div id='refresh-icon' style='display: none;'></div><span id='refresh-timer'>60s</span></div></div>",
            unsafe_allow_html=True,
        )

    # --- METRICS GATHERING ---
    top_apps = pd.DataFrame(columns=['application', 'Usage (MB)'])
    apps_error = False
    try:
        if traffic_data:
            app_df = pd.DataFrame(traffic_data)
            app_df['Usage (MB)'] = (app_df['sent'].fillna(0) + app_df['recv'].fillna(0)) / 1048576
            top_apps = app_df.groupby('application')['Usage (MB)'].sum().reset_index().sort_values(by='Usage (MB)', ascending=False).head(5)
    except: apps_error = True

    if len(graph_data) >= 2:
        latest, previous = graph_data[-1], graph_data[-2]
        delta_dl, delta_ul = latest['Download (MB)'] - previous['Download (MB)'], latest['Upload (MB)'] - previous['Upload (MB)']
        delta_total = (latest['Download (MB)'] + latest['Upload (MB)']) - (previous['Download (MB)'] + previous['Upload (MB)'])
    else: 
        latest = graph_data[-1] if graph_data else {"Download (MB)":0, "Upload (MB)":0}
        delta_dl = delta_ul = delta_total = 0

    def get_delta_color(val): return "off" if round(val, 2) == 0.00 else "normal"

    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 1])
    online_count = sum(1 for d in net_devices if d['status'].lower() == 'online')
    col1.metric("Infrastructure Status", "🟢 ONLINE" if is_mx_online else "🔴 OFFLINE", f"{online_count}/{len(net_devices)} Connected")
    active_clients = sum(1 for c in clients_list if str(c.get('status', '')).lower() == 'online')
    col2.metric("Active Client Devices", f"{active_clients}", "Connected")
    col3.metric("Network Health Score", "100%", "Optimal")
    col4.metric("WAN Total (Live)", f"{latest['Download (MB)'] + latest['Upload (MB)']:.2f} MB", delta=f"{delta_total:.2f} MB", delta_color=get_delta_color(delta_total))
    col5.metric("WAN Download (Live)", f"{latest['Download (MB)']:.2f} MB", delta=f"{delta_dl:.2f} MB", delta_color=get_delta_color(delta_dl))
    col6.metric("WAN Upload (Live)", f"{latest['Upload (MB)']:.2f} MB", delta=f"{delta_ul:.2f} MB", delta_color=get_delta_color(delta_ul))

    # --- GRAPH AREA ---
    chart_col, app_col = st.columns([3.4, 0.8])
    
    with chart_col:
        gh_left, gh_right = st.columns([2, 1])
        with gh_left: st.markdown("<div class='graph-title-shift'>📈 WAN Bandwidth History (Last 2 Hours)</div>", unsafe_allow_html=True)
        with gh_right: st.markdown("<div class='custom-legend'><span style='color: #29b5e8;'>● Download (MB)</span> &nbsp;&nbsp;&nbsp; <span style='color: #ff4b4b;'>● Upload (MB)</span></div>", unsafe_allow_html=True)
            
        df_graph = pd.DataFrame(graph_data)
        if not df_graph.empty:
            df_graph['Time'] = pd.to_datetime(df_graph['Time']).dt.tz_convert('America/Los_Angeles')
            df_graph['Tooltip_Time'] = df_graph['Time'].dt.strftime('%A, %I:%M %p')
            df_melted = df_graph.melt(id_vars=['Time'], value_vars=['Download (MB)', 'Upload (MB)'], var_name='Type', value_name='MB')
            hover_selection = alt.selection_point(fields=['Time'], nearest=True, on='mouseover', empty=False)

            chart = alt.Chart(df_melted).encode(
                x=alt.X('Time:T', title="Time ->", axis=alt.Axis(titleFontSize=24, titleAnchor="middle", titlePadding=10)),
                y=alt.Y('MB:Q', title="MegaBytes ->", stack=None, axis=alt.Axis(titleFontSize=24, titleAnchor="middle", titleAngle=-90, titlePadding=20)),
                color=alt.Color('Type:N', scale=alt.Scale(domain=['Download (MB)', 'Upload (MB)'], range=["#29b5e8", "#ff4b4b"]), legend=None),
                tooltip=alt.value(None)
            ).mark_area(opacity=0.7)

            selectors = alt.Chart(df_graph).mark_rule(color='transparent').encode(x='Time:T', tooltip=[alt.Tooltip('Tooltip_Time:N', title='TIME'), alt.Tooltip('Download (MB):Q', format='.2f'), alt.Tooltip('Upload (MB):Q', format='.2f')]).add_params(hover_selection)
            rules = alt.Chart(df_graph).mark_rule(color='white', strokeWidth=1).encode(x='Time:T').transform_filter(hover_selection)
            points = alt.Chart(df_melted).mark_circle().encode(x='Time:T', y='MB:Q', color='Type:N', opacity=alt.condition(hover_selection, alt.value(1), alt.value(0))).transform_filter(hover_selection)

            st.altair_chart(alt.layer(chart, selectors, rules, points).properties(height=350), width="stretch")

    with app_col:
        st.markdown("<div style='text-align: center; font-size: 1.5rem; font-weight: bold; margin-bottom: 10px;'>📊 Top 5 Applications</div>", unsafe_allow_html=True)
        if apps_error: st.warning("⚠️ Enable 'Detailed Traffic Analysis' in Meraki Dashboard.")
        elif not top_apps.empty:
            app_chart = alt.Chart(top_apps).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X('Usage (MB):Q', title=None, axis=None),
                y=alt.Y('application:N', title=None, sort='-x', axis=alt.Axis(labelFontSize=14, labelColor='white')),
                color=alt.Color('application:N', scale=alt.Scale(range=['#29b5e8', '#1bc98e', '#e64759', '#e4d836', '#9e54db']), legend=None),
                tooltip=['application', 'Usage (MB)']
            ).properties(height=300)
            st.altair_chart(app_chart, use_container_width=True)
        else: st.info("Gathering traffic data...")
    
    # --- HARDENED DUAL TABLES GATHERING ---
    df_infra_all = pd.DataFrame(net_devices)[['name', 'model', 'status', 'mac']]
    df_infra_all['is_online'] = df_infra_all['status'] == 'online'
    
    device_usage = {}
    for c in clients_list:
        mac = str(c.get('recentDeviceMac', '')).lower()
        if mac:
            usage_dict = c.get('usage') or {} 
            usage = usage_dict.get('sent', 0) + usage_dict.get('recv', 0)
            device_usage[mac] = device_usage.get(mac, 0) + usage

    df_infra_all['traffic_raw'] = df_infra_all['mac'].str.lower().map(device_usage).fillna(0)
    df_infra_all['Total Traffic (30d)'] = df_infra_all['traffic_raw'].apply(lambda x: f"{x / 1048576:.2f} GB")
    df_infra_all['status'] = df_infra_all['status'].str.upper().map({'ONLINE': '↑ ONLINE', 'OFFLINE': '↓ OFFLINE'}).fillna('⚠️ ALERT')
    df_infra_all['is_alert'] = df_infra_all['status'] == '⚠️ ALERT'
    df_infra_all['is_online'] = df_infra_all['status'].str.contains('ONLINE', na=False)
    df_infra_final = df_infra_all.sort_values(by=['is_alert', 'is_online', 'traffic_raw'], ascending=[False, False, False])[['name', 'model', 'status', 'Total Traffic (30d)']].rename(columns={'name':'Name', 'model':'Model', 'status':'Status'})

    df_clients_all = pd.DataFrame(clients_list)
    if not df_clients_all.empty:
        if 'switchport' not in df_clients_all.columns: df_clients_all['switchport'] = "—"
        if 'os' not in df_clients_all.columns: df_clients_all['os'] = "Unknown"
        if 'description' not in df_clients_all.columns: df_clients_all['description'] = df_clients_all.get('mac', 'Unknown')
        
        df_clients_all['Port'] = df_clients_all['switchport'].apply(lambda x: x if pd.notnull(x) and x != "" else "—")
        df_clients_all['status'] = df_clients_all['status'].str.upper().map({'ONLINE': '↑ ONLINE', 'OFFLINE': '↓ NOT CONNECTED'}).fillna('⚠️ ALERT')
        df_clients_all['is_alert'] = df_clients_all['status'] == '⚠️ ALERT'
        df_clients_all['is_online'] = df_clients_all['status'].str.contains('ONLINE', na=False)
        df_clients_final = df_clients_all.sort_values(by=['is_alert', 'is_online', 'lastSeen'], ascending=[False, False, False])[['description', 'os', 'status', 'Port']].rename(columns={'description':'Description', 'os':'OS', 'status':'Status'})
    else: df_clients_final = pd.DataFrame(columns=['Description', 'OS', 'Status', 'Port'])


    # --- ⭐️ COMBINED BOTTOM BOX (Tables + Pagination) ---
    with st.container():
        st.markdown("<div class='bottom-box-wrapper'></div>", unsafe_allow_html=True)
        
        t_l, t_r = st.columns(2)
        with t_l:
            st.markdown("<div class='centered-title'>🖧 Network Infrastructure</div>", unsafe_allow_html=True)
            st.dataframe(get_paged_data(df_infra_final, st.session_state.dashboard_page).style.map(color_status, subset=['Status']), width="stretch", hide_index=True)
        with t_r:
            st.markdown("<div class='centered-title'>💻 Recent Connected Clients</div>", unsafe_allow_html=True)
            st.dataframe(get_paged_data(df_clients_final, st.session_state.dashboard_page).style.map(color_status, subset=['Status']), width="stretch", hide_index=True)

        can_next = (st.session_state.dashboard_page + 1) * 5 < max(len(df_infra_all), len(df_clients_all))
        
        st.markdown("<div class='pag-aligner'></div>", unsafe_allow_html=True)
        
        _, f_l, _, f_r = st.columns([0.25, 1, 20, 1])
        with f_l:
            if st.button("←", key="prev_g", disabled=(st.session_state.dashboard_page == 0), use_container_width=True):
                st.session_state.dashboard_page -= 1
                st.rerun()
        with f_r:
            if st.button("→", key="next_g", disabled=not can_next, use_container_width=True):
                st.session_state.dashboard_page += 1
                st.rerun()

    # --- LIVE JAVASCRIPT TIMER INJECTION ---
    state_timestamp_ms = int(state_timestamp.timestamp() * 1000)
    is_online_js = "true" if is_mx_online else "false"
    refresh_interval_ms = 60000  # 60 seconds

    js_code = f"""
    <script>
    const parentDoc = window.parent.document;
    const stateTimestampMs = {state_timestamp_ms};
    const isOnline = {is_online_js};
    const refreshIntervalMs = {refresh_interval_ms};
    let lastRefreshTime = Date.now();

    setInterval(() => {{
        const now = new Date();
        const currentTime = now.getTime();
        
        // Calculate seconds until next refresh
        const timeSinceLastRefresh = currentTime - lastRefreshTime;
        const secondsUntilRefresh = Math.ceil((refreshIntervalMs - timeSinceLastRefresh) / 1000);
        
        // Show refresh icon for first 3 seconds of each refresh cycle
        const refreshIcon = parentDoc.getElementById('refresh-icon');
        const refreshTimer = parentDoc.getElementById('refresh-timer');
        
        if (refreshIcon && refreshTimer) {{
            if (timeSinceLastRefresh < 3000) {{
                refreshIcon.style.display = 'inline';
                refreshTimer.innerText = 'Refreshing...';
            }} else {{
                refreshIcon.style.display = 'none';
                refreshTimer.innerText = secondsUntilRefresh + 's';
            }}

            if (timeSinceLastRefresh < 3000 || secondsUntilRefresh <= 10) {{
                refreshTimer.classList.add('refresh-alert');
            }} else {{
                refreshTimer.classList.remove('refresh-alert');
            }}
        }}
        
        // Reset refresh timer every 60 seconds
        if (timeSinceLastRefresh >= refreshIntervalMs) {{
            lastRefreshTime = currentTime;
        }}
        
        const clockEl = parentDoc.getElementById('live-clock');
        if (clockEl) {{
            const formatter = new Intl.DateTimeFormat('en-US', {{ 
                timeZone: 'America/Los_Angeles', weekday: 'long', year: 'numeric', 
                month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', 
                second: '2-digit', hour12: true 
            }});
            const parts = formatter.formatToParts(now);
            const p = {{}};
            parts.forEach(part => p[part.type] = part.value);
            const timeStr = `${{p.weekday}}, ${{p.month}} ${{p.day}}, ${{p.year}} | ${{p.hour}}:${{p.minute}}:${{p.second}} ${{p.dayPeriod}}`;
            clockEl.innerText = timeStr;
        }}
        
        const timerEl = parentDoc.getElementById('live-timer');
        if (timerEl) {{
            let elapsedMs = now.getTime() - stateTimestampMs;
            if (elapsedMs < 0) elapsedMs = 0;
            let totalSecs = Math.floor(elapsedMs / 1000);
            let days = Math.floor(totalSecs / 86400);
            let hours = Math.floor((totalSecs % 86400) / 3600);
            let mins = Math.floor((totalSecs % 3600) / 60);
            let secs = totalSecs % 60;
            const pad = (num) => String(num).padStart(2, '0');
            const prefix = isOnline ? "" : "-";
            timerEl.innerText = `${{prefix}}${{days}}d ${{pad(hours)}}h ${{pad(mins)}}m ${{pad(secs)}}s`;
        }}
    }}, 1000);
    </script>
    """
    components.html(js_code, height=0, width=0)

except Exception as e: st.error(f"Critical Error: {e}")
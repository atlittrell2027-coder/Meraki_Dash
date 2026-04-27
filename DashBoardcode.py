import json
import os
from pathlib import Path
import random

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
import streamlit_extras

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

# ⭐️ STATIC CSS: Layout, Colors, and Hiding Elements
st.markdown("""
    <style>
    /* ⭐️ HIDE SCROLLBAR BUT KEEP SCROLLING */
    ::-webkit-scrollbar {
        display: none !important;
        width: 0px !important;
        background: transparent !important;
    }
    * {
        -ms-overflow-style: none !important;  /* IE and Edge */
        scrollbar-width: none !important;  /* Firefox */
    }

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

    .block-container { 
        padding-top: 0rem !important; 
        margin-top: -3rem !important; 
        padding-left: 1rem !important; 
        padding-right: 1rem !important; 
        padding-bottom: 20px !important; 
        max-width: 100% !important; 
    }

    /* ⭐️ MAIN TITLE ALIGNMENT */
    .main-title {
        font-size: 2.75rem;
        font-weight: bold;
        margin-top: 25px; /* Pushes the title down to align with the right-side clock block */
    }

    /* ⭐️ BOXES: SOLID rgb(14, 17, 24) - NO SEE THROUGH */
    [data-testid="stMetric"], 
    div[data-testid="stHorizontalBlock"]:has([data-testid="stVegaLiteChart"]),
    div[data-testid="stVerticalBlock"]:has(> div.element-container .top-box-wrapper),
    div[data-testid="stVerticalBlock"]:has(> div.element-container .bottom-box-wrapper) { 
        background: rgb(14, 17, 24) !important; 
        opacity: 1 !important;
        backdrop-filter: none !important;
        border: 1px solid rgb(159, 142, 99) !important;
        border-radius: 8px;
        box-shadow: 0px 8px 16px rgba(0, 0, 0, 0.8) !important;
    }

    /* ⭐️ Metric Cards Styled like Rack Units */
    [data-testid="stMetric"] { 
        display: flex; 
        flex-direction: column; 
        align-items: center; 
        justify-content: center; 
        text-align: center; 
        padding: 15px; 
        border-top: 3px solid rgb(159, 142, 99) !important; 
        margin-bottom: 15px !important; 
    }
    [data-testid="stMetric"] > div,
    [data-testid="stMetric"] > div > div {
        width: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
    }
    [data-testid="stMetric"] * {
        text-align: center !important;
    }
    [data-testid="stMetric"] > div > div:last-child {
        font-size: 1.08rem !important;
        line-height: 1.2 !important;
    }

    /* ⭐️ COMBINED Chart Area Custom Color */
    div[data-testid="stHorizontalBlock"]:has([data-testid="stVegaLiteChart"]) {
        padding: 20px; 
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
        padding: 12px 20px !important; 
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
        padding: 20px; 
        margin-bottom: 0px !important; 
    }
    
    /* ⭐️ HEADER WIDGET (Clock & Weather) */
    .header-widget { text-align: right; margin-top: 10px; font-size: 26px; } 
    #live-clock { font-size: 34px !important; } /* Enlarged Clock */
    .weather-text { color: #29b5e8; font-weight: bold; font-size: 30px; }
    
    .custom-legend { text-align: right; padding-top: 5px; font-size: 15px; font-weight: bold; }
    
    /* ⭐️ CENTERED CREDIT WIDGET STYLING */
    .credit-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
        margin-top: 12px;
    }
    .profile-pic {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        border: 2px solid #29b5e8;
        object-fit: cover;
        box-shadow: 0px 0px 10px rgba(41, 181, 232, 0.4);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        cursor: pointer;
    }
    .profile-pic:hover {
        transform: scale(1.1);
        box-shadow: 0px 0px 15px rgba(41, 181, 232, 0.8);
    }
    .credit-text {
        text-align: right;
        line-height: 1.1;
    }
    .credit-name {
        font-size: 18px;
        font-weight: bold;
        color: white;
    }
    .credit-title {
        font-size: 14px;
        color: #ffeb3b;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }

    /* ⭐️ TEXT ALIGNMENT */
    .op-center-row { display: flex; align-items: center; justify-content: center; width: 100%; font-size: 1.5rem; font-weight: bold; line-height: 1 !important; margin: 0 !important; padding: 0 !important; transform: translateY(-15px); position: relative; }
    .top-status-center { display: flex; align-items: center; gap: 0.75rem; justify-content: center; max-width: calc(100% - 280px); white-space: nowrap; font-size: 1.7rem; }
    .top-status-right { position: absolute; right: 20px; top: 50%; transform: translateY(-50%); display: flex; align-items: center; gap: 0.45rem; font-size: 1.1rem; color: #ffeb3b; white-space: nowrap; }
    .top-status-right span { min-width: 64px; text-align: right; }
    .top-status-center span, .top-status-right span { line-height: 1.1; }
    .refresh-alert { color: #ff4b4b !important; }
    #refresh-icon { width: 20px; height: 20px; border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; animation: spin 1.2s linear infinite; }
    img.top-logo { width: 26px; height: 26px; object-fit: contain; }
    
    .status-timer { color: #21c354; font-family: monospace; }
    
    @keyframes blinker { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    .status-offline { color: #ff4b4b; font-family: monospace; animation: blinker 2s ease-in-out infinite; }
    
    div.stButton > button { background-color: #ff4b4b !important; color: white !important; font-weight: bold !important; border-radius: 5px; border: none; padding: 8px 0 !important; margin: 0 !important; }
    div.element-container:has(.pag-aligner) + div[data-testid="stHorizontalBlock"] div.stButton > button { height: 50px !important; font-size: 24px !important; border-radius: 8px !important; padding: 0 !important; margin-top: 10px !important; }
    
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
    # Top Left Logo Base64 Loading
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

    # ⭐️ PYTHON-GENERATED DYNAMIC BACKGROUND CSS (PERFECT LOOP) ⭐️
    random.seed(42) # Ensures background layout is consistent
    bg_images, bg_sizes, bg_repeats, bg_pos_0, bg_pos_100 = [], [], [], [], []

    # Dynamic Color Check based on Status
    if status_class == 'status-offline':
        colors = ['rgba(255, 75, 75, 0.9)', 'rgba(220, 20, 20, 0.8)', 'rgba(180, 0, 0, 0.7)']
        base_grad = "linear-gradient(135deg, rgb(50, 0, 0), rgb(20, 0, 0), rgb(50, 0, 0))"
    else:
        colors = ['rgba(41, 181, 232, 0.8)', 'rgba(255, 235, 59, 0.6)', 'rgba(27, 201, 142, 0.6)']
        base_grad = "linear-gradient(135deg, rgb(2, 25, 50), rgb(0, 8, 16), rgb(2, 25, 50))" # Darker Base

    # 40 Pure Vertical Streams with Flawless Math Looping
    for i in range(40):
        c = random.choice(colors)
        x = random.randint(1, 99) 
        h = random.randint(800, 2500) # Exact height of the repeating tile
        loops = random.randint(1, 4)  # How many full tile cycles happen in 20 seconds
        direction = random.choice([1, -1])
        spd = h * loops * direction # Multiplying height by integer guarantees a perfect, invisible loop!
        
        bg_images.append(f"linear-gradient(180deg, transparent 0%, transparent 45%, {c} 50%, transparent 55%, transparent 100%)")
        bg_sizes.append(f"2px {h}px") 
        bg_repeats.append("repeat-y") 
        bg_pos_0.append(f"{x}% 0px")  
        bg_pos_100.append(f"{x}% {spd}px") 

    # Base dark gradient underneath all streams
    bg_images.append(base_grad)
    bg_sizes.append("200% 200%")
    bg_repeats.append("repeat")
    bg_pos_0.append("0% 50%")
    bg_pos_100.append("100% 50%")

    dynamic_css = f"""
    <style>
    @keyframes dataStreams {{
        0% {{ background-position: {', '.join(bg_pos_0)}; }}
        100% {{ background-position: {', '.join(bg_pos_100)}; }}
    }}
    .block-container {{ 
        background-color: rgb(0, 5, 10) !important;
        background-image: {', '.join(bg_images)} !important;
        background-size: {', '.join(bg_sizes)} !important;
        background-repeat: {', '.join(bg_repeats)} !important;
        animation: dataStreams 20s linear infinite !important;
        background-attachment: fixed;
    }}
    </style>
    """
    st.markdown(dynamic_css, unsafe_allow_html=True)


    # --- TOP HEADER (Clock & Weather) ---
    header_col1, header_col2 = st.columns([3, 2])
    with header_col1:
        st.markdown("<div class='main-title'>Network Operations Center</div>", unsafe_allow_html=True)

    with header_col2:
        try:
            w_res = requests.get("https://wttr.in/Chula+Vista?format=%c+%t+|+💧+%h", timeout=3)
            weather = w_res.content.decode('utf-8').strip().replace("+", "")
        except: weather = "🌤️ --°F | 💧 --%" 
        
        st.markdown(f"""
            <div class='header-widget'>
                <div><strong id='live-clock'>{current_time_str}</strong></div>
                <div class='weather-text'>{weather}</div>
            </div>
        """, unsafe_allow_html=True)

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
    total_devices = len(net_devices)
    
    # ⭐️ DYNAMIC HEALTH SCORE CALCULATION
    if total_devices > 0:
        health_score = int((online_count / total_devices) * 100)
    else:
        health_score = 100
        
    # If the main firewall is offline, network health plummets to 0
    if not is_mx_online:
        health_score = 0
        
    # By removing the manual arrows, Streamlit will now generate them automatically
    # Positive strings get an up arrow automatically, negative strings get a down arrow.
    if health_score == 100:
        health_delta = "Optimal"
        health_color = "normal"
    elif health_score >= 75:
        health_delta = "- Degraded"
        health_color = "normal"
    else:
        health_delta = "- Critical"
        health_color = "normal"

    col1.metric("Infrastructure Status", "ONLINE" if is_mx_online else "OFFLINE", f"{online_count}/{total_devices} Connected")
    active_clients = sum(1 for c in clients_list if str(c.get('status', '')).lower() == 'online')
    col2.metric("Active Client Devices", f"{active_clients}", "Connected")
    col3.metric("Network Health Score", f"{health_score}%", health_delta, delta_color=health_color)
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
            st.altair_chart(app_chart, width='stretch')
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


    # --- ⭐️ COMBINED BOTTOM BOX (Tables + Pagination + Centered Credit Widget) ---
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
        
        # Bottom Layout: [Left Arrow] --- [Centered Credit Widget] --- [Right Arrow]
        _, f_l, f_m, f_r = st.columns([0.25, 1, 20, 1])
        
        # Wrapped the image in an <a> tag pointing to your LinkedIn
        profile_html = "<a href='https://www.linkedin.com/in/andrew-t-littrell-86279a388/?lipi=urn%3Ali%3Apage%3Ad_flagship3_profile_view_base_contact_details%3B8wV2gQCWQ9aqDUSY55EQIA%3D%3D' target='_blank'><img src='https://github.com/atlittrell2027-coder.png' class='profile-pic' onerror=\"this.src='https://api.dicebear.com/9.x/initials/svg?seed=AL&backgroundColor=29b5e8&textColor=ffffff'\" alt='Andrew Littrell'/></a>"

        credit_html = f"""
        <div class='credit-container'>
            <div class='credit-text'>
                <div class='credit-name'>Andrew Littrell</div>
                <div class='credit-title'>Network Founder</div>
            </div>
            {profile_html}
        </div>
        """

        with f_l:
            if st.button("←", key="prev_g", disabled=(st.session_state.dashboard_page == 0), width='stretch'):
                st.session_state.dashboard_page -= 1
                st.rerun()
        
        with f_m:
            st.markdown(credit_html, unsafe_allow_html=True)

        with f_r:
            if st.button("→", key="next_g", disabled=not can_next, width='stretch'):
                st.session_state.dashboard_page += 1
                st.rerun()

    # --- ⭐️ LIVE JAVASCRIPT TIMER INJECTION (Browser-Synced with Cache Busting) ---
    js_code = """
    <script>
    // CACHE BUSTER: SERVER_RENDER_TIME_VAL (Forces Streamlit to rebuild the script so Date.now() resets correctly)
    const parentDoc = window.parent.document;
    const stateTimestampMs = TIMESTAMP_VAL;
    const isOnline = IS_ONLINE_VAL;
    const refreshIntervalMs = 60000;
    
    // We grab the exact time the browser executes this refreshed code
    const scriptStartTimeMs = Date.now();

    setInterval(() => {
        const now = new Date();
        const currentTime = now.getTime();
        
        // Timer counts down strictly from when the browser loaded the page
        const elapsedSinceLoad = currentTime - scriptStartTimeMs;
        let remainingMs = refreshIntervalMs - elapsedSinceLoad;
        if (remainingMs <= 0) remainingMs = 0;
        
        const secondsUntilRefresh = Math.ceil(remainingMs / 1000);
        
        const refreshIcon = parentDoc.getElementById('refresh-icon');
        const refreshTimer = parentDoc.getElementById('refresh-timer');
        
        if (refreshIcon && refreshTimer) {
            // Once it hits 0, it will say Refreshing... while it waits for Python to finish fetching new API data
            if (secondsUntilRefresh <= 0) {
                refreshIcon.style.display = 'inline';
                refreshTimer.innerText = 'Refreshing...';
            } else {
                refreshIcon.style.display = 'none';
                refreshTimer.innerText = secondsUntilRefresh + 's';
            }

            if (secondsUntilRefresh <= 10 && secondsUntilRefresh > 0) {
                refreshTimer.classList.add('refresh-alert');
            } else {
                refreshTimer.classList.remove('refresh-alert');
            }
        }
        
        const clockEl = parentDoc.getElementById('live-clock');
        if (clockEl) {
            const formatter = new Intl.DateTimeFormat('en-US', { 
                timeZone: 'America/Los_Angeles', weekday: 'long', year: 'numeric', 
                month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', 
                second: '2-digit', hour12: true 
            });
            const parts = formatter.formatToParts(now);
            const p = {};
            parts.forEach(part => p[part.type] = part.value);
            const timeStr = `${p.weekday}, ${p.month} ${p.day}, ${p.year} | ${p.hour}:${p.minute}:${p.second} ${p.dayPeriod}`;
            clockEl.innerText = timeStr;
        }
        
        const timerEl = parentDoc.getElementById('live-timer');
        if (timerEl) {
            let elapsedMs = now.getTime() - stateTimestampMs;
            if (elapsedMs < 0) elapsedMs = 0;
            let totalSecs = Math.floor(elapsedMs / 1000);
            let days = Math.floor(totalSecs / 86400);
            let hours = Math.floor((totalSecs % 86400) / 3600);
            let mins = Math.floor((totalSecs % 3600) / 60);
            let secs = totalSecs % 60;
            const pad = (num) => String(num).padStart(2, '0');
            const prefix = isOnline ? "" : "-";
            timerEl.innerText = `${prefix}${days}d ${pad(hours)}h ${pad(mins)}m ${pad(secs)}s`;
        }
    }, 1000);
    </script>
    """
    
    js_code = js_code.replace("TIMESTAMP_VAL", str(int(state_timestamp.timestamp() * 1000)))
    # We still inject Python's current timestamp to bust the cache, preventing Streamlit from using old timers
    js_code = js_code.replace("SERVER_RENDER_TIME_VAL", str(int(current_pst.timestamp() * 1000)))
    js_code = js_code.replace("IS_ONLINE_VAL", "true" if is_mx_online else "false")
    components.html(js_code, height=0, width=0)

except Exception as e: st.error(f"Critical Error: {e}")
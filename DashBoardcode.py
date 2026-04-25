import streamlit as st
import meraki
import pandas as pd
import requests
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh
import altair as alt
import os

# ⏱ Refresh every 60 seconds
st_autorefresh(interval=60000, limit=None, key="meraki_refresh")

# Page Configuration
st.set_page_config(page_title="Network NOC Dashboard", layout="wide")

# --- SESSION STATE TRACKING ---
if 'dashboard_page' not in st.session_state:
    st.session_state.dashboard_page = 0
if 'uptime_start_time' not in st.session_state:
    st.session_state.uptime_start_time = datetime.now(pytz.timezone('US/Pacific'))
if 'downtime_start_time' not in st.session_state:
    st.session_state.downtime_start_time = None
if 'last_known_status' not in st.session_state:
    st.session_state.last_known_status = None

# --- TIME CALCULATION ---
pst_tz = pytz.timezone('US/Pacific')
current_pst = datetime.now(pst_tz)

# CSS: Advanced styling for Layout and Background
st.markdown("""
    <style>
    html, body { overflow-y: auto !important; }

    .block-container { 
        padding-top: 0.5rem !important; /* ⭐️ Nudged entire page up */
        padding-left: 0.5rem !important; 
        padding-right: 1rem; 
        max-width: 100% !important; 
        logo_path = /workspaces/Meraki_Dash/images/Background.png;
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }

    [data-testid="stMetric"] { display: flex; flex-direction: column; align-items: flex-start; text-align: left; padding-left: 10px; }
    
    /* ⭐️ NUDGED DIVIDING LINE UP */
    hr { 
        margin-left: 10px; 
        width: 100%; 
        margin-top: -17px !important; 
        margin-bottom: 10px !important; 
    }
    
    .tight-divider hr { margin-top: -32px !important; margin-bottom: 5px !important; }

    .header-widget { text-align: right; margin-top: 10px; font-size: 26px; } 
    .weather-text { color: #29b5e8; font-weight: bold; font-size: 30px; }
    .custom-legend { text-align: right; padding-top: 5px; font-size: 15px; font-weight: bold; }
    .op-center-row { text-align: center !important; width: 100%; font-size: 1.5rem; font-weight: bold; line-height: 2.2rem; }
    .status-timer { color: #21c354; font-family: monospace; }
    .status-offline { color: #ff4b4b; font-family: monospace; text-decoration: blink; }
    
    div.stButton > button { background-color: #ff4b4b !important; color: white !important; font-weight: bold !important; border-radius: 5px; border: none; }
    .pag-footer button { background-color: #ff4b4b !important; color: white !important; border: none !important; height: 50px !important; font-size: 24px !important; border-radius: 8px !important; }
    
    .centered-title { display: block; text-align: center !important; width: 100%; margin-bottom: 5px; font-size: 1.75rem; font-weight: 600; }
    .graph-title-shift { padding-left: 38px; font-size: 1.75rem; font-weight: bold; }

    /* ⭐️ LOGO POSITION: Shifted UP another 0.10 characters */
    .top-header-logo-container {
        padding-top: -2.00px; 
        margin-left: 10px;    
    }

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
    if 'ONLINE' in str(val):
        return 'background-color: #0e3d2f; color: #21c354; border: 1px solid #21c354; border-radius: 4px; font-weight: bold; padding: 2px 8px;'
    elif 'OFFLINE' in str(val):
        return 'background-color: #3d0e0e; color: #ff4b4b; border: 1px solid #ff4b4b; border-radius: 4px; font-weight: bold; padding: 2px 8px;'
    return ''

current_time_str = current_pst.strftime("%A, %B %d, %Y | %I:%M %p")

try:
    api_key = st.secrets["MERAKI_API_KEY"]
    dashboard = meraki.DashboardAPI(api_key, suppress_logging=True)
    org_id = dashboard.organizations.getOrganizations()[0]['id']
    network_id = dashboard.organizations.getOrganizationNetworks(org_id)[0]['id']

    # --- DATA GATHERING ---
    devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
    net_devices = [d for d in devices if d['networkId'] == network_id]
    clients_list = dashboard.networks.getNetworkClients(network_id, timespan=2592000)
    
    mx_device = next((d for d in net_devices if 'MX85' in d.get('model', '')), None)
    is_mx_online = mx_device.get('status').lower() == 'online' if mx_device else False

    # DYNAMIC TIMER LOGIC
    if is_mx_online:
        if st.session_state.last_known_status == 'offline' or st.session_state.uptime_start_time is None:
            st.session_state.uptime_start_time = current_pst
            st.session_state.downtime_start_time = None
        st.session_state.last_known_status = 'online'
        status_class, status_label, elapsed, prefix = "status-timer", "SYSTEM UPTIME:", current_pst - st.session_state.uptime_start_time, ""
    else:
        if st.session_state.last_known_status == 'online' or st.session_state.downtime_start_time is None:
            st.session_state.downtime_start_time = current_pst
            st.session_state.uptime_start_time = None
        st.session_state.last_known_status = 'offline'
        status_class, status_label, elapsed, prefix = "status-offline", "SYSTEM DOWNTIME:", current_pst - st.session_state.downtime_start_time, "-"

    days, hours_rem = divmod(elapsed.total_seconds(), 86400)
    hours, mins_rem = divmod(hours_rem, 3600)
    minutes, seconds = divmod(mins_rem, 60)
    uptime_display = f"{prefix}{int(days)}d {int(hours):02}h {int(minutes):02}m {int(seconds):02}s"

    # --- TOP HEADER ---
    header_col1, header_col2 = st.columns([3, 2])
    with header_col1:
        logo_l, title_r = st.columns([0.3, 2.7])
        with logo_l:
            logo_path = 'images/MDTV_Logo.png'
            if os.path.exists(logo_path):
                st.markdown('<div class="top-header-logo-container">', unsafe_allow_html=True)
                st.image(logo_path, width=100) 
                st.markdown('</div>', unsafe_allow_html=True)
        with title_r:
            st.title("Network Operations Center")

    with header_col2:
        try:
            w_res = requests.get("https://wttr.in/Chula+Vista?format=%c+%t+|+💧+%h", timeout=3)
            weather = w_res.content.decode('utf-8').strip().replace("+", "")
        except: weather = "🌤️ --°F | 💧 --%" 
        st.markdown(f"<div class='header-widget'><div><strong>{current_time_str}</strong></div><div class='weather-text'>{weather}</div></div>", unsafe_allow_html=True)

    st.markdown("---")

    # CENTERED STATUS ROW
    stat_col1, stat_col2, stat_col3 = st.columns([1, 6, 1])
    with stat_col2:
        st.markdown(f"<div class='op-center-row'><span>📍 MDTV Intranet Usage | </span><span class='{status_class}'>{status_label} {uptime_display}</span></div>", unsafe_allow_html=True)
    with stat_col3:
        if mx_device and st.button("Reboot System", key="reboot_btn", use_container_width=True):
            dashboard.devices.rebootDevice(mx_device['serial'])
            st.session_state.last_known_status = 'offline'
            st.rerun()

    # --- METRICS GATHERING ---
    uplink_usage = dashboard.appliance.getNetworkApplianceUplinksUsageHistory(network_id, timespan=7200, resolution=60)
    graph_data = []
    if uplink_usage:
        for entry in uplink_usage:
            dl_sum = sum((i.get('received') / 1e6) if i.get('received') is not None else 0 for i in entry.get('byInterface', []))
            ul_sum = sum((i.get('sent') / 1e6) if i.get('sent') is not None else 0 for i in entry.get('byInterface', []))
            graph_data.append({"Time": entry['startTime'], "Download (MB)": dl_sum, "Upload (MB)": ul_sum})

    top_apps = pd.DataFrame(columns=['application', 'Usage (MB)'])
    apps_error = False
    try:
        traffic_data = dashboard.networks.getNetworkTraffic(network_id, timespan=7200)
        if traffic_data:
            app_df = pd.DataFrame(traffic_data)
            app_df['Usage (MB)'] = (app_df['sent'].fillna(0) + app_df['recv'].fillna(0)) / 1048576
            top_apps = app_df.groupby('application')['Usage (MB)'].sum().reset_index().sort_values(by='Usage (MB)', ascending=False).head(5)
    except: apps_error = True

    # METRICS ROW
    if len(graph_data) >= 2:
        latest, previous = graph_data[-1], graph_data[-2]
        delta_dl, delta_ul = latest['Download (MB)'] - previous['Download (MB)'], latest['Upload (MB)'] - previous['Upload (MB)']
        delta_total = (latest['Download (MB)'] + latest['Upload (MB)']) - (previous['Download (MB)'] + previous['Upload (MB)'])
    else: 
        latest = graph_data[-1] if graph_data else {"Download (MB)":0, "Upload (MB)":0}
        delta_dl = delta_ul = delta_total = 0

    def get_delta_color(val): return "off" if round(val, 2) == 0.00 else "normal"

    spacer, col1, col2, col3, col4, col5, col6 = st.columns([0.35, 1, 1, 1, 1, 1, 1])
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
            df_graph['Time'] = pd.to_datetime(df_graph['Time']).dt.tz_convert('US/Pacific')
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
            app_chart = alt.Chart(top_apps).mark_bar(color='#29b5e8', cornerRadiusEnd=4).encode(
                x=alt.X('Usage (MB):Q', title=None, axis=None),
                y=alt.Y('application:N', title=None, sort='-x', axis=alt.Axis(labelFontSize=14, labelColor='white')),
                tooltip=['application', 'Usage (MB)']
            ).properties(height=300)
            st.altair_chart(app_chart, use_container_width=True)
        else: st.info("Gathering traffic data...")

    st.markdown("<div class='tight-divider'><hr></div>", unsafe_allow_html=True)
    
    # --- DUAL TABLES ---
    df_infra_all = pd.DataFrame(net_devices)[['name', 'model', 'status', 'mac']]
    df_infra_all['is_online'] = df_infra_all['status'] == 'online'
    
    device_usage = {str(c.get('recentDeviceMac', '')).lower(): (c.get('usage', {}).get('sent', 0) + c.get('usage', {}).get('recv', 0)) for c in clients_list}
    df_infra_all['traffic_raw'] = df_infra_all['mac'].str.lower().map(device_usage).fillna(0)
    df_infra_all['Total Traffic (30d)'] = df_infra_all['traffic_raw'].apply(lambda x: f"{x / 1048576:.2f} GB")
    df_infra_all['status'] = df_infra_all['status'].str.upper().map({'ONLINE': '↑ ONLINE', 'OFFLINE': '↓ OFFLINE'})
    df_infra_final = df_infra_all.sort_values(by=['is_online', 'traffic_raw'], ascending=[False, False])[['name', 'model', 'status', 'Total Traffic (30d)']].rename(columns={'name':'Name', 'model':'Model', 'status':'Status'})

    df_clients_all = pd.DataFrame(clients_list)
    if not df_clients_all.empty:
        df_clients_all['Port'] = df_clients_all['switchport'].apply(lambda x: x if x else "—")
        df_clients_all['status'] = df_clients_all['status'].str.upper().map({'ONLINE': '↑ ONLINE', 'OFFLINE': '↓ OFFLINE'})
        df_clients_final = df_clients_all.sort_values(by=['status', 'lastSeen'], ascending=[False, False])[['description', 'os', 'status', 'Port']].rename(columns={'description':'Description', 'os':'OS', 'status':'Status'})
    else: df_clients_final = pd.DataFrame(columns=['Description', 'OS', 'Status', 'Port'])

    t_l, t_r = st.columns(2)
    with t_l:
        st.markdown("<div class='centered-title'>🖧 Network Infrastructure</div>", unsafe_allow_html=True)
        st.dataframe(get_paged_data(df_infra_final, st.session_state.dashboard_page).style.map(color_status, subset=['Status']), width="stretch", hide_index=True)
    with t_r:
        st.markdown("<div class='centered-title'>💻 Recent Connected Clients</div>", unsafe_allow_html=True)
        st.dataframe(get_paged_data(df_clients_final, st.session_state.dashboard_page).style.map(color_status, subset=['Status']), width="stretch", hide_index=True)

    # FOOTER
    can_next = (st.session_state.dashboard_page + 1) * 5 < max(len(df_infra_all), len(df_clients_all))
    st.markdown("<div class='pag-footer'>", unsafe_allow_html=True)
    f_spacer, f_l, f_m, f_r = st.columns([0.25, 1, 20, 1])
    with f_l:
        if st.button("←", key="prev_g", disabled=(st.session_state.dashboard_page == 0)):
            st.session_state.dashboard_page -= 1
            st.rerun()
    with f_r:
        if st.button("→", key="next_g", disabled=not can_next):
            st.session_state.dashboard_page += 1
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

except Exception as e: st.error(f"Critical Error: {e}")
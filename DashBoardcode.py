import streamlit as st
import meraki
import pandas as pd
import requests
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh
import altair as alt

# ⭐️ UPDATED: Refresh every 60 seconds (60,000 milliseconds)
st_autorefresh(interval=60000, limit=None, key="meraki_refresh")

# Page Configuration
st.set_page_config(page_title="Network NOC Dashboard", layout="wide")

# --- HARDWARE UPTIME CALCULATION ---
pst_tz = pytz.timezone('US/Pacific')
boot_time = datetime(2026, 4, 24, 13, 48, 48, tzinfo=pst_tz)
current_pst = datetime.now(pst_tz)

elapsed = current_pst - boot_time
days = elapsed.days
hours, remainder = divmod(elapsed.seconds, 3600)
minutes, seconds = divmod(remainder, 60)
uptime_display = f"{days}d {hours:02}h {minutes:02}m {seconds:02}s"

# CSS: Professional NOC alignment, Red Button, and NO FADE logic
st.markdown("""
    <style>
    /* REMOVE REFRESH FADING (Force 100% Opacity) */
    [data-testid="stAppViewBlockContainer"] {
        opacity: 1 !important;
    }

    .block-container { 
        padding-top: 1rem; 
        padding-left: 0.5rem !important; 
        padding-right: 1rem; 
        max-width: 100% !important; 
    }
    
    [data-testid="stMetric"] {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        text-align: left;
        padding-left: 10px;
    }
    
    [data-testid="stMetricDelta"] > div {
        justify-content: flex-start;
    }

    hr {
        margin-left: 10px;
        width: 100%;
    }

    .header-widget { text-align: right; margin-top: 10px; font-size: 26px; } 
    .weather-text { color: #29b5e8; font-weight: bold; font-size: 32px; }
    .custom-legend { text-align: right; padding-top: 25px; font-size: 15px; font-weight: bold; }
    
    .op-center-row {
        text-align: center !important;
        width: 100%;
        font-size: 1.5rem;
        font-weight: bold;
        line-height: 2.2rem;
    }
    
    .status-timer { color: #21c354; font-family: monospace; }
    .status-offline { color: #ff4b4b; font-family: monospace; text-decoration: blink; }

    /* Red Reboot Button Styling */
    div.stButton > button {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        border-radius: 5px;
    }
    
    div.stButton > button:hover {
        background-color: #d32f2f !important;
        color: white !important;
    }

    .centered-title {
        display: block;
        text-align: center !important;
        width: 100%;
        margin-bottom: 10px;
        font-size: 1.75rem;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTION FOR TABLE PILLS ---
def color_status(val):
    if 'ONLINE' in str(val):
        return 'background-color: #0e3d2f; color: #21c354; border: 1px solid #21c354; border-radius: 4px; font-weight: bold; padding: 2px 8px;'
    elif 'OFFLINE' in str(val):
        return 'background-color: #3d0e0e; color: #ff4b4b; border: 1px solid #ff4b4b; border-radius: 4px; font-weight: bold; padding: 2px 8px;'
    return ''

# --- FETCH DATE, TIME, AND WEATHER ---
current_time_str = current_pst.strftime("%A, %B %d, %Y | %I:%M %p")

try:
    response = requests.get("https://wttr.in/Chula+Vista?format=%c+%t+|+💧+%h", timeout=3)
    response.encoding = 'utf-8' 
    weather_data = response.text.strip().replace("+", "")
except:
    weather_data = "🌤️ --°F | 💧 --%" 

# Securely pull API Key
try:
    api_key = st.secrets["MERAKI_API_KEY"]
except KeyError:
    st.error("API Key not found!")
    st.stop()

dashboard = meraki.DashboardAPI(api_key, suppress_logging=True)

try:
    orgs = dashboard.organizations.getOrganizations()
    org_id = orgs[0]['id'] 
    networks = dashboard.organizations.getOrganizationNetworks(org_id)
    network_id = networks[0]['id'] 
    
    # --- DATA GATHERING ---
    devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
    net_devices = [d for d in devices if d['networkId'] == network_id]
    
    # MX85 Status
    mx_device = next((d for d in net_devices if 'MX85' in d.get('model', '')), None)
    is_mx_online = mx_device.get('status') == 'online' if mx_device else False
    mx_serial = mx_device.get('serial') if mx_device else None
    
    status_class = "status-timer" if is_mx_online else "status-offline"
    final_uptime = uptime_display if is_mx_online else "OFFLINE"

    # --- TOP HEADER ---
    header_col1, header_col2 = st.columns([2, 1])
    with header_col1:
        st.title("🌐 Network Operations Center")
    with header_col2:
        st.markdown(f"<div class='header-widget'><div><strong>{current_time_str}</strong></div><div class='weather-text'>{weather_data}</div></div>", unsafe_allow_html=True)

    st.markdown("---")

    # CENTERED STATUS ROW + RED REBOOT BUTTON
    stat_col1, stat_col2, stat_col3 = st.columns([1, 6, 1])
    with stat_col2:
        st.markdown(f"""
            <div class='op-center-row'>
                <span>📍 MDTV Intranet Usage | </span>
                <span class='{status_class}'>SYSTEM UPTIME: {final_uptime}</span>
            </div>
        """, unsafe_allow_html=True)
    with stat_col3:
        if mx_serial:
            if st.button("Reboot System", width="stretch"):
                try:
                    dashboard.devices.rebootNetworkDevice(mx_serial)
                    st.success("Reboot command sent!")
                except Exception as e:
                    st.error(f"Reboot failed: {e}")

    online_devices = sum(1 for d in net_devices if d['status'] == 'online')
    total_devices = len(net_devices)
    hardware_status = "🟢 ONLINE" if online_devices == total_devices else "🔴 OFFLINE DETECTED"
    health_score = int((online_devices / total_devices) * 100) if total_devices > 0 else 100
    
    clients = dashboard.networks.getNetworkClients(network_id, timespan=2592000)
    online_clients = sum(1 for c in clients if c.get('status') == 'Online')

    device_usage = {}
    for c in clients:
        mac = c.get('recentDeviceMac')
        usage = c.get('usage', {'sent': 0, 'recv': 0})
        if mac not in device_usage:
            device_usage[mac] = {'sent': 0, 'recv': 0}
        device_usage[mac]['sent'] += usage.get('sent', 0)
        device_usage[mac]['recv'] += usage.get('recv', 0)

    for d in net_devices:
        d_mac = d.get('mac')
        usage = device_usage.get(d_mac, {'sent': 0, 'recv': 0})
        total_kb = usage['recv'] + usage['sent']
        d['Total Traffic (30d)'] = f"{total_kb / 1048576:.2f} GB"

    # ⭐️ 1-MINUTE RESOLUTION (Synchronized)
    uplink_usage = dashboard.appliance.getNetworkApplianceUplinksUsageHistory(
        network_id, 
        timespan=7200, 
        resolution=60
    )
    
    graph_data = []
    latest_dl, latest_ul, latest_total = 0, 0, 0
    if uplink_usage:
        for entry in uplink_usage:
            time = entry['startTime']
            dl, ul = 0, 0
            for interface in entry['byInterface']:
                dl += (interface['received'] / 1000000) 
                ul += (interface['sent'] / 1000000)
            graph_data.append({"Time": time, "Download (MB)": dl, "Upload (MB)": ul})
        latest_dl = graph_data[-1]["Download (MB)"]
        latest_ul = graph_data[-1]["Upload (MB)"]
        latest_total = latest_dl + latest_ul

    # --- LIVE DATA METRICS ---
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Infrastructure Status", hardware_status, f"{online_devices}/{total_devices} Online")
    col2.metric("Active Client Devices", f"{online_clients}", "Connected right now")
    col3.metric("Network Health Score", f"{health_score}%", "Optimal")
    col4.metric("WAN Total (Live)", f"{latest_total:.2f} MB", delta="Traffic Load", delta_color="off")
    col5.metric("WAN Download (Live)", f"{latest_dl:.2f} MB", delta=f"{latest_dl:.2f} MB", delta_color="normal")
    col6.metric("WAN Upload (Live)", f"{latest_ul:.2f} MB", delta=f"{latest_ul:.2f} MB", delta_color="normal")
    
    # --- INTERACTIVE WAN GRAPH ---
    chart_title_col, chart_legend_col = st.columns([3, 1])
    with chart_title_col:
        st.markdown("### 📈 WAN Bandwidth History (Last 2 Hours)")
    with chart_legend_col:
        st.markdown("<div class='custom-legend'><span style='color: #29b5e8;'>● Download (MB)</span> &nbsp;&nbsp;&nbsp; <span style='color: #ff4b4b;'>● Upload (MB)</span></div>", unsafe_allow_html=True)
        
    df_graph = pd.DataFrame(graph_data)
    if not df_graph.empty:
        df_graph['Time'] = pd.to_datetime(df_graph['Time']).dt.tz_convert('US/Pacific')
        
        # Tooltip formatting
        df_graph['Tooltip_Time'] = df_graph['Time'].dt.strftime('%A, %I:%M %p')
        df_graph['DL_Info'] = df_graph['Download (MB)'].apply(lambda x: f"↓ {x:.2f} MB | {x/1024:.4f} GB")
        df_graph['UL_Info'] = df_graph['Upload (MB)'].apply(lambda x: f"↑ {x:.2f} MB | {x/1024:.4f} GB")
        
        df_melted = df_graph.melt(id_vars=['Time'], value_vars=['Download (MB)', 'Upload (MB)'], var_name='Traffic Type', value_name='MB')
        hover_selection = alt.selection_point(fields=['Time'], nearest=True, on='mouseover', empty=False)

        base = alt.Chart(df_melted).encode(
            x=alt.X('Time:T', title=None),
            y=alt.Y('MB:Q', title=None, stack=None),
            color=alt.Color('Traffic Type:N', scale=alt.Scale(domain=['Download (MB)', 'Upload (MB)'], range=["#29b5e8", "#ff4b4b"]), legend=None),
            tooltip=alt.value(None) 
        )
        areas = base.mark_area(opacity=0.7)

        selectors = alt.Chart(df_graph).mark_rule(color='transparent').encode(
            x='Time:T',
            tooltip=[
                alt.Tooltip('Tooltip_Time:N', title='TIME'),
                alt.Tooltip('DL_Info:N', title='DOWNLOAD'),
                alt.Tooltip('UL_Info:N', title='UPLOAD')
            ]
        ).add_params(hover_selection)

        rules = alt.Chart(df_graph).mark_rule(color='white', strokeWidth=1).encode(x='Time:T').transform_filter(hover_selection)
        points = alt.Chart(df_melted).mark_circle().encode(
            x='Time:T', y='MB:Q', color='Traffic Type:N',
            opacity=alt.condition(hover_selection, alt.value(1), alt.value(0)),
            tooltip=alt.value(None)
        ).transform_filter(hover_selection)

        st.altair_chart(alt.layer(areas, selectors, rules, points).properties(height=350), width="stretch")
    
    st.markdown("---")
    table_col1, table_col2 = st.columns(2)
    
    # 🖧 INFRASTRUCTURE TABLE
    with table_col1:
        st.markdown("<div class='centered-title'>🖧 Network Infrastructure</div>", unsafe_allow_html=True)
        df_devices = pd.DataFrame(net_devices)
        if not df_devices.empty:
            df_clean_devices = df_devices[['name', 'model', 'status', 'Total Traffic (30d)']]
            df_clean_devices['status'] = df_clean_devices['status'].str.upper().map({'ONLINE': '↑ ONLINE', 'OFFLINE': '↓ OFFLINE'})
            df_clean_devices = df_clean_devices.sort_values(by=['status', 'Total Traffic (30d)'], ascending=[False, False])
            styled_devices = df_clean_devices.style.map(color_status, subset=['status'])
            
            st.dataframe(styled_devices, width="stretch", hide_index=True, height=210,
                column_config={"status": st.column_config.Column("Status", alignment="center")})
            
    # 💻 CLIENTS TABLE
    with table_col2:
        st.markdown("<div class='centered-title'>💻 Recent Connected Clients</div>", unsafe_allow_html=True)
        df_clients = pd.DataFrame(clients)
        if not df_clients.empty:
            df_clients['Port'] = df_clients['switchport'].apply(lambda x: x if x else "—")
            df_clean_clients = df_clients[['description', 'os', 'status', 'Port']]
            df_clean_clients['status'] = df_clean_clients['status'].str.upper().map({'ONLINE': '↑ ONLINE', 'OFFLINE': '↓ OFFLINE'})
            df_clean_clients = df_clean_clients.sort_values(by=['status', 'description'], ascending=[False, True])
            styled_clients = df_clean_clients.style.map(color_status, subset=['status'])
            
            st.dataframe(styled_clients, width="stretch", hide_index=True, height=210,
                column_config={"status": st.column_config.Column("Status", alignment="center")})

except Exception as e:
    st.error(f"Error: {e}")
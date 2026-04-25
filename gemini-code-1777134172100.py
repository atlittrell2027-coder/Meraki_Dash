import streamlit as st
import meraki
import pandas as pd
import requests
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh
import altair as alt

# Refresh every 30 seconds
st_autorefresh(interval=30000, limit=None, key="meraki_refresh")

# Page Configuration & Custom CSS Styling
st.set_page_config(page_title="Network NOC Dashboard", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; }
    .header-widget { text-align: right; margin-top: 10px; font-size: 26px; } 
    .weather-text { color: #29b5e8; font-weight: bold; font-size: 32px; }
    .custom-legend { text-align: right; padding-top: 25px; font-size: 15px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- FETCH DATE, TIME, AND WEATHER ---
pst_tz = pytz.timezone('US/Pacific')
current_time = datetime.now(pst_tz).strftime("%A, %B %d, %Y | %I:%M %p")

try:
    response = requests.get("https://wttr.in/Chula+Vista?format=%c+%t+|+💧+%h", timeout=3)
    response.encoding = 'utf-8' 
    weather_data = response.text.strip().replace("+", "")
except:
    weather_data = "🌤️ --°F | 💧 --%" 

# --- HEADER LAYOUT ---
header_col1, header_col2 = st.columns([2, 1])

with header_col1:
    st.title("🌐 Network Operations Center")
    st.subheader("📍 MDTV Intranet Usage")
    
with header_col2:
    st.markdown(f"""
        <div class='header-widget'>
            <div><strong>{current_time}</strong></div>
            <div class='weather-text'>{weather_data}</div>
        </div>
    """, unsafe_allow_html=True)

# Securely pull the API Key from Streamlit Secrets
try:
    api_key = st.secrets["MERAKI_API_KEY"]
except KeyError:
    st.error("API Key not found! Please check your secrets setup.")
    st.stop()

# INITIALIZE THE MERAKI DASHBOARD
dashboard = meraki.DashboardAPI(api_key, suppress_logging=True)

try:
    # Get Organization and Network IDs 
    orgs = dashboard.organizations.getOrganizations()
    org_id = orgs[0]['id'] 
    
    networks = dashboard.organizations.getOrganizationNetworks(org_id)
    network_id = networks[0]['id'] 
    
    st.markdown("---")
    
    # --- DATA GATHERING ---
    
    # A. Get Hardware Status
    devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
    net_devices = [d for d in devices if d['networkId'] == network_id]
    
    online_devices = sum(1 for d in net_devices if d['status'] == 'online')
    total_devices = len(net_devices)
    
    # ⭐️ UPDATE 1: Changed label from "ALL HEALTHY" to "ONLINE"
    hardware_status = "🟢 ONLINE" if online_devices == total_devices else "🔴 OFFLINE DETECTED"
    
    # ⭐️ UPDATE 2: Calculate a dynamic Network Health Score
    health_score = int((online_devices / total_devices) * 100) if total_devices > 0 else 100
    health_delta = "Optimal" if health_score == 100 else "Needs Attention"
    
    # B. Get Connected Clients & Calculate Per-Switch Usage
    clients = dashboard.networks.getNetworkClients(network_id, timespan=86400)
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
        d['Total Traffic (GB)'] = total_kb / 1048576

    # C. Get MX85 Uplink History for the Graph
    uplink_usage = dashboard.appliance.getNetworkApplianceUplinksUsageHistory(network_id, timespan=7200)
    
    graph_data = []
    latest_dl = 0
    latest_ul = 0
    
    if uplink_usage:
        for entry in uplink_usage:
            time = entry['startTime']
            dl = 0
            ul = 0
            for interface in entry['byInterface']:
                dl += (interface['received'] / 1000000) 
                ul += (interface['sent'] / 1000000)
            graph_data.append({"Time": time, "Download (MB)": dl, "Upload (MB)": ul})
            
        latest_dl = graph_data[-1]["Download (MB)"]
        latest_ul = graph_data[-1]["Upload (MB)"]

    # --- UI LAYOUT ---
    
    # ⭐️ UPDATE 3: Expanding to 5 columns so the layout stays balanced
    col1, col2, col3, col4, col5 = st.columns(5)
    
    col1.metric("Infrastructure Status", hardware_status, f"{online_devices}/{total_devices} Online")
    col2.metric("Active Client Devices", f"{online_clients}", "Connected right now")
    
    # ⭐️ UPDATE 4: Dropping the Health Score directly in the middle
    col3.metric("Network Health Score", f"{health_score}%", health_delta)
    
    col4.metric("WAN Download (Live)", f"{latest_dl:.2f} MB")
    col5.metric("WAN Upload (Live)", f"{latest_ul:.2f} MB")
    
    # 📈 CHART TITLE & CUSTOM INLINE LEGEND
    chart_title_col, chart_legend_col = st.columns([3, 1])
    with chart_title_col:
        st.markdown("### 📈 WAN Bandwidth History (Last 2 Hours)")
    with chart_legend_col:
        st.markdown("""
            <div class='custom-legend'>
                <span style='color: #29b5e8;'>● Download (MB)</span> &nbsp;&nbsp;&nbsp; 
                <span style='color: #ff4b4b;'>● Upload (MB)</span>
            </div>
        """, unsafe_allow_html=True)
        
    df_graph = pd.DataFrame(graph_data)
    if not df_graph.empty:
        df_graph['Time'] = pd.to_datetime(df_graph['Time']).dt.tz_convert('US/Pacific')
        
        df_melted = df_graph.melt(id_vars=['Time'], value_vars=['Download (MB)', 'Upload (MB)'], var_name='Traffic Type', value_name='MB')
        
        chart = alt.Chart(df_melted).mark_area(opacity=0.7).encode(
            x=alt.X('Time:T', title=None),
            y=alt.Y('MB:Q', title=None, stack=None), 
            color=alt.Color(
                'Traffic Type:N', 
                scale=alt.Scale(domain=['Download (MB)', 'Upload (MB)'], range=["#29b5e8", "#ff4b4b"]),
                legend=None 
            )
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Gathering history. The graph will populate soon.")
    
    st.markdown("---")
    
    table_col1, table_col2 = st.columns(2)
    
    # 🖧 INFRASTRUCTURE TABLE
    with table_col1:
        st.markdown("### 🖧 Network Infrastructure")
        df_devices = pd.DataFrame(net_devices)
        if not df_devices.empty:
            df_clean_devices = df_devices[['name', 'model', 'status', 'Total Traffic (GB)']]
            
            df_clean_devices = df_clean_devices.sort_values(by=['status', 'Total Traffic (GB)'], ascending=[False, False])
            
            st.dataframe(
                df_clean_devices, 
                use_container_width=True, 
                hide_index=True,
                height=210,
                column_config={
                    "name": "Device Name",
                    "model": "Model",
                    "status": "Status",
                    "Total Traffic (GB)": st.column_config.NumberColumn(
                        "Total Traffic (24h)", 
                        format="%.2f GB",
                        help="Combined upload and download"
                    )
                }
            )
            
    # 💻 CLIENTS TABLE
    with table_col2:
        st.markdown("### 💻 Recent Connected Clients")
        df_clients = pd.DataFrame(clients)
        if not df_clients.empty:
            if 'description' not in df_clients.columns:
                df_clients['description'] = "Unknown"
            
            df_clean_clients = df_clients[['description', 'os', 'status']]
            
            df_clean_clients = df_clean_clients.sort_values(by=['status', 'description'], ascending=[False, True])
            
            st.dataframe(
                df_clean_clients, 
                use_container_width=True, 
                hide_index=True,
                height=210,
                column_config={
                    "description": "Client Name",
                    "os": "Operating System",
                    "status": "Status"
                }
            )

except Exception as e:
    st.error(f"Failed to pull data. Ensure your API key is correct. Error: {e}")
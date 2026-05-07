import streamlit as st
import streamlit.components.v1 as components
import meraki
import random
import json
from pathlib import Path
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# ⏱ Auto-refresh the rack every 60 seconds
st_autorefresh(interval=60000, limit=None, key="meraki_rack_refresh")

st.set_page_config(page_title="Hardware Rack", layout="wide")

pst_tz = pytz.timezone('America/Los_Angeles')
current_pst = datetime.now(pst_tz)

# Try to sync with main dashboard's uptime state if available
state_file = Path(__file__).resolve().parent.parent / 'traffic_state.json'
state_timestamp = current_pst
try:
    if state_file.exists():
        raw = json.loads(state_file.read_text())
        ts = raw.get('traffic_state_start')
        if ts: state_timestamp = datetime.fromisoformat(ts)
except Exception: pass

# --- CUSTOM CSS FOR THE HARDWARE RACK ---
st.markdown("""
    <style>
    /* Hide Streamlit Header & Footer */
    [data-testid="stHeader"], footer, [data-testid="collapsedControl"] { display: none !important; }
    .block-container { padding-top: 1rem !important; max-width: 100% !important; display: flex; flex-direction: column; align-items: center; }
    
    body, .stApp { background-color: rgb(0, 5, 10) !important; color: white; }
    
    .page-title { text-align: center; color: #29b5e8; font-size: 2.5rem; font-weight: bold; margin-bottom: 20px; width: 100%; }

    /* The Main Wrapper - SYMMETRICAL 3-COLUMN LAYOUT */
    .rack-system-wrapper { 
        display: flex; gap: 15px; width: 100%; max-width: 1200px; margin: 0 auto; justify-content: center; align-items: flex-start; 
    }

    /* Left Side: Floating Labels */
    .labels-column { width: 180px; flex-shrink: 0; display: flex; flex-direction: column; padding-top: 32px; }
    .label-slot { height: 60px; margin-bottom: 2px; display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
    .hw-name { font-size: 1rem; color: #e0e0e0; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: right; max-width: 140px; }

    /* Right Side: Floating Telemetry Data */
    .data-column { width: 180px; flex-shrink: 0; display: flex; flex-direction: column; padding-top: 32px; }
    .data-slot { height: 60px; margin-bottom: 2px; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; padding-left: 10px; gap: 2px; }
    .data-text { font-family: 'Courier New', monospace; font-size: 0.75rem; color: #29b5e8; line-height: 1.2; opacity: 0.85; white-space: nowrap; }
    .data-text.alert { color: #ff4b4b; opacity: 1; font-weight: bold; }

    /* Status LED Lights */
    .status-light { width: 14px; height: 14px; border-radius: 50%; border: 1px solid rgba(0,0,0,0.5); flex-shrink: 0; }
    .status-online { background-color: #2bff62; box-shadow: 0 0 12px #2bff62; }
    .status-offline { background-color: #ff4b4b; animation: blink 1s infinite; box-shadow: 0 0 12px #ff4b4b; }
    @keyframes blink { 0% {opacity: 1;} 50% {opacity: 0.2;} 100% {opacity: 1;} }

    /* 42U Server Cabinet Frame */
    .rack-cabinet {
        background-color: #050505; border: 12px solid #1a1a1a; border-radius: 4px; padding: 20px 20px;
        width: 680px; flex-shrink: 0; box-shadow: 0px 15px 35px rgba(0,0,0,0.9), inset 0px 0px 20px #000;
        display: flex; flex-direction: column; gap: 0px; position: relative;
    }
    .rack-cabinet::before, .rack-cabinet::after {
        content: ''; position: absolute; top: 0; bottom: 0; width: 20px;
        background-image: radial-gradient(#000 40%, transparent 45%); background-size: 10px 15px; background-position: center;
    }
    .rack-cabinet::before { left: 5px; border-right: 2px solid #333; }
    .rack-cabinet::after { right: 5px; border-left: 2px solid #333; }

    /* Hardware Device Base (19" Scale) */
    .rack-unit {
        background: linear-gradient(180deg, #e0e0e0 0%, #ffffff 15%, #b0b0b0 100%);
        border: 1px solid #777; border-radius: 2px; height: 60px; display: flex; align-items: center; padding: 0;
        box-shadow: 0px 3px 6px rgba(0,0,0,0.6); position: relative; z-index: 2; margin-bottom: 2px;
    }
    .rack-unit.offline { background: linear-gradient(180deg, #d4a0a0 0%, #ffcccc 15%, #b07070 100%); border-color: #ff4b4b; }
    .empty-slot { height: 60px; background-color: #0a0a0a; border: 1px solid #151515; display: flex; align-items: center; justify-content: center; color: #333; font-family: monospace; font-size: 12px; margin-bottom: 2px; letter-spacing: 4px; }

    /* PORT LAYOUTS */
    .ports-wrapper { 
        display: flex; align-items: flex-end; justify-content: center; width: 100%; 
        padding-right: 0px; gap: 8px; padding-bottom: 6px;
    }
    .port-block { display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 2px; }
    .port-group { display: flex; gap: 4px; } 
    .port-col { display: flex; flex-direction: column; align-items: center; gap: 3px; }
    
    /* TINY TEXT LABELS */
    .top-label { font-size: 6px; color: #444; font-weight: 900; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 1px; font-family: sans-serif; }
    .col-lbl { font-size: 4.5px; color: #333; text-align: center; font-weight: 900; line-height: 1.1; margin-top: 1px; font-family: sans-serif; }
    
    .sfp-divider { width: 1px; height: 28px; background-color: #888; border-radius: 1px; margin: 0 4px; margin-bottom: 10px; }

    /* PORT STYLES */
    .port { width: 13px; height: 11px; background-color: #0a0a0a; border: 1px solid #444; border-top: 3px solid #333; position: relative; border-radius: 1px; }
    .port.sfp { width: 14px; height: 12px; background-color: #111; border: 1px solid #777; border-top: 1px solid #aaa; border-radius: 2px; }
    
    /* MX Special Ports */
    .port.usb { width: 12px; height: 5px; border: 1px solid #888; border-top: 1px solid #ccc; background-color: #111; margin-top: 3px; }
    .port.mgt { border-color: #b8860b; border-top: 3px solid #daa520; } 
    
    /* ADMINISTRATIVELY DISABLED PORT */
    .port.disabled { background-color: #2b2b2b !important; border: 1px solid #555 !important; border-top: 3px solid #222 !important; opacity: 0.3 !important; }

    /* BRIGHTER ANIMATED LINK LIGHTS */
    @keyframes traffic-flicker {
        0% { opacity: 1; box-shadow: 0 0 10px #2bff62; }
        25% { opacity: 0.3; box-shadow: 0 0 2px #2bff62; }
        50% { opacity: 0.9; box-shadow: 0 0 8px #2bff62; }
        75% { opacity: 0.1; box-shadow: none; }
        100% { opacity: 1; box-shadow: 0 0 10px #2bff62; }
    }
    
    .port.active { background-color: #111; border-color: #666; border-top-color: #444; }
    .port.active::after {
        content: ''; position: absolute; top: -4px; left: 1px; width: 3.5px; height: 3.5px;
        background-color: #2bff62; border-radius: 50%;
        animation: traffic-flicker 0.4s infinite alternate; animation-delay: var(--anim-delay, 0s); 
    }
    .port.sfp.active::after { left: 1.5px; }

    /* ⭐️ CUSTOM SHELF (U31) - PERFECTLY CENTERED */
    .shelf-unit {
        height: 60px;
        background: linear-gradient(180deg, #181818 0%, #0a0a0a 90%, #222 100%);
        border: 1px solid #333; border-radius: 2px;
        display: flex; align-items: flex-end; 
        justify-content: center; /* ⭐️ Centers the entire payload on the shelf */
        padding: 0 0 3px 0; 
        box-shadow: inset 0 -8px 15px rgba(0,0,0,0.8);
        position: relative; z-index: 2; margin-bottom: 2px; gap: 30px; /* ⭐️ Gap between Stack and Cloud Key */
    }
    
    .stack-container { display: flex; flex-direction: column; align-items: center; gap: 1px; }

    .mac-mini {
        width: 250px; 
        height: 16px;
        background: linear-gradient(180deg, #f8f9fa, #d1d5db);
        border: 1px solid #9ca3af; border-radius: 4px 4px 0 0;
        display: flex; align-items: center; justify-content: center;
        font-size: 6px; font-weight: 900; color: #4b5563; letter-spacing: 1px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.5);
    }
    
    .unifi-switch {
        width: 250px; 
        height: 26px;
        background: linear-gradient(180deg, #ffffff, #e5e7eb);
        border: 1px solid #9ca3af; border-radius: 2px;
        display: flex; align-items: center; justify-content: space-between;
        padding: 0 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.6);
    }
    
    .unifi-logo {
        width: 14px; height: 14px; background-color: #0ea5e9; border-radius: 3px;
        box-shadow: 0 0 6px rgba(14, 165, 233, 0.6);
    }
    
    .unifi-ports { display: flex; align-items: center; gap: 4px; }

    .cloud-key {
        width: 60px; height: 18px; margin-bottom: 1px;
        background: linear-gradient(180deg, #f8f9fa, #d1d5db);
        border: 1px solid #9ca3af; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        font-size: 5px; font-weight: 900; color: #4b5563; letter-spacing: 1px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.6); position: relative;
    }
    .cloud-key::before {
        content: ''; position: absolute; left: 8px; top: 7px; width: 4px; height: 4px;
        background-color: #0ea5e9; border-radius: 50%; box-shadow: 0 0 4px #0ea5e9;
    }

    /* Timer styles */
    .refresh-alert { color: #ff4b4b !important; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
""", unsafe_allow_html=True)

# Navigation Header & Timer
st.markdown("<div style='width: 100%; max-width: 1200px; display: flex; justify-content: space-between; align-items: center;'>", unsafe_allow_html=True)
nav_col, title_col, timer_col = st.columns([1, 4, 1])
with nav_col:
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    if st.button("← Back to NOC Dashboard", use_container_width=True):
        st.switch_page("DashBoardcode.py")
with title_col:
    st.markdown("<div class='page-title'>🖧 Virtual 42U Hardware Rack</div>", unsafe_allow_html=True)
with timer_col:
    st.markdown("""
        <div style='text-align: right; margin-top: 25px;'>
            <div id='refresh-icon' style='display: none; width: 18px; height: 18px; border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; animation: spin 1.2s linear infinite; display: inline-block; vertical-align: middle; margin-right: 5px;'></div>
            <span id='refresh-timer' style='color: #ffeb3b; font-size: 1rem; font-weight: bold; vertical-align: middle;'>60s</span>
        </div>
    """, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

try:
    api_key = st.secrets["MERAKI_API_KEY"]
    dashboard = meraki.DashboardAPI(api_key, suppress_logging=True)
    org_id = dashboard.organizations.getOrganizations()[0]['id']
    network_id = dashboard.organizations.getOrganizationNetworks(org_id)[0]['id']

    devices = dashboard.organizations.getOrganizationDevicesStatuses(org_id)
    rack_hardware = [d for d in devices if d['networkId'] == network_id and not d.get('model', '').upper().startswith('MR')]

    # ⭐️ EXPLICIT PHYSICAL RACK MAPPING
    u_mapping = {}
    unmapped_devices = []

    for d in rack_hardware:
        name = d.get('name', '').lower()
        if 'switch 4' in name: u_mapping[41] = d
        elif 'switch 3' in name: u_mapping[39] = d
        elif 'switch 2' in name: u_mapping[37] = d
        elif 'switch 1' in name: u_mapping[35] = d
        elif 'spare' in name: u_mapping[34] = d
        elif 'mdt' in name: u_mapping[33] = d
        else: unmapped_devices.append(d)

    # Place unmapped extra switches dynamically
    current_unmapped_u = 30 
    for d in unmapped_devices:
        while current_unmapped_u in u_mapping and current_unmapped_u > 0:
            current_unmapped_u -= 1
        if current_unmapped_u > 0:
            u_mapping[current_unmapped_u] = d
            current_unmapped_u -= 1

    is_mx_online = True
    for d in rack_hardware:
        if 'MX' in d.get('model', '').upper() and d.get('status', '').lower() != 'online':
            is_mx_online = False
            break
            
    random.seed(42)
    bg_images, bg_sizes, bg_repeats, bg_pos_0, bg_pos_100 = [], [], [], [], []

    if not is_mx_online:
        colors = ['rgba(255, 75, 75, 0.9)', 'rgba(220, 20, 20, 0.8)', 'rgba(180, 0, 0, 0.7)']
        base_grad = "linear-gradient(135deg, rgb(50, 0, 0), rgb(20, 0, 0), rgb(50, 0, 0))"
    else:
        colors = ['rgba(41, 181, 232, 0.8)', 'rgba(255, 235, 59, 0.6)', 'rgba(27, 201, 142, 0.6)']
        base_grad = "linear-gradient(135deg, rgb(2, 25, 50), rgb(0, 8, 16), rgb(2, 25, 50))"

    for i in range(40):
        c = random.choice(colors)
        x = random.randint(1, 99) 
        h = random.randint(800, 2500)
        loops = random.randint(1, 4)
        direction = random.choice([1, -1])
        spd = h * loops * direction
        bg_images.append(f"linear-gradient(180deg, transparent 0%, transparent 45%, {c} 50%, transparent 55%, transparent 100%)")
        bg_sizes.append(f"2px {h}px") 
        bg_repeats.append("repeat-y") 
        bg_pos_0.append(f"{x}% 0px")  
        bg_pos_100.append(f"{x}% {spd}px") 

    bg_images.append(base_grad)
    bg_sizes.append("200% 200%")
    bg_repeats.append("repeat")
    bg_pos_0.append("0% 50%")
    bg_pos_100.append("100% 50%")

    dynamic_css = f"""
    <style>
    @keyframes dataStreams {{ 0% {{ background-position: {', '.join(bg_pos_0)}; }} 100% {{ background-position: {', '.join(bg_pos_100)}; }} }}
    .block-container {{ 
        background-color: rgb(0, 5, 10) !important; background-image: {', '.join(bg_images)} !important;
        background-size: {', '.join(bg_sizes)} !important; background-repeat: {', '.join(bg_repeats)} !important;
        animation: dataStreams 20s linear infinite !important; background-attachment: fixed;
    }}
    </style>
    """
    st.markdown(dynamic_css, unsafe_allow_html=True)

    if not rack_hardware:
        st.warning("No rack-mountable devices found in this network.")
    else:
        # Start Master Wrapper
        html_lines = ["<div class='rack-system-wrapper'>"]
        
        # --- LEFT COLUMN: LABELS ---
        html_lines.append("<div class='labels-column'>")
        for u in range(42, 0, -1):
            if u in u_mapping:
                d = u_mapping[u]
                is_online = d['status'].lower() == 'online'
                status_class = "status-online" if is_online else "status-offline"
                name = d.get('name', '') or d.get('mac', 'Unknown')
                html_lines.append(f"<div class='label-slot'><span class='hw-name'>{name}</span><span class='status-light {status_class}'></span></div>")
            elif u == 31:
                html_lines.append(f"<div class='label-slot'><span class='hw-name'>UniFi USW / Mac Mini</span><span class='status-light status-online'></span></div>")
            else:
                html_lines.append("<div class='label-slot'></div>")
        html_lines.append("</div>") 

        # --- CENTER COLUMN: 42U RACK ---
        html_lines.append("<div class='rack-cabinet'>")
        for u in range(42, 0, -1):
            if u in u_mapping:
                d = u_mapping[u]
                is_online = d['status'].lower() == 'online'
                rack_class = "rack-unit" if is_online else "rack-unit offline"
                model = d.get('model', 'Meraki Device')
                serial = d.get('serial')
                
                real_port_statuses = {}
                if 'MS' in model and is_online:
                    try:
                        ports_data = dashboard.switch.getDeviceSwitchPortsStatuses(serial)
                        for p in ports_data: real_port_statuses[str(p.get('portId'))] = p.get('status', '').lower()
                    except Exception: pass 
                
                def get_port_html(p_id, base_cls="port", force_active=False):
                    cls = base_cls
                    tit = f"Port {p_id}"
                    delay = f"style='--anim-delay: {random.uniform(0, 1):.2f}s;'"
                    
                    if force_active and is_online:
                        cls += " active"
                        tit += " | CONNECTED"
                    elif real_port_statuses:
                        stat = real_port_statuses.get(str(p_id), 'disconnected')
                        tit += f" | {stat.upper()}"
                        if stat == 'connected': cls += " active"
                        elif stat == 'disabled': cls += " disabled" 
                    
                    return f"<div class='{cls}' {delay} title='{tit}'></div>"

                def gen_column(top_id, bot_id, base_cls="port", f_act_top=False, f_act_bot=False):
                    col_html = "<div class='port-col'>"
                    col_html += get_port_html(top_id, base_cls, f_act_top)
                    col_html += get_port_html(bot_id, base_cls, f_act_bot)
                    col_html += f"<div class='col-lbl'>{top_id}▲<br>{bot_id}▼</div>"
                    col_html += "</div>"
                    return col_html

                ports_html = ""

                # MX85 GENERATION
                if 'MX' in model:
                    ports_html += "<div class='ports-wrapper'>"
                    ports_html += "<div class='port-block'><div class='top-label'>SYSTEM</div><div class='port-group'>"
                    ports_html += "<div class='port-col'>"
                    ports_html += f"<div class='port usb' title='USB Port'></div>"
                    ports_html += f"<div class='port mgt' title='Management Port'></div>"
                    ports_html += "<div class='col-lbl'>USB<br>MGT</div></div>"
                    ports_html += "</div></div><div class='sfp-divider'></div>"
                    
                    ports_html += "<div class='port-block'><div class='top-label'>WAN</div><div class='port-group'>"
                    ports_html += gen_column(1, 2, "port sfp", True, False) 
                    ports_html += gen_column(3, 4, "port", True, False)     
                    ports_html += "</div></div><div class='sfp-divider'></div>"
                    
                    ports_html += "<div class='port-block'><div class='top-label'>LAN</div><div class='port-group'>"
                    ports_html += gen_column(5, 6, "port")
                    ports_html += gen_column(7, 8, "port")
                    ports_html += gen_column(9, 10, "port")
                    ports_html += gen_column(11, 12, "port")
                    ports_html += "</div></div><div class='sfp-divider'></div>"
                    
                    ports_html += "<div class='port-block'><div class='top-label'>SFP LAN</div><div class='port-group'>"
                    ports_html += gen_column(13, 14, "port sfp")
                    ports_html += "</div></div>"
                    ports_html += "</div>" 
                
                # SWITCH GENERATION
                else:
                    if 'MS120-48' in model: rj45_count, sfp_count = 48, 4
                    else: rj45_count, sfp_count = 24, 4
                    
                    ports_html += "<div class='ports-wrapper'>"
                    rj45_columns = [(i, i+1) for i in range(1, rj45_count, 2)]
                    blocks = [rj45_columns[i:i+6] for i in range(0, len(rj45_columns), 6)]
                    
                    for block in blocks:
                        ports_html += "<div class='port-block'><div class='top-label'>PoE GbE</div><div class='port-group'>"
                        for top_p, bot_p in block:
                            ports_html += gen_column(top_p, bot_p)
                        ports_html += "</div></div>"
                    
                    if sfp_count > 0:
                        sfp_columns = [(i, i+1) for i in range(rj45_count + 1, rj45_count + sfp_count, 2)]
                        ports_html += "<div class='sfp-divider'></div>"
                        ports_html += "<div class='port-block'><div class='top-label'>SFP / SFP+</div><div class='port-group'>"
                        for top_p, bot_p in sfp_columns:
                            ports_html += gen_column(top_p, bot_p, "port sfp")
                        ports_html += "</div></div>"
                        
                    ports_html += "</div>"

                html_lines.append(f"<div class='{rack_class}'>")
                html_lines.append(ports_html)
                html_lines.append("</div>")

            # CUSTOM SHELF (U31)
            elif u == 31:
                html_lines.append("<div class='shelf-unit'>")
                
                html_lines.append("<div class='stack-container'>")
                html_lines.append("<div class='mac-mini' title='Apple Mac Mini'>MAC MINI</div>")
                
                ports_html = "<div class='unifi-ports'>"
                for i in range(8):
                    delay = f"style='--anim-delay: {random.uniform(0, 1):.2f}s;'"
                    ports_html += f"<div class='port active' {delay} title='UniFi RJ45 {i+1}'></div>"
                ports_html += "<div class='sfp-divider' style='height: 14px; margin-bottom: 0;'></div>"
                for i in range(2):
                    delay = f"style='--anim-delay: {random.uniform(0, 1):.2f}s;'"
                    ports_html += f"<div class='port sfp active' {delay} title='UniFi SFP+ {i+1}'></div>"
                ports_html += "</div>"
                
                html_lines.append(f"<div class='unifi-switch'><div class='unifi-logo' title='UniFi OS'></div>{ports_html}</div>")
                html_lines.append("</div>") 
                
                html_lines.append("<div class='cloud-key' title='UniFi Cloud Key Plus'>CLOUD KEY</div>")
                
                html_lines.append("</div>")

            # BLANKING PANEL
            else:
                html_lines.append("<div class='empty-slot'>[ BLANKING PANEL ]</div>")
                
        html_lines.append("</div>") # Close rack-cabinet
        
        # --- RIGHT COLUMN: TELEMETRY DATA ---
        html_lines.append("<div class='data-column'>")
        for u in range(42, 0, -1):
            if u in u_mapping:
                d = u_mapping[u]
                mac = d.get('mac', 'N/A')
                ip = d.get('lanIp', d.get('publicIp', '---.---.---.---'))
                status = d.get('status', 'offline').lower()
                color_class = "data-text" if status == 'online' else "data-text alert"
                
                html_lines.append("<div class='data-slot'>")
                html_lines.append(f"<span class='{color_class}'>MAC: {mac}</span>")
                html_lines.append(f"<span class='{color_class}'>IP:&nbsp;&nbsp;{ip}</span>")
                html_lines.append("</div>")
            elif u == 31: # UniFi shelf mock data
                html_lines.append("<div class='data-slot'>")
                html_lines.append("<span class='data-text'>MAC: A1:B2:C3:D4:E5</span>")
                html_lines.append("<span class='data-text'>IP:&nbsp;&nbsp;192.168.1.5</span>")
                html_lines.append("</div>")
            else:
                html_lines.append("<div class='data-slot'></div>")
        html_lines.append("</div>") # Close data-column
        
        html_lines.append("</div>") # Close rack-system-wrapper
        
        st.markdown("".join(html_lines), unsafe_allow_html=True)

    # JS TIMER INJECTION 
    js_code = """
    <script>
    const parentDoc = window.parent.document;
    const refreshIntervalMs = 60000;
    const scriptStartTimeMs = Date.now();

    setInterval(() => {
        const currentTime = Date.now();
        const elapsedSinceLoad = currentTime - scriptStartTimeMs;
        let remainingMs = refreshIntervalMs - elapsedSinceLoad;
        if (remainingMs <= 0) remainingMs = 0;
        
        const secondsUntilRefresh = Math.ceil(remainingMs / 1000);
        const refreshIcon = parentDoc.getElementById('refresh-icon');
        const refreshTimer = parentDoc.getElementById('refresh-timer');
        
        if (refreshIcon && refreshTimer) {
            if (secondsUntilRefresh <= 0) {
                refreshIcon.style.display = 'inline-block';
                refreshTimer.innerText = 'Refreshing...';
            } else {
                refreshIcon.style.display = 'none';
                refreshTimer.innerText = secondsUntilRefresh + 's';
            }
            if (secondsUntilRefresh <= 10 && secondsUntilRefresh > 0) refreshTimer.classList.add('refresh-alert');
            else refreshTimer.classList.remove('refresh-alert');
        }
    }, 1000);
    </script>
    """
    js_code = js_code.replace("SERVER_RENDER_TIME_VAL", str(int(current_pst.timestamp() * 1000)))
    components.html(js_code, height=0, width=0)

except Exception as e:
    st.error(f"Failed to fetch Meraki data: {e}")
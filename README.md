# 🌐 MDTV Intranet & Meraki NOC Dashboard
A professional-grade Network Operations Center (NOC) dashboard built with **Python**, **Streamlit**, and the **Meraki Dashboard API**. This project provides real-time monitoring and management for the Mater Dei TV network infrastructure.

## 🚀 Quick Start
To launch the dashboard from your terminal, run:

```bash
streamlit run DashBoardcode.py

✨ Key Features
Live Connectivity Status: Real-time monitoring of MX85 and MS120 hardware with dynamic 🟢/🔴 status indicators and infrastructure counts.

Smart State-Based Timers: * System Uptime: Automatically counts up from zero when the system is online.

System Downtime: A blinking red timer with a negative (-) prefix that triggers the moment the system drops offline.

Bandwidth Analytics: High-resolution graph showing the last 2 hours of Download and Upload traffic (MB) with interactive tooltips.

Traffic Insights: A compact breakdown of the Top 5 Applications by bandwidth consumption to identify high-usage services.

Remote Management: Integrated Reboot System button to trigger a hardware restart directly from the NOC interface.

Dual-Table Visibility: Paginated tables for both Network Infrastructure and Recent Connected Clients (including OS and switchport data).

Environmental Monitoring: Real-time weather, temperature, and humidity tracking for Chula Vista.

🔐 Security & Setup
This project uses Streamlit Secrets Management to ensure Meraki API keys are never exposed in the source code or on GitHub.

Create a folder named .streamlit in the root directory.

Inside that folder, create a file named secrets.toml.

Add your API key:

MERAKI_API_KEY = "your_api_key_here"

Ensure .streamlit/ is added to your .gitignore file.

🛠️ Tech Stack
Core: Python 3.11

Framework: Streamlit

API: Cisco Meraki SDK

Visuals: Altair & Pandas

Weather: wttr.in
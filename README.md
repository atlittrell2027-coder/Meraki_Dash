# 🌐 MDTV Intranet & Meraki NOC Dashboard

A professional, real-time Network Operations Center (NOC) dashboard built with **Python** and **Streamlit**. This dashboard is specifically designed to monitor a server rack containing a **Cisco Meraki MX85** and two **MS120-48LP** switches, providing live telemetry for bandwidth, hardware status, and client connectivity.

## 🚀 Features

-   **Live WAN Analytics:** Real-time Download/Upload metrics and a non-interactive area chart showing the last 2 hours of traffic.
-   **Infrastructure Status:** Instant health check for the MX85 and MS120 switches.
-   **Dynamic Health Score:** A custom-calculated percentage based on device uptime and status.
-   **Traffic Analysis:** Per-device traffic monitoring (in GB) sorted by the heaviest network users.
-   **Kiosk Optimized:** Auto-refreshing every 30 seconds with a full-width layout designed to fill a server rack monitor.
-   **Environmental Data:** Live Chula Vista weather, humidity, and PST clock integrated into the header.

## 🛠️ Tech Stack

-   **Language:** Python 3.x
-   **Framework:** [Streamlit](https://streamlit.io/)
-   **API:** [Cisco Meraki Dashboard API](https://developer.cisco.com/meraki/api-v1/)
-   **Visualization:** [Altair](https://altair-viz.github.io/) & Pandas
-   **Weather:** [wttr.in](https://wttr.in/)

## 🔐 Security & Setup

This project uses **Streamlit Secrets Management** to ensure Meraki API keys are never exposed in the source code or on GitHub.

### 1. Local Development (Codespaces)
1.  Create a folder named `.streamlit` in the root directory.
2.  Inside that folder, create a file named `secrets.toml`.
3.  Add your API key:
    ```toml
    MERAKI_API_KEY = "your_api_key_here"
    ```
4.  Ensure `.streamlit/` is added to your `.gitignore` file.

### 2. Installation
Run the following command to install the required dependencies:
```bash
pip install streamlit meraki pandas requests pytz streamlit-autorefresh altair
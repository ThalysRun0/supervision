import os
import yaml
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from parser import extract_logs, extract_protocol_connections, extract_proc, categorize_process, extract_power
from visualizer import generate_plot, generate_power_plot, generate_network_plot, generate_proc_plot

timestamp = datetime.now().strftime("%H:%M:%S")
st.session_state["trigger_reload"] = True
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

protocol_ports = config["networks"]["protocols"]
interfaces = config["networks"]["interfaces"]

st.set_page_config(page_title="Linux Analyse", layout="wide")

st.title("🪵 Logs and other Linux system analyze")

if "connexion_log" not in st.session_state:
    st.session_state["connexion_log"] = pd.DataFrame()

if "proc_log" not in st.session_state:
    st.session_state["proc_log"] = pd.DataFrame()

if "power_log" not in st.session_state:
    st.session_state["power_log"] = pd.DataFrame()

if "event_log" not in st.session_state:
    st.session_state["event_log"] = pd.DataFrame()

events_data = pd.DataFrame()
if st.session_state["trigger_reload"]:
#    print("EVENTS ---------------------------------------------------------------------------")
    events = extract_logs(config)
    if len(events) > 0:
        #st.session_state["event_log"] = pd.concat([st.session_state["event_log"], events], ignore_index=True) #.append({"timestamp": timestamp, "data": events})
        st.session_state["event_log"] = events
        #st.session_state["event_log"] = st.session_state["event_log"].tail(-20)
        events_data = st.session_state["event_log"]#[-1]['data']

connexions_data = pd.DataFrame()
if st.session_state["trigger_reload"]:
#    print("NETWORK ---------------------------------------------------------------------------")
    connexions = extract_protocol_connections(interfaces, protocol_ports)
    if len(connexions) > 0:
        #st.session_state["connexion_log"] = pd.concat([st.session_state["connexion_log"], connexions], ignore_index=True) #.append({"timestamp": timestamp, "data": connexions})
        st.session_state["connexion_log"] = connexions
        #st.session_state["connexion_log"] = st.session_state["connexion_log"].tail(-20)
        connexions_data = st.session_state["connexion_log"]#[-1]['data']
pids_with_ip = connexions_data["pid"].dropna().astype(int).unique()

procs_data = pd.DataFrame()
if st.session_state["trigger_reload"]:
#    print("NETWORK ---------------------------------------------------------------------------")
    procs = extract_proc()
    if len(procs) > 0:
        #st.session_state["proc_log"] = pd.concat([st.session_state["proc_log"], procs], ignore_index=True) #.append({"timestamp": timestamp, "data": connexions})
        st.session_state["proc_log"] = procs
        #st.session_state["proc_log"] = st.session_state["proc_log"].tail(-20)
        procs_data = st.session_state["proc_log"]#[-1]['data']

power_data = pd.DataFrame()
if st.session_state["trigger_reload"]:
#    print("POWER ---------------------------------------------------------------------------")
    power = extract_power()
    if power is not None:
        st.session_state["power_log"] = pd.concat([st.session_state["power_log"], power], ignore_index=True) #.append({"timestamp": timestamp, "data": power})
        #st.session_state["power_log"] = power
        st.session_state["power_log"] = st.session_state["power_log"].tail(20)
        power_data = st.session_state["power_log"]#[-1]['data']

col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
with col1:
    if st.button(label="Persist"):
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join("logs", f"rapport_{timestamp_str}.csv")
        events_data.sort_values("timestamp").to_csv(output_path, index=False)
        st.toast(f"✅ Saved report under : `{output_path}`")
        st.session_state["trigger_reload"] = True
    else:
        st.session_state["trigger_reload"] = False

    mode = st.radio(label="mode", options=["🌀 Live", "📂 Load past"], label_visibility="hidden")
    csv_files = sorted([f for f in os.listdir("logs") if f.startswith("rapport_") and f.endswith(".csv")], reverse=True)
    clicked_time = None

    if mode == "🌀 Live":
        refresh_interval = st.slider(label="⏱ Automatic refresh (minutes)", min_value=0, max_value=30, value=5)
        if refresh_interval > 0:
            count = st_autorefresh(interval=refresh_interval * 60 * 1000, key="auto-refresh")
            st.session_state["last_count"] = count
            if count > st.session_state["last_count"]:
                st.session_state["trigger_reload"] = True
                st.session_state["auto_refresh_trigger"] = True
                st.session_state["last_count"] = count  # Mise à jour de la valeur
            else:
                st.session_state["trigger_reload"] = False
        else:
            st.session_state["auto_refresh_trigger"] = False
    else:
        selected_file = st.selectbox("Select existing CSV file :", csv_files)
        if selected_file:
            events_data = pd.read_csv(os.path.join("logs", selected_file), parse_dates=["timestamp"])
        else:
            st.warning("No files found in folder 'logs/'")

with col2:
    with st.expander(f"⚡ CPU consumption (W) : {0 if power_data.empty else power_data.loc[:, 'watts'].iloc[-1]}", expanded=True):
        generate_power_plot(power_data)
#    with st.expander("Data statement", expanded=False):
#        tmp_data = st.session_state["power_log"]#[['data']].apply(pd.Series)[['data']]*
#        st.dataframe(tmp_data)

with col3:
    with st.expander(f"📡 Active connexions : {0 if connexions_data.empty else connexions_data.shape[0]}", expanded=True):
        generate_network_plot(connexions_data)
    with st.expander("List", expanded=False):
        st.dataframe(connexions_data)

with col4:
    with st.expander(f"🧠 Active processes : {0 if procs_data.empty else procs_data.shape[0]}", expanded=True):
        proc_threshold = st.slider("Threshold CPU/RAM intensivity %", 0, 100, 50)
        procs_data["category"] = procs_data.apply(
            lambda row: categorize_process(row, pids_with_ip, proc_threshold),
            axis=1
        )
        generate_proc_plot(procs_data)
    with st.expander("List", expanded=False):
        st.dataframe(procs_data)

if st.session_state.get("auto_refresh_trigger", False):
    st.session_state["trigger_reload"] = True
else:
    st.session_state["trigger_reload"] = False

if events_data.empty:
    st.warning("No weak signal detected")

with st.expander("🔍 Data filter", expanded=False):
    sources = st.multiselect("Sources", options=events_data["source"].unique(), default=list(events_data["source"].unique()))
    filtered_df = events_data[events_data["source"].isin(sources)]
    keywords = config["keywords"]
    keyword_filter = st.multiselect("Keywords", options=keywords, default=keywords)
    filtered_df = filtered_df[filtered_df["message"].str.contains('|'.join(keyword_filter), case=False)]

st.subheader("📊 Event Histogram")
generate_plot(filtered_df)
filtered_df = filtered_df[filtered_df["message"].str.contains('|'.join(keyword_filter), case=False)]

st.dataframe(filtered_df.sort_values("timestamp", ascending=False), use_container_width=True)

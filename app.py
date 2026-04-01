"""Streamlit dashboard for Oura Ring health metrics."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

from auth import get_auth_url, exchange_code_for_token, refresh_access_token, get_token, get_pat
from oura_client import OuraClient
from db import init_db, store_data, load_data, log_sync, get_last_sync, get_categories

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Health Metrics", page_icon="💤", layout="wide")
init_db()

# ---------------------------------------------------------------------------
# OAuth handling
# ---------------------------------------------------------------------------
query_params = st.query_params

# Handle OAuth callback (only needed when not using a PAT)
if not get_pat():
    if "code" in query_params:
        code = query_params["code"]
        try:
            token_data = exchange_code_for_token(code)
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Auth failed: {e}")
            st.stop()

    token = get_token()

    if token is None:
        st.title("Health Metrics")
        st.write("Connect your Oura Ring to get started.")
        auth_url = get_auth_url()
        st.link_button("Connect Oura Ring", auth_url)
        st.stop()


# ---------------------------------------------------------------------------
# Authenticated — sidebar controls
# ---------------------------------------------------------------------------
def get_client() -> OuraClient:
    """Get an OuraClient using a PAT or stored OAuth token."""
    pat = get_pat()
    if pat:
        return OuraClient(pat)
    t = get_token()
    try:
        client = OuraClient(t["access_token"])
        client._get("/personal_info")
        return client
    except Exception:
        new_token = refresh_access_token(t["refresh_token"])
        return OuraClient(new_token["access_token"])


# Date range selector
default_end = date.today()
default_start = default_end - timedelta(days=30)
start_date = st.sidebar.date_input("From", value=default_start)
end_date = st.sidebar.date_input("To", value=default_end)

# Sync button
if st.sidebar.button("Sync Data from Oura", type="primary"):
    with st.spinner("Fetching data from Oura..."):
        client = get_client()
        data = client.fetch_all(start_date=start_date, end_date=end_date)
        total = 0
        for category, records in data.items():
            count = store_data(category, records)
            total += count
        log_sync(start_date.isoformat(), end_date.isoformat())
    st.sidebar.success(f"Synced {total} records!")

last_sync = get_last_sync()
if last_sync:
    st.sidebar.caption(f"Last sync: {last_sync['synced_at']}")


# ---------------------------------------------------------------------------
# Helper to load data as DataFrame
# ---------------------------------------------------------------------------
def load_df(category: str) -> pd.DataFrame:
    records = load_data(category, start_date.isoformat(), end_date.isoformat())
    if not records:
        return pd.DataFrame()
    df = pd.json_normalize(records)
    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day")
    return df


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
st.title("Health Metrics")

categories = get_categories()

if not categories:
    st.info("No data yet. Use the **Sync Data from Oura** button in the sidebar to fetch your data.")
    st.stop()

# ---- Sleep Tab ----
tab_sleep, tab_activity, tab_readiness, tab_hr, tab_other = st.tabs(
    ["Sleep", "Activity", "Readiness", "Heart Rate", "Other"]
)

with tab_sleep:
    df_sleep = load_df("daily_sleep")
    if df_sleep.empty:
        st.info("No sleep data available for this period.")
    else:
        # Score over time
        if "score" in df_sleep.columns:
            st.subheader("Sleep Score")
            fig = px.scatter(df_sleep, x="day", y="score")
            fig.update_traces(marker_size=10)
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)

        # Key metrics in columns
        metric_cols = st.columns(4)
        for i, col_name in enumerate(["score", "contributors.deep_sleep", "contributors.efficiency", "contributors.total_sleep"]):
            if col_name in df_sleep.columns:
                label = col_name.replace("contributors.", "").replace("_", " ").title()
                latest = df_sleep[col_name].iloc[-1]
                avg = df_sleep[col_name].mean()
                metric_cols[i % 4].metric(label, f"{latest:.0f}", f"avg: {avg:.0f}")

    # Detailed sleep data
    df_sleep_detail = load_df("sleep")
    if not df_sleep_detail.empty:
        st.subheader("Sleep Stages")
        stage_cols = [c for c in df_sleep_detail.columns if c.startswith("sleep_phase_5_min")]
        duration_cols = ["deep_sleep_duration", "light_sleep_duration", "rem_sleep_duration", "awake_time"]
        available = [c for c in duration_cols if c in df_sleep_detail.columns]
        if available:
            if "bedtime_start" in df_sleep_detail.columns:
                df_sleep_detail["night"] = pd.to_datetime(df_sleep_detail["bedtime_start"]).dt.date
            elif "day" in df_sleep_detail.columns:
                df_sleep_detail["night"] = df_sleep_detail["day"]

            if "night" in df_sleep_detail.columns:
                # Convert seconds to hours
                for c in available:
                    df_sleep_detail[c + "_hrs"] = df_sleep_detail[c] / 3600

                hrs_cols = [c + "_hrs" for c in available]
                fig = px.bar(
                    df_sleep_detail,
                    x="night",
                    y=hrs_cols,
                    barmode="stack",
                    labels={"value": "Hours", "night": "Night"},
                )
                fig.update_layout(legend_title_text="Stage")
                st.plotly_chart(fig, use_container_width=True)

with tab_activity:
    df_activity = load_df("daily_activity")
    if df_activity.empty:
        st.info("No activity data available for this period.")
    else:
        if "score" in df_activity.columns:
            st.subheader("Activity Score")
            fig = px.scatter(df_activity, x="day", y="score")
            fig.update_traces(marker_size=10)
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)

        # Steps
        if "steps" in df_activity.columns:
            st.subheader("Daily Steps")
            fig = px.bar(df_activity, x="day", y="steps")
            st.plotly_chart(fig, use_container_width=True)

            cols = st.columns(3)
            cols[0].metric("Today", f"{df_activity['steps'].iloc[-1]:,.0f}")
            cols[1].metric("Average", f"{df_activity['steps'].mean():,.0f}")
            cols[2].metric("Max", f"{df_activity['steps'].max():,.0f}")

        # Calories
        cal_cols = [c for c in ["active_calories", "total_calories"] if c in df_activity.columns]
        if cal_cols:
            st.subheader("Calories")
            fig = px.scatter(df_activity, x="day", y=cal_cols)
            fig.update_traces(marker_size=8)
            st.plotly_chart(fig, use_container_width=True)

        # Movement breakdown
        move_cols = [c for c in ["high_activity_time", "medium_activity_time", "low_activity_time", "sedentary_time"] if c in df_activity.columns]
        if move_cols:
            st.subheader("Movement Breakdown")
            for c in move_cols:
                df_activity[c + "_min"] = df_activity[c] / 60
            min_cols = [c + "_min" for c in move_cols]
            fig = px.bar(df_activity, x="day", y=min_cols, barmode="stack", labels={"value": "Minutes"})
            st.plotly_chart(fig, use_container_width=True)

with tab_readiness:
    df_readiness = load_df("daily_readiness")
    if df_readiness.empty:
        st.info("No readiness data available for this period.")
    else:
        if "score" in df_readiness.columns:
            st.subheader("Readiness Score")
            fig = px.scatter(df_readiness, x="day", y="score")
            fig.update_traces(marker_size=10)
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)

            cols = st.columns(3)
            cols[0].metric("Today", f"{df_readiness['score'].iloc[-1]:.0f}")
            cols[1].metric("Average", f"{df_readiness['score'].mean():.0f}")
            cols[2].metric("Max", f"{df_readiness['score'].max():.0f}")

        # Contributors
        contrib_cols = [c for c in df_readiness.columns if c.startswith("contributors.")]
        if contrib_cols:
            st.subheader("Readiness Contributors (Latest)")
            latest = df_readiness.iloc[-1]
            contrib_data = {c.replace("contributors.", "").replace("_", " ").title(): latest[c] for c in contrib_cols if pd.notna(latest[c])}
            if contrib_data:
                fig = go.Figure(go.Bar(
                    x=list(contrib_data.values()),
                    y=list(contrib_data.keys()),
                    orientation="h",
                ))
                fig.update_layout(xaxis_range=[0, 100], height=400)
                st.plotly_chart(fig, use_container_width=True)

with tab_hr:
    df_hr = load_df("heartrate")
    if df_hr.empty:
        st.info("No heart rate data available for this period.")
    else:
        st.subheader("Heart Rate")
        if "timestamp" in df_hr.columns and "bpm" in df_hr.columns:
            df_hr["timestamp"] = pd.to_datetime(df_hr["timestamp"])
            fig = px.line(df_hr, x="timestamp", y="bpm")
            fig.update_layout(yaxis_title="BPM")
            st.plotly_chart(fig, use_container_width=True)

            cols = st.columns(3)
            cols[0].metric("Current", f"{df_hr['bpm'].iloc[-1]}")
            cols[1].metric("Average", f"{df_hr['bpm'].mean():.0f}")
            cols[2].metric("Resting (Min)", f"{df_hr['bpm'].min()}")

with tab_other:
    # SpO2
    df_spo2 = load_df("daily_spo2")
    if not df_spo2.empty:
        st.subheader("SpO2")
        spo2_col = "spo2_percentage.average" if "spo2_percentage.average" in df_spo2.columns else None
        if spo2_col:
            fig = px.scatter(df_spo2, x="day", y=spo2_col, labels={spo2_col: "SpO2 %"})
            fig.update_traces(marker_size=8)
            st.plotly_chart(fig, use_container_width=True)

    # Stress
    df_stress = load_df("daily_stress")
    if not df_stress.empty:
        st.subheader("Stress")
        stress_col = next((c for c in ["stress_high", "recovery_high", "day_summary"] if c in df_stress.columns), None)
        if stress_col:
            fig = px.scatter(df_stress, x="day", y=stress_col)
            fig.update_traces(marker_size=8)
            st.plotly_chart(fig, use_container_width=True)
        elif "day" in df_stress.columns:
            st.dataframe(df_stress, use_container_width=True)

    # Resilience
    df_resilience = load_df("daily_resilience")
    if not df_resilience.empty:
        st.subheader("Resilience")
        if "level" in df_resilience.columns:
            fig = px.scatter(df_resilience, x="day", y="level")
            fig.update_traces(marker_size=8)
            st.plotly_chart(fig, use_container_width=True)

    # Workouts
    df_workout = load_df("workout")
    if not df_workout.empty:
        st.subheader("Workouts")
        display_cols = [c for c in ["day", "activity", "calories", "intensity", "start_datetime", "end_datetime"] if c in df_workout.columns]
        if display_cols:
            st.dataframe(df_workout[display_cols], use_container_width=True)
        else:
            st.dataframe(df_workout, use_container_width=True)

    # Tags
    df_tags = load_df("tag")
    if not df_tags.empty:
        st.subheader("Tags")
        st.dataframe(df_tags, use_container_width=True)

    if df_spo2.empty and df_stress.empty and df_resilience.empty and df_workout.empty and df_tags.empty:
        st.info("No additional data available for this period.")

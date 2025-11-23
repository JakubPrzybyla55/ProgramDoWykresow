import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from utils import (
    parse_roasttime_csv,
    parse_profile_csv,
    calculate_ror,
    smooth_data,
    get_profiles,
    get_roast_files
)
from utils import parse_roasttime_csv, parse_profile_csv, calculate_ror, smooth_data

st.set_page_config(page_title="Coffee Roast Analyzer", layout="wide")

st.title("Coffee Roast Analyzer")

# --- Sidebar: Profile Selection ---
st.sidebar.header("Select Profile")

base_data_path = 'data'
profiles = get_profiles(base_data_path)

if not profiles:
    st.sidebar.warning(f"No profiles found in '{base_data_path}'. Please create folders.")
    st.stop()

selected_profile = st.sidebar.selectbox("Choose Coffee Profile", profiles)

# Get files for selected profile
plan_file_path, roast_files_paths = get_roast_files(selected_profile, base_data_path)

# --- Main Logic ---

if not plan_file_path:
    st.error(f"No Plan CSV found in '{selected_profile}/Plan'. Please add a CSV file.")
else:
    # Load Plan
    try:
        plan_df = parse_profile_csv(plan_file_path)
        st.success(f"Loaded Plan: {os.path.basename(plan_file_path)}")
    except Exception as e:
        st.error(f"Error loading plan: {e}")
        st.stop()

    # Select Roast
    st.sidebar.header("Select Roast (Empirical)")

    selected_roast_path = None
    if roast_files_paths:
        # Create a mapping for display names
        roast_options = {os.path.basename(p): p for p in roast_files_paths}
        selected_roast_name = st.sidebar.selectbox(
            "Choose Roast Data",
            list(roast_options.keys()),
            index=0
        )
        selected_roast_path = roast_options[selected_roast_name]
    else:
        st.sidebar.info("No roast files found in 'Wypały'.")

    # --- Visualization ---

    # Chart 1: Temperature & Profile
    fig_temp = go.Figure()

    # Plot Plan Points
    fig_temp.add_trace(go.Scatter(
        x=plan_df['Time_Seconds'],
        y=plan_df['Temperatura'],
        mode='markers+text',
        name='Plan Profile',
        text=plan_df['Faza'],
        textposition="top center",
        marker=dict(size=10, color='blue', symbol='x')
    ))

    actual_milestones = {}
    actual_df = pd.DataFrame()

    if selected_roast_path:
        try:
            actual_df, actual_milestones = parse_roasttime_csv(selected_roast_path)

            # Processing
            actual_df = calculate_ror(actual_df, window_seconds=10)
            actual_df['Calc_RoR_Smooth'] = smooth_data(actual_df['Calc_RoR'], window=15)

            # Plot Actual Temp
            fig_temp.add_trace(go.Scatter(
                x=actual_df['Time_Seconds'],
                y=actual_df['IBTS Temp'],
                mode='lines',
                name=f'Actual: {os.path.basename(selected_roast_path)}',
                line=dict(color='firebrick', width=2)
            ))

            # Add Actual Milestones
            for name, time_sec in actual_milestones.items():
                row = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
                if not row.empty:
                    temp_val = row['IBTS Temp'].values[0]
                    fig_temp.add_trace(go.Scatter(
                        x=[time_sec],
                        y=[temp_val],
                        mode='markers',
                        name=f'Actual {name}',
                        marker=dict(size=10, color='green', symbol='circle-open')
                    ))

        except Exception as e:
            st.error(f"Error loading roast file: {e}")

    fig_temp.update_layout(
        title=f"Profile: {selected_profile}",
        xaxis_title="Time (seconds)",
        yaxis_title="Temperature (°C)",
        hovermode="x unified"
    )
    st.plotly_chart(fig_temp, use_container_width=True)

    # Chart 2: RoR (Only if roast is loaded)
    if not actual_df.empty:
        fig_ror = go.Figure()

st.sidebar.header("Upload Files")
profile_file = st.sidebar.file_uploader("Upload Profile (Plan) CSV", type=['csv'])
roast_file = st.sidebar.file_uploader("Upload RoastTime (Empirical) CSV", type=['csv'])

if profile_file and roast_file:
    try:
        # --- Processing ---
        st.write("Processing files...")

        # 1. Parse Data
        plan_df = parse_profile_csv(profile_file)
        actual_df, actual_milestones = parse_roasttime_csv(roast_file)

        # 2. Calculate RoR for Empirical Data
        # User requested 10s window for calculation
        actual_df = calculate_ror(actual_df, window_seconds=10)

        # 3. Smooth RoR
        # User requested smoothing ("redukcja szumów")
        # Apply smoothing to the calculated RoR
        actual_df['Calc_RoR_Smooth'] = smooth_data(actual_df['Calc_RoR'], window=15) # 15s window for smoothing

        # Also smooth the IBTS ROR from file if needed, or just use as is.
        # User said: "Calculated RoR in addition to the one from program".

        # --- Visualization ---

        # Chart 1: Temperature & Profile
        fig_temp = go.Figure()

        # Plot Actual Temp
        fig_temp.add_trace(go.Scatter(
            x=actual_df['Time_Seconds'],
            y=actual_df['IBTS Temp'],
            mode='lines',
            name='Actual Temp (IBTS)',
            line=dict(color='firebrick', width=2)
        ))

        # Plot Plan Points
        fig_temp.add_trace(go.Scatter(
            x=plan_df['Time_Seconds'],
            y=plan_df['Temperatura'],
            mode='markers+text',
            name='Plan Profile',
            text=plan_df['Faza'],
            textposition="top center",
            marker=dict(size=10, color='blue', symbol='x')
        ))

        # Add Actual Milestones if found (Vertical Lines or Points)
        # We can try to map them to the temperature at that time
        milestone_annotations = []
        for name, time_sec in actual_milestones.items():
            # Find temp at this time
            row = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
            if not row.empty:
                temp_val = row['IBTS Temp'].values[0]
                fig_temp.add_trace(go.Scatter(
                    x=[time_sec],
                    y=[temp_val],
                    mode='markers',
                    name=f'Actual {name}',
                    marker=dict(size=10, color='green', symbol='circle-open')
                ))

        fig_temp.update_layout(
            title="Temperature Curve: Plan vs Actual",
            xaxis_title="Time (seconds)",
            yaxis_title="Temperature (°C)",
            hovermode="x unified"
        )
        st.plotly_chart(fig_temp, use_container_width=True)

        # Chart 2: RoR
        fig_ror = go.Figure()

        # Plot File RoR
        if 'IBTS ROR' in actual_df.columns:
            fig_ror.add_trace(go.Scatter(
                x=actual_df['Time_Seconds'],
                y=actual_df['IBTS ROR'],
                mode='lines',
                name='File RoR (IBTS)',
                line=dict(color='lightgray', dash='dot')
            ))

        # Plot Calculated & Smoothed RoR
        fig_ror.add_trace(go.Scatter(
            x=actual_df['Time_Seconds'],
            y=actual_df['Calc_RoR_Smooth'],
            mode='lines',
            name='Calculated RoR (Smoothed)',
            line=dict(color='orange', width=2)
        ))

        fig_ror.update_layout(
            title="Rate of Rise (RoR)",
            xaxis_title="Time (seconds)",
            yaxis_title="RoR (°C/min)",
            hovermode="x unified"
        )
        st.plotly_chart(fig_ror, use_container_width=True)

        # --- Analysis ---
        st.header("Analysis")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Plan vs Actual")
            comparison_data = []

            for index, row in plan_df.iterrows():
                phase_name = row['Faza']
                plan_time = row['Time_Seconds']
                plan_temp = row['Temperatura']

                actual_time = None
                actual_temp = None

                matched_key = None
                for key in actual_milestones:
                    if key.lower() in phase_name.lower() or phase_name.lower() in key.lower():
                        matched_key = key
                        break

                if matched_key:
                    actual_time = actual_milestones[matched_key]
                    r = actual_df.iloc[(actual_df['Time_Seconds'] - actual_time).abs().argsort()[:1]]
                    if not r.empty:
                        actual_temp = r['IBTS Temp'].values[0]

                p_time_str = f"{int(plan_time//60)}:{int(plan_time%60):02d}"
                a_time_str = f"{int(actual_time//60)}:{int(actual_time%60):02d}" if actual_time is not None else "-"

                comparison_data.append({
                    "Phase": phase_name,
                    "Plan Time": p_time_str,
                    "Plan Temp": plan_temp,
                    "Actual Time": a_time_str,
                    "Actual Temp": round(actual_temp, 1) if actual_temp else "-",
                })

            st.table(pd.DataFrame(comparison_data))

        with col2:
            st.subheader("Phase Metrics")
            ror_metrics = []
            for name, time_sec in actual_milestones.items():
                r = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
                if not r.empty:
                    ror_val = r['Calc_RoR_Smooth'].values[0]
                    ror_metrics.append({
                        "Event": name,
                        "RoR (Smoothed)": round(ror_val, 2)
                    })
            st.table(pd.DataFrame(ror_metrics))

            if 'Yellowing' in actual_milestones and '1st Crack' in actual_milestones:
                t_y = actual_milestones['Yellowing']
                t_fc = actual_milestones['1st Crack']

                r_y = actual_df.iloc[(actual_df['Time_Seconds'] - t_y).abs().argsort()[:1]]['Calc_RoR_Smooth'].values[0]
                r_fc = actual_df.iloc[(actual_df['Time_Seconds'] - t_fc).abs().argsort()[:1]]['Calc_RoR_Smooth'].values[0]

                st.info(f"**Maillard Phase RoR:** {round(r_y, 1)} -> {round(r_fc, 1)} °C/min")
        # --- Analysis & Metrics ---
        st.header("Analysis")

        # 1. Comparison Table
        st.subheader("Plan vs Actual Comparison")

        comparison_data = []

        for index, row in plan_df.iterrows():
            phase_name = row['Faza'] # e.g. "Yellowing End" or "1st Crack"
            plan_time = row['Time_Seconds']
            plan_temp = row['Temperatura']

            actual_time = None
            actual_temp = None

            # Try to match with parsed milestones
            # Need fuzzy matching or standard naming?
            # User profile names: "1st Crack", "Yellowing End"
            # Actual milestones: "1st Crack", "Yellowing" (which is usually start)

            matched_key = None
            for key in actual_milestones:
                if key.lower() in phase_name.lower() or phase_name.lower() in key.lower():
                    # Special logic for Yellowing
                    # If Plan is "Yellowing End" and Actual is "Yellowing" (Start), they don't match directly.
                    # But let's assume loose matching for now.
                    matched_key = key
                    break

            if matched_key:
                actual_time = actual_milestones[matched_key]
                # Get temp at this time
                r = actual_df.iloc[(actual_df['Time_Seconds'] - actual_time).abs().argsort()[:1]]
                if not r.empty:
                    actual_temp = r['IBTS Temp'].values[0]

            # Formatting
            p_time_str = f"{int(plan_time//60)}:{int(plan_time%60):02d}"
            a_time_str = f"{int(actual_time//60)}:{int(actual_time%60):02d}" if actual_time is not None else "-"

            diff_time = round(actual_time - plan_time, 1) if actual_time is not None else None
            diff_temp = round(actual_temp - plan_temp, 1) if actual_temp is not None else None

            comparison_data.append({
                "Phase": phase_name,
                "Plan Time": p_time_str,
                "Plan Temp": plan_temp,
                "Actual Time": a_time_str,
                "Actual Temp": round(actual_temp, 1) if actual_temp else "-",
                "Diff Time (s)": diff_time,
                "Diff Temp (°C)": diff_temp
            })

        st.table(pd.DataFrame(comparison_data))

        # 2. RoR Phase Analysis
        st.subheader("Phase RoR Analysis")
        # Calculate RoR at key actual milestones

        ror_metrics = []
        for name, time_sec in actual_milestones.items():
            # Find RoR at this time
            r = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
            if not r.empty:
                ror_val = r['Calc_RoR_Smooth'].values[0]
                ror_metrics.append({
                    "Event": name,
                    "Time": f"{int(time_sec//60)}:{int(time_sec%60):02d}",
                    "RoR (Smoothed)": round(ror_val, 2)
                })

        st.write("RoR values at Actual Events:")
        st.table(pd.DataFrame(ror_metrics))

        # Custom Logic: Yellowing -> 1st Crack RoR drop
        if 'Yellowing' in actual_milestones and '1st Crack' in actual_milestones:
            t_y = actual_milestones['Yellowing']
            t_fc = actual_milestones['1st Crack']

            r_y = actual_df.iloc[(actual_df['Time_Seconds'] - t_y).abs().argsort()[:1]]['Calc_RoR_Smooth'].values[0]
            r_fc = actual_df.iloc[(actual_df['Time_Seconds'] - t_fc).abs().argsort()[:1]]['Calc_RoR_Smooth'].values[0]

            st.info(f"**Maillard Phase RoR Change (Yellowing -> 1st Crack):** {round(r_y, 1)} -> {round(r_fc, 1)} °C/min")

    except Exception as e:
        st.error(f"Error processing files: {e}")
        import traceback
        st.text(traceback.format_exc())
else:
    st.info("Please upload both CSV files to begin.")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from utils import (
    parse_roasttime_csv,
    parse_profile_csv,
    calculate_ror,
    calculate_ror_sg,
    smooth_data,
    get_profiles,
    get_roast_files,
    SCIPY_AVAILABLE
)

st.set_page_config(page_title="Analizator Wypału Kawy", layout="wide")

st.title("Analizator Wypału Kawy")

# --- Sidebar: Wybór Profilu ---
st.sidebar.header("Wybierz Profil")

base_data_path = 'data'
profiles = get_profiles(base_data_path)

if not profiles:
    st.sidebar.warning(f"Nie znaleziono profili w '{base_data_path}'. Proszę utworzyć foldery.")
    st.stop()

selected_profile = st.sidebar.selectbox("Wybierz Profil Kawy", profiles)

# Pobierz pliki dla wybranego profilu
plan_file_path, roast_files_paths = get_roast_files(selected_profile, base_data_path)

# --- Główna Logika ---

if not plan_file_path:
    st.error(f"Nie znaleziono pliku Planu CSV w '{selected_profile}/Plan'. Dodaj plik CSV.")
else:
    # Wczytaj Plan
    try:
        plan_df = parse_profile_csv(plan_file_path)
        st.success(f"Wczytano Plan: {os.path.basename(plan_file_path)}")
    except Exception as e:
        st.error(f"Błąd wczytywania planu: {e}")
        st.stop()

    # Wybór Wypału
    st.sidebar.header("Wybierz Wypał (Rzeczywisty)")

    selected_roast_path = None
    if roast_files_paths:
        # Tworzenie mapowania nazw do wyświetlenia
        roast_options = {os.path.basename(p): p for p in roast_files_paths}

        # Funkcja formatująca do skracania długich nazw w selectbox
        def format_filename(filename):
            max_len = 30
            if len(filename) > max_len:
                return "..." + filename[-(max_len-3):]
            return filename

        selected_roast_name = st.sidebar.selectbox(
            "Wybierz Dane Wypału",
            list(roast_options.keys()),
            index=0,
            format_func=format_filename
        )
        selected_roast_path = roast_options[selected_roast_name]
    else:
        st.sidebar.info("Brak plików wypałów w folderze 'Wypały'.")

    st.sidebar.markdown("---")

    # --- Sekcja Widoczności Danych ---
    st.sidebar.header("Widoczność Danych")
    show_plan = st.sidebar.checkbox("Pokaż Plan", value=True)
    show_ibts = st.sidebar.checkbox("Pokaż IBTS (Temp/RoR)", value=True)
    show_probe = st.sidebar.checkbox("Pokaż Sondę (Temp/RoR)", value=True)

    st.sidebar.markdown("---")

    # --- Ustawienia RoR ---
    st.sidebar.header("Ustawienia RoR")

    if not SCIPY_AVAILABLE:
         st.sidebar.warning("Metoda Savitzky-Golay jest niedostępna (brak pakietu scipy).")

    method_options = ['Średnia Ruchoma']
    if SCIPY_AVAILABLE:
        method_options.append('Savitzky-Golay')

    # --- Ustawienia IBTS ---
    st.sidebar.subheader("IBTS")
    ror_method_ibts = st.sidebar.radio(
        "Metoda (IBTS)",
        method_options,
        index=0,
        key="ror_method_ibts"
    )

    ibts_params = {}
    if ror_method_ibts == 'Średnia Ruchoma':
        window_sec = st.sidebar.number_input("Okno Wygładzania (sek) - IBTS", min_value=1, max_value=60, value=15, key="ibts_ma_win")
        ibts_params['window_sec'] = window_sec
    elif ror_method_ibts == 'Savitzky-Golay':
        sg_window = st.sidebar.number_input("Okno SG - IBTS", min_value=3, max_value=99, value=15, step=2, key="ibts_sg_win")
        sg_poly = st.sidebar.number_input("Rząd wielomianu - IBTS", min_value=1, max_value=5, value=2, key="ibts_sg_poly")
        sg_deriv = st.sidebar.number_input("Rząd pochodnej - IBTS", min_value=1, max_value=3, value=1, key="ibts_sg_deriv")
        if sg_window % 2 == 0:
            sg_window += 1
        ibts_params['sg_window'] = sg_window
        ibts_params['sg_poly'] = sg_poly
        ibts_params['sg_deriv'] = sg_deriv

    # --- Ustawienia Sondy (Probe) ---
    st.sidebar.subheader("Sonda")
    ror_method_probe = st.sidebar.radio(
        "Metoda (Sonda)",
        method_options,
        index=0,
        key="ror_method_probe"
    )

    probe_params = {}
    if ror_method_probe == 'Średnia Ruchoma':
        window_sec = st.sidebar.number_input("Okno Wygładzania (sek) - Sonda", min_value=1, max_value=60, value=15, key="probe_ma_win")
        probe_params['window_sec'] = window_sec
    elif ror_method_probe == 'Savitzky-Golay':
        sg_window = st.sidebar.number_input("Okno SG - Sonda", min_value=3, max_value=99, value=15, step=2, key="probe_sg_win")
        sg_poly = st.sidebar.number_input("Rząd wielomianu - Sonda", min_value=1, max_value=5, value=2, key="probe_sg_poly")
        sg_deriv = st.sidebar.number_input("Rząd pochodnej - Sonda", min_value=1, max_value=3, value=1, key="probe_sg_deriv")
        if sg_window % 2 == 0:
            sg_window += 1
        probe_params['sg_window'] = sg_window
        probe_params['sg_poly'] = sg_poly
        probe_params['sg_deriv'] = sg_deriv

    # --- Limity Osi ---
    st.sidebar.markdown("---")
    st.sidebar.header("Ustawienia Wykresów")

    st.sidebar.subheader("Zakres osi RoR")
    col_ror_min, col_ror_max = st.sidebar.columns(2)
    ror_y_min = col_ror_min.number_input("Min RoR", value=-5)
    ror_y_max = col_ror_max.number_input("Max RoR", value=35)

    st.sidebar.subheader("Zakres osi Ustawień (Moc/Nawiew)")
    col_set_min, col_set_max = st.sidebar.columns(2)
    settings_y_min = col_set_min.number_input("Min", value=0)
    settings_y_max = col_set_max.number_input("Max", value=9)

    # --- Przetwarzanie Danych ---

    # Przygotowanie danych rzeczywistych
    actual_milestones = {}
    actual_df = pd.DataFrame()

    if selected_roast_path:
        try:
            actual_df, actual_milestones = parse_roasttime_csv(selected_roast_path)

            # Oblicz średni interwał próbkowania, aby przeliczyć sekundy na liczbę próbek dla wygładzania
            avg_interval = 1.0
            if not actual_df.empty and 'Time_Seconds' in actual_df.columns:
                 diffs = actual_df['Time_Seconds'].diff()
                 avg_interval = diffs.median()
                 if pd.isna(avg_interval) or avg_interval <= 0:
                     avg_interval = 1.0

            # --- Obliczenia RoR IBTS ---
            if 'IBTS Temp' in actual_df.columns:
                if ror_method_ibts == 'Średnia Ruchoma':
                    # Calculate raw point-to-point RoR
                    actual_df = calculate_ror(actual_df, temp_col='IBTS Temp', time_col='Time_Seconds')
                    base_ror_col = 'Calc_RoR'
                    if base_ror_col in actual_df.columns:
                        # Convert window seconds to samples
                        smooth_samples = max(1, int(ibts_params['window_sec'] / avg_interval))
                        actual_df['RoR_Display'] = smooth_data(actual_df[base_ror_col], window=smooth_samples)
                else:
                    actual_df = calculate_ror_sg(actual_df, temp_col='IBTS Temp',
                                                 window_length=ibts_params['sg_window'],
                                                 polyorder=ibts_params['sg_poly'],
                                                 deriv=ibts_params['sg_deriv'])
                    base_ror_col = 'Calc_RoR_SG'
                    if base_ror_col in actual_df.columns:
                        actual_df['RoR_Display'] = actual_df[base_ror_col]

            # --- Obliczenia RoR Probe ---
            if 'Bean Probe Temp' in actual_df.columns:
                if ror_method_probe == 'Średnia Ruchoma':
                    actual_df = calculate_ror(actual_df, temp_col='Bean Probe Temp', time_col='Time_Seconds')
                    base_ror_col = 'Calc_RoR_Probe'
                    if base_ror_col in actual_df.columns:
                        smooth_samples = max(1, int(probe_params['window_sec'] / avg_interval))
                        actual_df['RoR_Display_Probe'] = smooth_data(actual_df[base_ror_col], window=smooth_samples)
                else:
                    actual_df = calculate_ror_sg(actual_df, temp_col='Bean Probe Temp',
                                                 window_length=probe_params['sg_window'],
                                                 polyorder=probe_params['sg_poly'],
                                                 deriv=probe_params['sg_deriv'])
                    base_ror_col = 'Calc_RoR_SG_Probe'
                    if base_ror_col in actual_df.columns:
                        actual_df['RoR_Display_Probe'] = actual_df[base_ror_col]

        except Exception as e:
            st.error(f"Błąd wczytywania pliku wypału: {e}")
            import traceback
            traceback.print_exc()

    # --- Wizualizacja ---

    def add_l_projection(fig, x_val, y_val, color, row=1, col=1, is_time_x=True, show_y=True, show_x=True, text_offset_y=0):
        y_axis_name = f"y{row}" if row > 1 else "y"
        x_axis_name = f"x{col}" if col > 1 else "x"
        yref_domain = f"{y_axis_name} domain"
        xref_domain = f"{x_axis_name} domain"

        if y_val is None:
             fig.add_vline(x=x_val, line_width=1, line_dash="dash", line_color=color, opacity=0.5, row=row, col=col)
        else:
            fig.add_shape(type="line",
                x0=x_val, y0=0, x1=x_val, y1=y_val,
                line=dict(color=color, width=1, dash="dash"),
                row=row, col=col
            )
            if show_y:
                 fig.add_shape(type="line",
                    x0=0, y0=y_val, x1=x_val, y1=y_val,
                    line=dict(color=color, width=1, dash="dash"),
                    row=row, col=col
                )

        if show_x:
            x_text = f"{int(x_val//60)}:{int(x_val%60):02d}" if is_time_x else f"{x_val:.1f}"
            fig.add_annotation(
                x=x_val, y=0,
                xref=x_axis_name, yref=yref_domain,
                text=x_text,
                showarrow=False,
                font=dict(size=10, color=color),
                yshift=-15,
                bgcolor="rgba(0,0,0,0.5)"
            )

        if show_y and y_val is not None:
            fig.add_annotation(
                x=0, y=y_val,
                xref=xref_domain, yref=y_axis_name,
                text=f"{y_val:.1f}",
                showarrow=False,
                font=dict(size=10, color=color),
                xshift=-25,
                xanchor="right",
                bgcolor="rgba(0,0,0,0.5)"
            )

    def add_settings_subplot(fig_main, row_idx=2):
        # Actual
        if not actual_df.empty:
            if 'Fan' in actual_df.columns:
                 fig_main.add_trace(go.Scatter(
                    x=actual_df['Time_Seconds'], y=actual_df['Fan'],
                    name='Rzecz. Nawiew', line_shape='hv',
                    line=dict(color='cornflowerblue', width=2),
                    legendgroup='settings'
                ), row=row_idx, col=1)
            if 'Power' in actual_df.columns:
                 fig_main.add_trace(go.Scatter(
                    x=actual_df['Time_Seconds'], y=actual_df['Power'],
                    name='Rzecz. Moc', line_shape='hv',
                    line=dict(color='mediumpurple', width=2),
                    legendgroup='settings'
                ), row=row_idx, col=1)

        # Plan (Markers)
        if show_plan:
            if 'Nawiew' in plan_df.columns:
                 fig_main.add_trace(go.Scatter(
                    x=plan_df['Time_Seconds'], y=plan_df['Nawiew'],
                    mode='markers+text', name='Plan Nawiew',
                    text=plan_df['Nawiew'], textposition="top center",
                    marker=dict(color='cyan', symbol='triangle-up'),
                    legendgroup='settings'
                ), row=row_idx, col=1)

            if 'Moc' in plan_df.columns:
                 fig_main.add_trace(go.Scatter(
                    x=plan_df['Time_Seconds'], y=plan_df['Moc'],
                    mode='markers+text', name='Plan Moc',
                    text=plan_df['Moc'], textposition="bottom center",
                    marker=dict(color='magenta', symbol='triangle-down'),
                    legendgroup='settings'
                ), row=row_idx, col=1)

    # Sort plan by time
    plan_df_sorted = plan_df.sort_values('Time_Seconds')

    # ==========================
    # FIGURE 1: TEMPERATURE
    # ==========================

    fig_temp = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.75, 0.25],
        subplot_titles=(f"Profil Temperatury: {selected_profile}", "Ustawienia")
    )

    # --- Row 1: Temp ---

    # Plan Points
    if show_plan:
        for i, row in plan_df_sorted.iterrows():
            pos = "top center" if i % 2 == 0 else "bottom center"

            fig_temp.add_trace(go.Scatter(
                x=[row['Time_Seconds']],
                y=[row['Temperatura']],
                mode='markers+text',
                name='Plan',
                text=[row['Faza']],
                textposition=pos,
                marker=dict(size=12, color='cyan', symbol='x'),
                showlegend=(i==0)
            ), row=1, col=1)

            add_l_projection(fig_temp, row['Time_Seconds'], row['Temperatura'], 'cyan', row=1)

    # Actual Traces
    if not actual_df.empty:
        # IBTS
        if show_ibts:
            fig_temp.add_trace(go.Scatter(
                x=actual_df['Time_Seconds'],
                y=actual_df['IBTS Temp'],
                mode='lines',
                name='Rzecz. IBTS',
                line=dict(color='orange', width=2)
            ), row=1, col=1)

        # Probe
        if show_probe and 'Bean Probe Temp' in actual_df.columns:
            fig_temp.add_trace(go.Scatter(
                x=actual_df['Time_Seconds'],
                y=actual_df['Bean Probe Temp'],
                mode='lines',
                name='Rzecz. Sonda',
                line=dict(color='lightgreen', width=2, dash='dot')
            ), row=1, col=1)

        # Milestones (Actual)
        sorted_milestones = sorted(actual_milestones.items(), key=lambda x: x[1])
        for i, (name, time_sec) in enumerate(sorted_milestones):
            row = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
            if not row.empty:
                temp_val = row['IBTS Temp'].values[0] # Kamienie milowe zazwyczaj na IBTS

                offset_y = 0
                if i > 0:
                    prev_time = sorted_milestones[i-1][1]
                    if (time_sec - prev_time) < 30:
                        offset_y = 20 if (i % 2 != 0) else 0

                fig_temp.add_trace(go.Scatter(
                    x=[time_sec],
                    y=[temp_val],
                    mode='markers',
                    name=f'{name}',
                    marker=dict(size=10, color='red', symbol='circle-open'),
                    showlegend=False
                ), row=1, col=1)

                fig_temp.add_annotation(
                    x=time_sec, y=temp_val,
                    text=name,
                    showarrow=True,
                    arrowhead=1,
                    yshift=15 + offset_y if i%2==0 else -15 - offset_y,
                    font=dict(color='red'),
                    row=1, col=1
                )

                add_l_projection(fig_temp, time_sec, temp_val, 'red', row=1)

    # --- Row 2: Settings ---
    add_settings_subplot(fig_temp, row_idx=2)

    fig_temp.update_layout(
        template="plotly_dark",
        height=700,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig_temp.update_yaxes(title_text="Temperatura (°C)", row=1, col=1)
    fig_temp.update_yaxes(title_text="Wartość", range=[settings_y_min, settings_y_max], dtick=1, row=2, col=1)
    fig_temp.update_xaxes(title_text="Czas (sekundy)", row=2, col=1)

    st.plotly_chart(fig_temp, use_container_width=True)


    # ==========================
    # FIGURE 2: RoR
    # ==========================
    if not actual_df.empty:
        fig_ror = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            row_heights=[0.75, 0.25],
            subplot_titles=("RoR (Szybkość Wzrostu)", "Ustawienia")
        )

        # IBTS RoR
        if show_ibts and 'RoR_Display' in actual_df.columns:
            fig_ror.add_trace(go.Scatter(
                x=actual_df['Time_Seconds'],
                y=actual_df['RoR_Display'],
                mode='lines',
                name='RoR IBTS',
                line=dict(color='magenta', width=2)
            ), row=1, col=1)

        # Probe RoR
        if show_probe and 'RoR_Display_Probe' in actual_df.columns:
            fig_ror.add_trace(go.Scatter(
                x=actual_df['Time_Seconds'],
                y=actual_df['RoR_Display_Probe'],
                mode='lines',
                name='RoR Sonda',
                line=dict(color='mediumspringgreen', width=2, dash='dot')
            ), row=1, col=1)

        # Plan Projections (Time only)
        if show_plan:
            for _, row in plan_df_sorted.iterrows():
                 add_l_projection(fig_ror, row['Time_Seconds'], None, 'cyan', row=1, show_y=False)

        # Actual Milestones
        for name, time_sec in actual_milestones.items():
             # Szukamy RoR w tym czasie
             if 'RoR_Display' in actual_df.columns:
                row_actual = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
                if not row_actual.empty:
                     ror_val = row_actual['RoR_Display'].values[0]

                     if pd.notna(ror_val):
                         fig_ror.add_trace(go.Scatter(
                            x=[time_sec], y=[ror_val],
                            mode='markers', name=name,
                            marker=dict(size=8, color='red', symbol='circle-open'),
                            showlegend=False
                         ), row=1, col=1)

                         fig_ror.add_annotation(
                            x=time_sec, y=ror_val,
                            text=name, showarrow=False,
                            yshift=10, font=dict(color='red', size=9),
                            row=1, col=1
                         )
                         add_l_projection(fig_ror, time_sec, ror_val, 'red', row=1)
                     else:
                         add_l_projection(fig_ror, time_sec, None, 'red', row=1, show_y=False)
             else:
                 add_l_projection(fig_ror, time_sec, None, 'red', row=1, show_y=False)

        # Settings
        add_settings_subplot(fig_ror, row_idx=2)

        fig_ror.update_layout(
            template="plotly_dark",
            height=600,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig_ror.update_yaxes(title_text="RoR (°C/min)", range=[ror_y_min, ror_y_max], row=1, col=1)
        fig_ror.update_yaxes(title_text="Wartość", range=[settings_y_min, settings_y_max], dtick=1, row=2, col=1)
        fig_ror.update_xaxes(title_text="Czas (sekundy)", row=2, col=1)

        st.plotly_chart(fig_ror, use_container_width=True)

        # --- Analiza (Tables) ---
        st.header("Analiza")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Plan vs Rzeczywistość")
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

                if "start" in phase_name.lower() and 0 not in actual_milestones.values():
                     actual_time = 0.0
                     matched_key = "Start"
                elif matched_key:
                    actual_time = actual_milestones[matched_key]

                if actual_time is not None:
                    r = actual_df.iloc[(actual_df['Time_Seconds'] - actual_time).abs().argsort()[:1]]
                    if not r.empty:
                        actual_temp = r['IBTS Temp'].values[0]

                p_time_str = f"{int(plan_time//60)}:{int(plan_time%60):02d}"
                a_time_str = f"{int(actual_time//60)}:{int(actual_time%60):02d}" if actual_time is not None else "-"

                comparison_data.append({
                    "Faza": phase_name,
                    "Plan Czas": p_time_str,
                    "Plan Temp": plan_temp,
                    "Rzecz. Czas": a_time_str,
                    "Rzecz. Temp": round(actual_temp, 1) if actual_temp else "-",
                })

            st.table(pd.DataFrame(comparison_data))

        with col2:
            st.subheader("Metryki Faz (Średni RoR)")

            key_events = {k: v for k, v in actual_milestones.items()}

            if 'Turning Point' not in key_events:
                 try:
                    early_df = actual_df[actual_df['Time_Seconds'] < 180]
                    if not early_df.empty:
                        temp_col = 'IBTS Temp'
                        if 'Bean Probe Temp' in actual_df.columns:
                            temp_col = 'Bean Probe Temp'

                        if temp_col in early_df.columns:
                            min_idx = early_df[temp_col].idxmin()
                            tp_time = early_df.loc[min_idx, 'Time_Seconds']
                            key_events['Turning Point'] = tp_time
                 except:
                    pass

            key_events['Start'] = 0.0

            if 'Drop' not in key_events:
                 key_events['Drop'] = actual_df['Time_Seconds'].max()

            sorted_events = sorted(key_events.items(), key=lambda x: x[1])
            phase_metrics = []

            for i in range(len(sorted_events) - 1):
                start_name, start_time = sorted_events[i]
                end_name, end_time = sorted_events[i+1]

                if end_time - start_time < 10:
                    continue

                mask = (actual_df['Time_Seconds'] >= start_time) & (actual_df['Time_Seconds'] <= end_time)
                phase_data = actual_df.loc[mask]

                if not phase_data.empty and 'RoR_Display' in phase_data:
                    avg_ror = phase_data['RoR_Display'].mean()
                    phase_metrics.append({
                        "Faza": f"{start_name} -> {end_name}",
                        "Średni RoR": round(avg_ror, 2)
                    })

            st.table(pd.DataFrame(phase_metrics))

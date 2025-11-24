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

    # --- Ustawienia Wykresów i RoR ---
    st.sidebar.markdown("---")
    st.sidebar.header("Ustawienia Wykresów")

    # Wybór metody obliczania RoR
    method_options = ['Średnia Ruchoma']
    if SCIPY_AVAILABLE:
        method_options.append('Savitzky-Golay')

    ror_method = st.sidebar.radio(
        "Metoda obliczania RoR",
        method_options,
        index=0
    )

    if not SCIPY_AVAILABLE:
         st.sidebar.warning("Metoda Savitzky-Golay jest niedostępna (brak pakietu scipy).")

    # Parametry dla metod
    if ror_method == 'Średnia Ruchoma':
        window_sec = st.sidebar.number_input("Długość okna (sekundy)", min_value=1, max_value=60, value=15)
        calc_window = max(1, int(window_sec / 2))
        smooth_window = int(window_sec)
        sg_poly = None
        sg_window = None
    elif ror_method == 'Savitzky-Golay':
        sg_window = st.sidebar.number_input("Długość okna SG (musi być nieparzysta)", min_value=3, max_value=99, value=15, step=2)
        sg_poly = st.sidebar.number_input("Rząd wielomianu SG", min_value=1, max_value=5, value=2)
        if sg_window % 2 == 0:
            sg_window += 1
        calc_window = None
        smooth_window = None

    # Limity osi Y dla RoR
    st.sidebar.subheader("Zakres osi RoR")
    col_min, col_max = st.sidebar.columns(2)
    ror_y_min = col_min.number_input("Min", value=-5)
    ror_y_max = col_max.number_input("Max", value=35)

    # --- Przetwarzanie Danych ---

    # Przygotowanie danych rzeczywistych
    actual_milestones = {}
    actual_df = pd.DataFrame()

    if selected_roast_path:
        try:
            actual_df, actual_milestones = parse_roasttime_csv(selected_roast_path)

            # Obliczenia RoR
            cols_to_calc = [('IBTS Temp', ''), ('Bean Probe Temp', '_Probe')]

            for temp_col, suffix in cols_to_calc:
                if temp_col in actual_df.columns:
                    if ror_method == 'Średnia Ruchoma':
                        actual_df = calculate_ror(actual_df, temp_col=temp_col, window_seconds=calc_window)
                        # calculate_ror dodaje kolumne 'Calc_RoR{suffix}'
                        # Teraz wygładzamy
                        base_ror_col = f'Calc_RoR{suffix}'
                        if base_ror_col in actual_df.columns:
                            actual_df[f'RoR_Display{suffix}'] = smooth_data(actual_df[base_ror_col], window=smooth_window)
                    else:
                        actual_df = calculate_ror_sg(actual_df, temp_col=temp_col, window_length=sg_window, polyorder=sg_poly)
                        # calculate_ror_sg dodaje 'Calc_RoR_SG{suffix}'
                        base_ror_col = f'Calc_RoR_SG{suffix}'
                        if base_ror_col in actual_df.columns:
                            actual_df[f'RoR_Display{suffix}'] = actual_df[base_ror_col]

        except Exception as e:
            st.error(f"Błąd wczytywania pliku wypału: {e}")
            # print stack trace
            import traceback
            traceback.print_exc()

    # --- Wizualizacja ---

    # Funkcja pomocnicza do rzutowania L-kształtnego
    def add_l_projection(fig, x_val, y_val, color, row=1, col=1, is_time_x=True, show_y=True, show_x=True, text_offset_y=0):
        # Linia Pionowa: (x, 0) -> (x, y)
        # Ale uwaga: 0 na osi Y to może być środek wykresu.
        # Chcemy od "dołu" wykresu do punktu.
        # Użyjmy yref='y domain' dla dołu? Nie, bo y_val jest w danych.
        # Więc musimy znać min Y. Przyjmijmy 0 lub min z danych.
        # Jednak Plotly shapes z xref='x', yref='y' wymagają wartości.
        # Jeśli rysujemy od osi X (y=0) do punktu:

        # Jeśli y_val jest None (np. tylko czas zdarzenia), rysujemy tylko pionową linię przez cały wykres?
        # User: "od dołu do punktu oraz od lewej do punktu"

        if y_val is None:
            # Jeśli nie mamy wartości Y (np. sam czas milestone), rysujemy pełną linię pionową (dashed)
             fig.add_vline(x=x_val, line_width=1, line_dash="dash", line_color=color, opacity=0.5, row=row, col=col)
        else:
            # L-shape
            # Pionowa: od 0 (lub dołu) do y_val
            # Pozioma: od 0 (lewa) do x_val

            # Aby linia zaczynała się od "osi", musimy przyjąć jakiś punkt startowy.
            # Dla temperatury 0 stopni to dobry start.
            # Dla czasu 0 sekund.

            fig.add_shape(type="line",
                x0=x_val, y0=0, x1=x_val, y1=y_val,
                line=dict(color=color, width=1, dash="dash"),
                xref=f"x{col}", yref=f"y{row}" if row==1 else f"y{row+1}", # To jest tricky w subplots, trzeba uważać na indeksy osi
                row=row, col=col
            )

            if show_y:
                 fig.add_shape(type="line",
                    x0=0, y0=y_val, x1=x_val, y1=y_val,
                    line=dict(color=color, width=1, dash="dash"),
                    xref=f"x{col}", yref=f"y{row}",
                    row=row, col=col
                )

        # Etykieta na osi X
        if show_x:
            if is_time_x:
                x_text = f"{int(x_val//60)}:{int(x_val%60):02d}"
            else:
                x_text = f"{x_val:.1f}"

            fig.add_annotation(
                x=x_val, y=0,
                xref=f"x{col}", yref=f"y{row} domain", # y domain relative to subplot
                text=x_text,
                showarrow=False,
                font=dict(size=10, color=color),
                yshift=-15,
                bgcolor="rgba(0,0,0,0.5)",
                row=row, col=col
            )

        if show_y and y_val is not None:
            # Etykieta na osi Y
            fig.add_annotation(
                x=0, y=y_val,
                xref=f"x{col} domain", yref=f"y{row}",
                text=f"{y_val:.1f}",
                showarrow=False,
                font=dict(size=10, color=color),
                xshift=-25,
                xanchor="right",
                bgcolor="rgba(0,0,0,0.5)",
                row=row, col=col
            )

    # --- Konstrukcja Wykresów z Subplots ---

    # Row 1: Temp / RoR (Height 0.8)
    # Row 2: Settings (Height 0.2)

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.8, 0.2],
        subplot_titles=("Temperatura & RoR", "Ustawienia (Moc / Nawiew)")
    )

    fig.update_layout(template="plotly_dark", margin=dict(l=70, b=50))

    # --- Wykres 1 (Góra): Temperatura i RoR ---

    # 1. Plan (Temperatura)
    # Punkty
    # Staggering labels logic
    # Sort plan by time
    plan_df_sorted = plan_df.sort_values('Time_Seconds')

    for i, row in plan_df_sorted.iterrows():
        # Simple stagger: alternate offsets
        # Sprawdzamy czy poprzedni punkt był blisko

        y_offset = 15 if i % 2 == 0 else 30

        fig.add_trace(go.Scatter(
            x=[row['Time_Seconds']],
            y=[row['Temperatura']],
            mode='markers+text',
            name='Plan',
            text=[row['Faza']],
            textposition="top center",
            textfont=dict(color='cyan'),
            marker=dict(size=10, color='cyan', symbol='x'),
            showlegend=(i==0)
        ), row=1, col=1)

        # Projekcje
        add_l_projection(fig, row['Time_Seconds'], row['Temperatura'], 'cyan', row=1)

    # 2. Rzeczywista Temperatura (IBTS)
    if not actual_df.empty:
        fig.add_trace(go.Scatter(
            x=actual_df['Time_Seconds'],
            y=actual_df['IBTS Temp'],
            mode='lines',
            name='Rzecz. IBTS Temp',
            line=dict(color='orange', width=2)
        ), row=1, col=1)

        # 3. Rzeczywista Temperatura (Probe)
        if 'Bean Probe Temp' in actual_df.columns:
             fig.add_trace(go.Scatter(
                x=actual_df['Time_Seconds'],
                y=actual_df['Bean Probe Temp'],
                mode='lines',
                name='Rzecz. Probe Temp',
                line=dict(color='green', width=2, dash='dot')
            ), row=1, col=1)

        # 4. RoR (IBTS) na drugiej osi Y (wewnątrz tego samego subplotu? Czy osobny wykres?)
        # User said: "temp and RoR... yes on the same charts" and "best if fan/power at bottom"
        # Usually RoR is on secondary Y axis on the same plot as Temp.
        # Let's add Secondary Y axis for RoR to Row 1.

        # Warning: make_subplots with secondary_y=True is global or per row?
        # It's better to manually add axes in layout for custom complex setups,
        # but let's stick to standard layout first.
        # Actually, standard roasting charts often have RoR on the right axis.

        # But wait, user requested "Temp graph" and "RoR graph" previously in original code they were separate.
        # "Na wykresach ror zaznacz także..." -> Plural.
        # "Chce aby na wykresie temperatury oraz ROR były zaznaczone dane..." -> Singular/Plural ambiguity.
        # Given "Charts" (plural) in point 5 and 7.
        # But in point 1: "horizontal and vertical lines...".

        # Let's keep Temp and RoR separate as in the original code?
        # But now with Settings at the bottom.
        # If I keep them separate, I need 3 rows? Temp, RoR, Settings.
        # User said: "1. lines... 2. drop point... 7. Settings on Temp AND RoR charts".
        # This implies settings should be visible for BOTH.
        # If I have 2 separate charts (Temp, RoR), I need settings on both?
        # Or one big combined chart?
        # The provided image (which I can't see but user described) usually shows Temp and RoR together or stacked.
        # Let's assume 2 separate Plotly figures (as original code had fig_temp and fig_ror)
        # AND add the "Settings" strip to BOTH figures.

        pass # Decision made below.

    # DECISION: Revert to 2 separate figures (Temp and RoR) as in original code,
    # but modify EACH to include the Settings subplot at the bottom.

    # --- Helper to create Settings Data ---
    settings_traces = []

    def create_settings_traces(plan_df, actual_df):
        traces = []

        # 1. Plan Settings
        # Plan usually has discrete points. We can assume the setting is valid until the next point.
        # Or just markers? User said "Plan settings must be added".
        # Let's draw them as rectangles if we can infer duration, or markers if not.
        # Plan: Time, Nawiew, Moc.
        # If we assume step changes:
        if 'Nawiew' in plan_df.columns and 'Moc' in plan_df.columns:
            # Create step plot data
            # Plan is sparse (milestones).
            # We can interpolate or just show points.
            # "Faza Maillarda moc zmieniana 2 razy" implies we might have extra rows in Plan just for settings.
            pass

        # 2. Actual Settings (Fan, Power)
        # These are continuous. We need to detect blocks of constant values.
        # Or just plot the line 'step-shape'.

        # For actuals, plotting a stepped line is easiest and accurate.
        # But user mentioned "Bars" and "Labels P6, F4".
        # Let's use filled area or thick lines.

        if not actual_df.empty:
            if 'Fan' in actual_df.columns:
                 traces.append(go.Scatter(
                    x=actual_df['Time_Seconds'], y=actual_df['Fan'],
                    name='Fan (Actual)', line_shape='hv',
                    mode='lines', line=dict(color='blue'),
                    legendgroup='settings'
                ))
            if 'Power' in actual_df.columns:
                 traces.append(go.Scatter(
                    x=actual_df['Time_Seconds'], y=actual_df['Power'],
                    name='Power (Actual)', line_shape='hv',
                    mode='lines', line=dict(color='purple'),
                    legendgroup='settings'
                ))
        return traces

    # Actually, plotting lines for settings is better than bars if values fluctuate.
    # But user image description: "P6, F4" text on bars.
    # I will stick to lines for now as it's more robust for CSV data.
    # To emulate "Bars with text", I can add annotations for changes.

    def add_settings_subplot(fig_main, row_idx=2):
        # Adds traces to the specified row
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
    for i, row in plan_df_sorted.iterrows():
        # Alternate text position to avoid overlap
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
        fig_temp.add_trace(go.Scatter(
            x=actual_df['Time_Seconds'],
            y=actual_df['IBTS Temp'],
            mode='lines',
            name='Rzecz. IBTS',
            line=dict(color='orange', width=2)
        ), row=1, col=1)

        # Probe
        if 'Bean Probe Temp' in actual_df.columns:
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
                temp_val = row['IBTS Temp'].values[0]

                # Stagger labels for milestones
                # Check distance to previous
                offset_y = 0
                if i > 0:
                    prev_time = sorted_milestones[i-1][1]
                    if (time_sec - prev_time) < 30: # 30 seconds threshold
                        offset_y = 20 if (i % 2 != 0) else 0 # shift every second one

                # We can't easily shift Scatter text with offset_y in pixels in Plotly without custom annotations.
                # Use annotation instead of mode='markers+text' for the label.

                fig_temp.add_trace(go.Scatter(
                    x=[time_sec],
                    y=[temp_val],
                    mode='markers',
                    name=f'{name}',
                    marker=dict(size=10, color='red', symbol='circle-open'),
                    showlegend=False
                ), row=1, col=1)

                # Add Annotation Label
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
    fig_temp.update_yaxes(title_text="Wartość", row=2, col=1)
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
        if 'RoR_Display' in actual_df.columns:
            fig_ror.add_trace(go.Scatter(
                x=actual_df['Time_Seconds'],
                y=actual_df['RoR_Display'],
                mode='lines',
                name='RoR IBTS',
                line=dict(color='magenta', width=2)
            ), row=1, col=1)

        # Probe RoR
        if 'RoR_Display_Probe' in actual_df.columns:
            fig_ror.add_trace(go.Scatter(
                x=actual_df['Time_Seconds'],
                y=actual_df['RoR_Display_Probe'],
                mode='lines',
                name='RoR Sonda',
                line=dict(color='mediumspringgreen', width=2, dash='dot')
            ), row=1, col=1)

        # Plan Projections (Time only)
        for _, row in plan_df_sorted.iterrows():
             # Vertical line only
             add_l_projection(fig_ror, row['Time_Seconds'], None, 'cyan', row=1, show_y=False)

        # Actual Milestones
        for name, time_sec in actual_milestones.items():
             row_actual = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
             if not row_actual.empty and 'RoR_Display' in row_actual:
                 ror_val = row_actual['RoR_Display'].values[0]

                 # Marker
                 fig_ror.add_trace(go.Scatter(
                    x=[time_sec], y=[ror_val],
                    mode='markers', name=name,
                    marker=dict(size=8, color='red', symbol='circle-open'),
                    showlegend=False
                 ), row=1, col=1)

                 # Label
                 fig_ror.add_annotation(
                    x=time_sec, y=ror_val,
                    text=name, showarrow=False,
                    yshift=10, font=dict(color='red', size=9),
                    row=1, col=1
                 )

                 add_l_projection(fig_ror, time_sec, ror_val, 'red', row=1)
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
        fig_ror.update_yaxes(title_text="Wartość", row=2, col=1)
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

            # Find TP
            if 'Turning Point' not in key_events:
                 try:
                    early_df = actual_df[actual_df['Time_Seconds'] < 180]
                    if not early_df.empty:
                        min_idx = early_df['IBTS Temp'].idxmin()
                        tp_time = early_df.loc[min_idx, 'Time_Seconds']
                        key_events['Turning Point'] = tp_time
                 except:
                    pass

            key_events['Start'] = 0.0

            # Ensure Drop/End is present (parse_roasttime_csv already adds Drop if not present)
            # But let's make sure we have 'End' or 'Drop'
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

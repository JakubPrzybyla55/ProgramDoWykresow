import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
        # Dla średniej ruchomej, możemy użyć parametru do calculate_ror
        # ale w utils używamy calculate_ror z window_seconds do liczenia diff
        # a potem smooth_data.
        # Przyjmijmy: Diff window = window_sec / 2 (min 1), Smooth window = window_sec
        calc_window = max(1, int(window_sec / 2))
        smooth_window = int(window_sec)
        sg_poly = None
    elif ror_method == 'Savitzky-Golay':
        sg_window = st.sidebar.number_input("Długość okna SG (musi być nieparzysta)", min_value=3, max_value=99, value=15, step=2)
        sg_poly = st.sidebar.number_input("Rząd wielomianu SG", min_value=1, max_value=5, value=2)
        if sg_window % 2 == 0:
            sg_window += 1

    # Limity osi Y dla RoR
    st.sidebar.subheader("Zakres osi RoR")
    col_min, col_max = st.sidebar.columns(2)
    ror_y_min = col_min.number_input("Min", value=-5)
    ror_y_max = col_max.number_input("Max", value=35)

    # --- Wizualizacja ---

    # Przygotowanie danych rzeczywistych
    actual_milestones = {}
    actual_df = pd.DataFrame()
    ror_col_name = 'Calc_RoR'

    if selected_roast_path:
        try:
            actual_df, actual_milestones = parse_roasttime_csv(selected_roast_path)

            # Obliczenia RoR w zależności od wyboru
            if ror_method == 'Średnia Ruchoma':
                actual_df = calculate_ror(actual_df, window_seconds=calc_window)
                actual_df['RoR_Display'] = smooth_data(actual_df['Calc_RoR'], window=smooth_window)
            else:
                actual_df = calculate_ror_sg(actual_df, window_length=sg_window, polyorder=sg_poly)
                actual_df['RoR_Display'] = actual_df['Calc_RoR_SG']

        except Exception as e:
            st.error(f"Błąd wczytywania pliku wypału: {e}")

    # Wykres 1: Temperatura & Profil
    fig_temp = go.Figure()

    # Styl ciemny
    fig_temp.update_layout(template="plotly_dark")

    # Punkty Planu
    fig_temp.add_trace(go.Scatter(
        x=plan_df['Time_Seconds'],
        y=plan_df['Temperatura'],
        mode='markers+text',
        name='Plan Profilu',
        text=plan_df['Faza'],
        textposition="top center",
        marker=dict(size=12, color='cyan', symbol='x')
    ))

    # Linie pionowe dla Planu
    for _, row in plan_df.iterrows():
         fig_temp.add_vline(x=row['Time_Seconds'], line_width=1, line_dash="dash", line_color="cyan", opacity=0.3)

    if not actual_df.empty:
        # Wykres Rzeczywistej Temperatury
        fig_temp.add_trace(go.Scatter(
            x=actual_df['Time_Seconds'],
            y=actual_df['IBTS Temp'],
            mode='lines',
            name=f'Rzeczywista: {os.path.basename(selected_roast_path)}',
            line=dict(color='orange', width=2)
        ))

        # Rzeczywiste Zdarzenia (Milestones)
        for name, time_sec in actual_milestones.items():
            row = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
            if not row.empty:
                temp_val = row['IBTS Temp'].values[0]
                fig_temp.add_trace(go.Scatter(
                    x=[time_sec],
                    y=[temp_val],
                    mode='markers',
                    name=f'Rzeczywiste {name}',
                    marker=dict(size=10, color='red', symbol='circle-open')
                ))
                # Linie pionowe dla Rzeczywistych zdarzeń
                fig_temp.add_vline(x=time_sec, line_width=1, line_dash="dot", line_color="red", opacity=0.5)

    fig_temp.update_layout(
        title=f"Profil Temperatury: {selected_profile}",
        xaxis_title="Czas (sekundy)",
        yaxis_title="Temperatura (°C)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_temp, use_container_width=True)

    # Wykres 2: RoR (Tylko jeśli wypał jest wczytany)
    if not actual_df.empty:
        fig_ror = go.Figure()
        fig_ror.update_layout(template="plotly_dark")

        # Wyświetl obliczony RoR
        fig_ror.add_trace(go.Scatter(
            x=actual_df['Time_Seconds'],
            y=actual_df['RoR_Display'],
            mode='lines',
            name='Obliczony RoR',
            line=dict(color='magenta', width=2)
        ))

        # Linie pionowe dla zdarzeń (Plan i Rzeczywiste)
        for _, row in plan_df.iterrows():
             fig_ror.add_vline(x=row['Time_Seconds'], line_width=1, line_dash="dash", line_color="cyan", opacity=0.3)

        for name, time_sec in actual_milestones.items():
             fig_ror.add_vline(x=time_sec, line_width=1, line_dash="dot", line_color="red", opacity=0.5)

        fig_ror.update_layout(
            title="Szybkość Wzrostu (RoR)",
            xaxis_title="Czas (sekundy)",
            yaxis_title="RoR (°C/min)",
            yaxis_range=[ror_y_min, ror_y_max],
            hovermode="x unified",
             legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_ror, use_container_width=True)

        # --- Analiza ---
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

                # Próba dopasowania po nazwie
                matched_key = None
                # Najpierw szukamy dokładnych dopasowań dla kluczowych faz
                # Mapping user phases to typical metadata keys if needed
                # Ale tutaj po prostu szukamy substringów

                for key in actual_milestones:
                    if key.lower() in phase_name.lower() or phase_name.lower() in key.lower():
                        matched_key = key
                        break

                # Specjalne mapowanie dla startu (zazwyczaj 0)
                if "start" in phase_name.lower() and 0 not in actual_milestones.values():
                     actual_time = 0.0 # Zakładamy że start jest w 0
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

            # Definiowanie punktów podziału dla faz
            # Szukamy kluczowych punktów czasowych w danych rzeczywistych
            # Standardowe fazy: Start -> TP -> Yellowing -> 1st Crack -> Drop

            # Zbieramy punkty czasowe z metadanych i sortujemy
            # Dodajemy start (0) i koniec (ostatni czas)

            key_events = {k: v for k, v in actual_milestones.items()}

            # Dodaj Turning Point jeśli nie ma w milestones, ale jest zazwyczaj wykrywalny jako min temp
            # Spróbujmy znaleźć TP: minimum temperatury w pierwszych 3 minutach
            try:
                early_df = actual_df[actual_df['Time_Seconds'] < 180]
                if not early_df.empty:
                    min_idx = early_df['IBTS Temp'].idxmin()
                    tp_time = early_df.loc[min_idx, 'Time_Seconds']
                    if 'Turning Point' not in key_events:
                        key_events['Turning Point'] = tp_time
            except:
                pass

            key_events['Start'] = 0.0
            key_events['End'] = actual_df['Time_Seconds'].max()

            # Sortujemy zdarzenia po czasie
            sorted_events = sorted(key_events.items(), key=lambda x: x[1])

            phase_metrics = []

            for i in range(len(sorted_events) - 1):
                start_name, start_time = sorted_events[i]
                end_name, end_time = sorted_events[i+1]

                # Pomijamy bardzo krótkie interwały
                if end_time - start_time < 10:
                    continue

                # Wybieramy dane z tego przedziału
                mask = (actual_df['Time_Seconds'] >= start_time) & (actual_df['Time_Seconds'] <= end_time)
                phase_data = actual_df.loc[mask]

                if not phase_data.empty:
                    avg_ror = phase_data['RoR_Display'].mean()
                    phase_metrics.append({
                        "Faza": f"{start_name} -> {end_name}",
                        "Średni RoR": round(avg_ror, 2)
                    })

            st.table(pd.DataFrame(phase_metrics))

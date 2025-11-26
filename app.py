import streamlit as st
import pandas as pd
import numpy as np
import os
from utils import (
    parse_roasttime_csv,
    parse_profile_csv,
    calculate_ror,
    calculate_ror_sg,
    calculate_thermal_dose,
    smooth_data,
    get_profiles,
    get_roast_files,
    get_all_roast_files,
    SCIPY_AVAILABLE,
    get_agtron,
    set_agtron
)
from tabs import plan_analysis, plan_comparison, general_comparison, plan_editor

# --- CSS dla kompaktowego widoku ---
st.set_page_config(page_title="Analizator Wypału Kawy", layout="wide")

st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 0rem;
            padding-left: 5rem;
            padding-right: 5rem;
        }
        /* ... (reszta CSS bez zmian) ... */
    </style>
""", unsafe_allow_html=True)

st.title("Analizator Wypału Kawy")

# --- Sidebar ---
st.sidebar.header("Wybierz Profil")
base_data_path = 'data'
profiles = get_profiles(base_data_path)

if not profiles:
    st.sidebar.warning(f"Nie znaleziono profili w '{base_data_path}'. Proszę utworzyć foldery.")
    st.stop()

selected_profile = st.sidebar.selectbox("Wybierz Profil Kawy", profiles)
plan_file_path, roast_files_paths = get_roast_files(selected_profile, base_data_path)

# --- Główna logika ---
if not plan_file_path:
    st.error(f"Nie znaleziono pliku Planu CSV w '{selected_profile}/Plan'. Dodaj plik CSV.")
else:
    try:
        plan_df = parse_profile_csv(plan_file_path)
    except Exception as e:
        st.error(f"Błąd wczytywania planu: {e}")
        st.stop()

    st.sidebar.header("Wybierz Wypał (Rzeczywisty)")
    selected_roast_path = None
    if roast_files_paths:
        roast_options = {os.path.basename(p): p for p in roast_files_paths}
        selected_roast_name = st.sidebar.selectbox("Wybierz Dane Wypału", list(roast_options.keys()))
        selected_roast_path = roast_options[selected_roast_name]

        profile_path = os.path.join(base_data_path, selected_profile)
        current_agtron = get_agtron(profile_path, selected_roast_name) or 0.0
        st.sidebar.markdown("---")
        st.sidebar.subheader("Dane Wypału")
        new_agtron = st.sidebar.number_input("Kolor Agtron", value=float(current_agtron), step=0.1, format="%.1f")
        if new_agtron != current_agtron:
            set_agtron(profile_path, selected_roast_name, new_agtron)
            st.sidebar.success("Zapisano kolor.")
    else:
        st.sidebar.info("Brak plików wypałów w folderze 'Wypały'.")

    st.sidebar.markdown("---")
    with st.sidebar.expander("Ustawienia Widoczności i Wykresów", expanded=True):
        show_plan = st.checkbox("Pokaż Plan", value=True)
        show_ibts = st.checkbox("Pokaż IBTS (Temp/RoR)", value=True)
        show_probe = st.checkbox("Pokaż Sondę (Temp/RoR)", value=True)
        ror_y_min, ror_y_max = st.slider("Zakres osi RoR", -20, 50, (-5, 35))
        settings_y_min, settings_y_max = st.slider("Zakres osi Ustawień", 0, 15, (0, 9))

    with st.sidebar.expander("Ustawienia RoR"):
        method_options = ['Średnia Ruchoma'] + (['Savitzky-Golay'] if SCIPY_AVAILABLE else [])
        if not SCIPY_AVAILABLE:
            st.sidebar.warning("Metoda Savitzky-Golay niedostępna (brak scipy).")

        st.sidebar.subheader("IBTS")
        ror_method_ibts = st.sidebar.radio("Metoda (IBTS)", method_options, key="ror_method_ibts")
        ibts_params = {}
        if ror_method_ibts == 'Średnia Ruchoma':
            ibts_params['window_sec'] = st.sidebar.number_input("Okno Wygładzania (sek) - IBTS", 1, 60, 15, key="ibts_ma_win")
        else:
            ibts_params['window_length'] = st.sidebar.number_input("Okno SG - IBTS", 3, 99, 15, 2, key="ibts_sg_win")
            ibts_params['polyorder'] = st.sidebar.number_input("Rząd wielomianu - IBTS", 1, 5, 2, key="ibts_sg_poly")
            ibts_params['deriv'] = st.sidebar.number_input("Rząd pochodnej - IBTS", 1, 3, 1, key="ibts_sg_deriv")

        st.sidebar.subheader("Sonda")
        ror_method_probe = st.sidebar.radio("Metoda (Sonda)", method_options, key="ror_method_probe")
        probe_params = {}
        if ror_method_probe == 'Średnia Ruchoma':
            probe_params['window_sec'] = st.sidebar.number_input("Okno Wygładzania (sek) - Sonda", 1, 60, 15, key="probe_ma_win")
        else:
            probe_params['window_length'] = st.sidebar.number_input("Okno SG - Sonda", 3, 99, 15, 2, key="probe_sg_win")
            probe_params['polyorder'] = st.sidebar.number_input("Rząd wielomianu - Sonda", 1, 5, 2, key="probe_sg_poly")
            probe_params['deriv'] = st.sidebar.number_input("Rząd pochodnej - Sonda", 1, 3, 1, key="probe_sg_deriv")

    with st.sidebar.expander("Ustawienia Dawki Termicznej"):
        dose_t_base = st.number_input("Temperatura Bazowa (°C)", value=100.0, step=1.0)
        dose_start_time = st.number_input("Start Obliczeń (sek)", value=5.0, step=1.0)

    with st.sidebar.expander("Analiza Teoretyczna (Wielomian)"):
        poly_degree = st.number_input("Stopień wielomianu", 1, 10, 3, 1)

    # --- Struktura zakładek ---
    tab1, tab2, tab3, tab4 = st.tabs(["Analiza Planu", "Porównanie Wypałów (dla Planu)", "Porównanie Wypałów (Ogólne)", "Edytor Planu"])

    with tab1:
        plan_analysis.render(st, selected_profile, plan_df, selected_roast_path, show_plan, show_ibts, show_probe, ror_y_min, ror_y_max, settings_y_min, settings_y_max, ror_method_ibts, ibts_params, ror_method_probe, probe_params, dose_t_base, dose_start_time, poly_degree)

    with tab2:
        plan_comparison.render(st, selected_profile, roast_files_paths, selected_roast_path, base_data_path, dose_t_base, dose_start_time)

    with tab3:
        general_comparison.render(st, base_data_path, dose_t_base, dose_start_time)

    with tab4:
        plan_editor.render(st, profiles, selected_profile, base_data_path, plan_file_path)

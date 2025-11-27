import streamlit as st
import pandas as pd
import numpy as np
import os
from utils import (
    parsuj_csv_profilu,
    pobierz_profile,
    pobierz_pliki_wypalow,
    SCIPY_AVAILABLE,
    pobierz_agtron,
    ustaw_agtron
)
from tabs import plan_analysis, plan_comparison, general_comparison, plan_editor
from state import AppState

def load_css(file_name):
    """Funkcja do ładowania zewnętrznego pliku CSS."""
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# --- Konfiguracja strony i CSS ---
st.set_page_config(page_title="Analizator Wypału Kawy", layout="wide")
load_css("style.css") # Ładowanie CSS z pliku

st.title("Analizator Wypału Kawy")

# --- Inicjalizacja stanu ---
state = AppState()

# --- Sidebar ---
st.sidebar.header("Wybierz Profil")
state.profiles = pobierz_profile(state.base_data_path)

if not state.profiles:
    st.sidebar.warning(f"Nie znaleziono profili w '{state.base_data_path}'. Proszę utworzyć foldery.")
    st.stop()

state.selected_profile = st.sidebar.selectbox("Wybierz Profil Kawy", state.profiles)
state.plan_file_path, state.roast_files_paths = pobierz_pliki_wypalow(state.selected_profile, state.base_data_path)

# --- Główna logika ---
if not state.plan_file_path:
    st.warning(f"Nie znaleziono pliku Planu CSV w '{state.selected_profile}/Plan'. Przejdź do 'Edytora Planu', aby go utworzyć.")
    # Ustaw pusty DataFrame, aby reszta aplikacji mogła działać
    state.plan_df = pd.DataFrame(columns=['Faza', 'Czas', 'Temperatura', 'Time_Seconds'])
else:
    try:
        state.plan_df = parsuj_csv_profilu(state.plan_file_path)
    except (ValueError, FileNotFoundError) as e:
        st.error(f"Błąd wczytywania pliku planu: {e}")
        st.stop()

    st.sidebar.header("Wybierz Wypał (Rzeczywisty)")
    if state.roast_files_paths:
        roast_options = {os.path.basename(p): p for p in state.roast_files_paths}
        selected_roast_name = st.sidebar.selectbox("Wybierz Dane Wypału", list(roast_options.keys()))
        state.selected_roast_path = roast_options[selected_roast_name]

        profile_path = os.path.join(state.base_data_path, state.selected_profile)
        current_agtron = pobierz_agtron(profile_path, selected_roast_name) or 0.0
        st.sidebar.markdown("---")
        st.sidebar.subheader("Dane Wypału")
        new_agtron = st.sidebar.number_input("Kolor Agtron", value=float(current_agtron), step=0.1, format="%.1f")
        if new_agtron != current_agtron:
            ustaw_agtron(profile_path, selected_roast_name, new_agtron)
            st.sidebar.success("Zapisano kolor.")
    else:
        st.sidebar.info("Brak plików wypałów w folderze 'Wypały'.")

    st.sidebar.markdown("---")
    with st.sidebar.expander("Ustawienia Widoczności i Wykresów", expanded=True):
        state.show_plan = st.checkbox("Pokaż Plan", value=state.show_plan)
        state.show_ibts = st.checkbox("Pokaż IBTS (Temp/RoR)", value=state.show_ibts)
        state.show_probe = st.checkbox("Pokaż Sondę (Temp/RoR)", value=state.show_probe)
        ror_y_min, ror_y_max = st.slider("Zakres osi RoR", -20, 50, state.ror_y_lim)
        state.ror_y_lim = (ror_y_min, ror_y_max)
        settings_y_min, settings_y_max = st.slider("Zakres osi Ustawień", 0, 15, state.settings_y_lim)
        state.settings_y_lim = (settings_y_min, settings_y_max)

    with st.sidebar.expander("Ustawienia RoR"):
        method_options = ['Średnia Ruchoma'] + (['Savitzky-Golay'] if SCIPY_AVAILABLE else [])
        if not SCIPY_AVAILABLE:
            st.sidebar.warning("Metoda Savitzky-Golay niedostępna (brak scipy).")

        st.sidebar.subheader("IBTS")
        state.ror_method_ibts = st.sidebar.radio("Metoda (IBTS)", method_options, key="ror_method_ibts")
        if state.ror_method_ibts == 'Średnia Ruchoma':
            state.ibts_params['window_sec'] = st.sidebar.number_input("Okno Wygładzania (sek) - IBTS", 1, 60, 15, key="ibts_ma_win")
        else:
            state.ibts_params['window_length'] = st.sidebar.number_input("Okno SG - IBTS", 3, 99, 15, 2, key="ibts_sg_win")
            state.ibts_params['polyorder'] = st.sidebar.number_input("Rząd wielomianu - IBTS", 1, 5, 2, key="ibts_sg_poly")
            state.ibts_params['deriv'] = st.sidebar.number_input("Rząd pochodnej - IBTS", 1, 3, 1, key="ibts_sg_deriv")

        st.sidebar.subheader("Sonda")
        state.ror_method_probe = st.sidebar.radio("Metoda (Sonda)", method_options, key="ror_method_probe")
        if state.ror_method_probe == 'Średnia Ruchoma':
            state.probe_params['window_sec'] = st.sidebar.number_input("Okno Wygładzania (sek) - Sonda", 1, 60, 15, key="probe_ma_win")
        else:
            state.probe_params['window_length'] = st.sidebar.number_input("Okno SG - Sonda", 3, 99, 15, 2, key="probe_sg_win")
            state.probe_params['polyorder'] = st.sidebar.number_input("Rząd wielomianu - Sonda", 1, 5, 2, key="probe_sg_poly")
            state.probe_params['deriv'] = st.sidebar.number_input("Rząd pochodnej - Sonda", 1, 3, 1, key="probe_sg_deriv")

    with st.sidebar.expander("Ustawienia Dawki Termicznej"):
        state.dose_t_base = st.number_input("Temperatura Bazowa (°C)", value=state.dose_t_base, step=1.0)
        state.dose_start_time = st.number_input("Start Obliczeń (sek)", value=state.dose_start_time, step=1.0)

    with st.sidebar.expander("Analiza Teoretyczna (Wielomian)"):
        state.poly_degree = st.number_input("Stopień wielomianu", 1, 10, state.poly_degree, 1)

    # --- Struktura zakładek ---
    tab1, tab2, tab3, tab4 = st.tabs(["Analiza Planu", "Porównanie Wypałów (dla Planu)", "Porównanie Wypałów (Ogólne)", "Edytor Planu"])

    with tab1:
        plan_analysis.render(st, state)
    with tab2:
        plan_comparison.render(st, state)
    with tab3:
        general_comparison.render(st, state)
    with tab4:
        plan_editor.render(st, state)

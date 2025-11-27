import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
from utils import (
    parsuj_csv_roasttime,
    oblicz_dawke_termiczna,
    pobierz_agtron,
    pobierz_metadane_planu,
    aktualizuj_metadane_planu,
    oblicz_dawke_termiczna_arrhenius,
    parsuj_csv_profilu
)
from state import AppState

def render(st: object, state: AppState):
    """Renderuje zakładkę Porównanie Wypałów dla Planu."""
    st.subheader(f"Dawka Termiczna vs Kolor dla Planu: {state.selected_profile}")

    if not state.roast_files_paths:
        st.info("Brak plików wypałów do analizy w tym profilu.")
        return
    if not state.plan_file_path:
        st.warning("Brak pliku planu dla tego profilu. Nie można obliczyć dawki teoretycznej.")
        return

    # --- Pobieranie i edycja metadanych planu ---
    plan_name = os.path.basename(state.plan_file_path)
    plan_metadata = pobierz_metadane_planu(plan_name)

    st.markdown("##### Ustawienia dla Planu Teoretycznego")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        agtron_teoretyczny = st.number_input(
            "Teoretyczny Kolor (Agtron)",
            value=float(plan_metadata.get('agtron', 85.0)),
            min_value=0.0, max_value=150.0, step=0.1, format="%.1f"
        )
    with col2:
        const_A = st.number_input("Stała A", value=float(plan_metadata.get('A', 0.788)), step=1e-4, format="%.4f")
    with col3:
        const_Ea = st.number_input("Energia Aktywacji (Ea)", value=float(plan_metadata.get('Ea', 26.02)), step=1e-3, format="%.3f")
    with col4:
        const_R = st.number_input("Stała Gazowa (R)", value=float(plan_metadata.get('R', 0.008314)), step=1e-6, format="%.6f")

    if st.button("Zapisz ustawienia dla tego planu"):
        aktualizuj_metadane_planu(plan_name, {
            'agtron': agtron_teoretyczny,
            'A': const_A,
            'Ea': const_Ea,
            'R': const_R
        })
        st.success(f"Zapisano ustawienia dla planu: {plan_name}")
        # Odświeżenie metadanych po zapisie
        plan_metadata = pobierz_metadane_planu(plan_name)

    # --- Obliczenia dawek ---
    all_data = []

    # 1. Obliczenia dla planu
    try:
        plan_df = parsuj_csv_profilu(state.plan_file_path)
        plan_df = oblicz_dawke_termiczna(plan_df, temp_col='Temperatura', time_col='Time_Seconds', t_base=state.dose_t_base, start_time_threshold=state.dose_start_time)
        plan_df = oblicz_dawke_termiczna_arrhenius(plan_df, temp_col='Temperatura', time_col='Time_Seconds', A=const_A, Ea=const_Ea, R=const_R, start_time_threshold=state.dose_start_time)

        all_data.append({
            'Label': "PLAN",
            'Agtron': agtron_teoretyczny,
            'File': plan_name,
            'Dose_Old': plan_df['Thermal_Dose'].iloc[-1],
            'Dose_New': plan_df['Thermal_Dose_Arrhenius'].iloc[-1]
        })
    except Exception as e:
        st.error(f"Nie udało się przetworzyć pliku planu: {e}")

    # 2. Obliczenia dla wypałów empirycznych
    for r_path in state.roast_files_paths:
        f_name = os.path.basename(r_path)
        try:
            r_df, _ = parsuj_csv_roasttime(r_path)
            agtron_val = pobierz_agtron(os.path.join(state.base_data_path, state.selected_profile), f_name)
            if agtron_val is None: continue

            r_df = oblicz_dawke_termiczna(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=state.dose_t_base, start_time_threshold=state.dose_start_time)
            r_df = oblicz_dawke_termiczna_arrhenius(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', A=const_A, Ea=const_Ea, R=const_R, start_time_threshold=state.dose_start_time)

            all_data.append({
                'Label': f"{f_name.replace('.csv','')}",
                'Agtron': agtron_val,
                'File': f_name,
                'Dose_Old': r_df['Thermal_Dose'].iloc[-1],
                'Dose_New': r_df['Thermal_Dose_Arrhenius'].iloc[-1]
            })
        except Exception as e:
            print(f"Błąd przetwarzania {f_name}: {e}")

    # --- Wizualizacja ---
    if not all_data:
        st.warning("Brak danych do wyświetlenia. Upewnij się, że wypały mają przypisany kolor Agtron.")
        return

    df_plot = pd.DataFrame(all_data).sort_values(by="Agtron", ascending=False)

    # Wykres 1: Model Oryginalny (Czerwony)
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=df_plot['Label'],
        y=df_plot['Dose_Old'],
        text=df_plot['Agtron'].apply(lambda x: f"{x:.1f}"),
        textposition='outside',
        name='Dawka (Model Oryginalny)',
        marker_color='indianred',
        width=0.4,
        hovertemplate="<b>%{x}</b><br>Dawka (Oryg.): %{y:.0f}<br>Agtron: %{text}<extra></extra>"
    ))

    fig1.update_layout(
        template="plotly_dark",
        title="Dawka Termiczna (Model 1 - Oryginalny)",
        xaxis_title="Wypał",
        yaxis_title="Skumulowana Dawka",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Wykres 2: Model Arrhenius (Niebieski)
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df_plot['Label'],
        y=df_plot['Dose_New'],
        text=df_plot['Agtron'].apply(lambda x: f"{x:.1f}"),
        textposition='outside',
        name='Dawka (Model Arrhenius)',
        marker_color='royalblue',
        width=0.4,
        hovertemplate="<b>%{x}</b><br>Dawka (Arrhenius): %{y:.0f}<br>Agtron: %{text}<extra></extra>"
    ))

    fig2.update_layout(
        template="plotly_dark",
        title="Dawka Termiczna (Model 2 - Arrhenius)",
        xaxis_title="Wypał",
        yaxis_title="Skumulowana Dawka",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig2, use_container_width=True)

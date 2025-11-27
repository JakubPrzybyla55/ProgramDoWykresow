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
            'Label': f"PLAN ({agtron_teoretyczny:.1f})",
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
                'Label': f"{f_name.replace('.csv','')} ({agtron_val:.1f})",
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

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_plot['Label'],
        y=df_plot['Dose_Old'],
        name='Dawka (Model Oryginalny)',
        marker_color='indianred',
        hovertemplate="<b>%{x}</b><br>Dawka (Oryg.): %{y:.0f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=df_plot['Label'],
        y=df_plot['Dose_New'],
        name='Dawka (Model Arrhenius)',
        marker_color='lightsalmon',
        hovertemplate="<b>%{x}</b><br>Dawka (Arrhenius): %{y:.0f}<extra></extra>"
    ))

    fig.update_layout(
        barmode='group',
        template="plotly_dark",
        title="Porównanie Dawki Termicznej (dwa modele)",
        xaxis_title="Wypał (Kolor Agtron)",
        yaxis_title="Skumulowana Dawka Termiczna",
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

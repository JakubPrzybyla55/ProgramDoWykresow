import streamlit as st
import pandas as pd
import os
import glob
import plotly.graph_objects as go
from utils import (
    get_all_roast_files,
    parse_roasttime_csv,
    calculate_thermal_dose,
    get_agtron,
    get_plan_metadata,
    calculate_thermal_dose_arrhenius
)

def get_all_plan_files(base_path='data'):
    """Skanuje wszystkie profile i zwraca listę ścieżek do plików planów."""
    return glob.glob(os.path.join(base_path, '*', 'Plan', '*.csv'))

def render(
    st,
    base_data_path: str,
    dose_t_base: float,
    dose_start_time: float
):
    """Renderuje zakładkę Ogólne Porównanie Wypałów."""
    st.subheader("Ogólne Porównanie Dawki Termicznej vs Kolor")

    all_roast_files = get_all_roast_files(base_data_path)
    all_plan_files = get_all_plan_files(base_data_path)

    if not all_roast_files:
        st.info("Brak plików wypałów do analizy w żadnym z profili.")
        return
    if not all_plan_files:
        st.warning("Nie znaleziono żadnych plików planów. Nie można wybrać stałych do obliczeń.")
        return

    # --- Wybór planu jako źródła stałych ---
    plan_options = {os.path.basename(p): p for p in all_plan_files}
    selected_plan_name = st.selectbox(
        "Wybierz plan, aby użyć jego zapisanych stałych do obliczeń dawki",
        list(plan_options.keys())
    )

    plan_metadata = get_plan_metadata(selected_plan_name)
    const_A = float(plan_metadata.get('A', 0.788))
    const_Ea = float(plan_metadata.get('Ea', 26.02))
    const_R = float(plan_metadata.get('R', 0.008314))

    st.info(f"Używane stałe z planu '{selected_plan_name}': A={const_A:.4f}, Ea={const_Ea:.3f}, R={const_R:.6f}")

    # --- Obliczenia dawek ---
    all_data = []

    selected_files = st.multiselect(
        "Wybierz wypały do porównania (domyślnie wszystkie)",
        options=[os.path.basename(p) for p in all_roast_files],
        default=[os.path.basename(p) for p in all_roast_files]
    )

    roast_path_map = {os.path.basename(p): p for p in all_roast_files}
    files_to_process = [roast_path_map[name] for name in selected_files if name in roast_path_map]

    for r_path in files_to_process:
        f_name = os.path.basename(r_path)
        profile_name = os.path.basename(os.path.dirname(os.path.dirname(r_path)))
        try:
            r_df, _ = parse_roasttime_csv(r_path)
            agtron_val = get_agtron(os.path.join(base_data_path, profile_name), f_name)
            if agtron_val is None: continue

            r_df = calculate_thermal_dose(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=dose_t_base, start_time_threshold=dose_start_time)
            r_df = calculate_thermal_dose_arrhenius(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', A=const_A, Ea=const_Ea, R=const_R, start_time_threshold=dose_start_time)

            all_data.append({
                'Label': f"{profile_name} / {f_name.replace('.csv','')} ({agtron_val:.1f})",
                'Agtron': agtron_val,
                'Dose_Old': r_df['Thermal_Dose'].iloc[-1],
                'Dose_New': r_df['Thermal_Dose_Arrhenius'].iloc[-1]
            })
        except Exception as e:
            print(f"Błąd przetwarzania {f_name}: {e}")

    # --- Wizualizacja ---
    if not all_data:
        st.warning("Brak danych do wyświetlenia. Upewnij się, że wybrane wypały mają przypisany kolor Agtron.")
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
        xaxis_title="Wypał / Profil (Kolor Agtron)",
        yaxis_title="Skumulowana Dawka Termiczna",
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

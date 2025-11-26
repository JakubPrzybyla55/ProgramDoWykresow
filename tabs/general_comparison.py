
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
    calculate_thermal_dose_arrhenius,
    get_milestone_data_for_table
)

def get_all_plan_files(base_path='data'):
    """Skanuje wszystkie profile i zwraca listę ścieżek do plików planów."""
    return glob.glob(os.path.join(base_path, '*', 'Plan', '*.csv'))

def render_bar_chart_and_table_general(st, df_plot, title, y_col, y_name, color, milestones_map, plan_metadata_for_table):
    """Renderuje wykres słupkowy i tabelę z obliczeniami dla porównania ogólnego."""

    st.markdown(f"#### {title}")

    # --- Sortowanie ---
    sort_options = {
        "Domyślnie (wg Agtron)": "Agtron",
        "Wg Dawki (rosnąco)": y_col,
        "Wg Dawki (malejąco)": y_col
    }
    sort_key = st.selectbox("Sortuj według", list(sort_options.keys()), key=f"sort_{y_col}")

    ascending = "rosnąco" in sort_key
    df_sorted = df_plot.sort_values(by=sort_options[sort_key], ascending=ascending)

    # --- Wykres ---
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_sorted['Label'],
        y=df_sorted[y_col],
        name=y_name,
        marker_color=color,
        hovertemplate="<b>%{x}</b><br>" + f"{y_name}: %{{y:.2f}}<extra></extra>"
    ))
    fig.update_layout(
        template="plotly_dark",
        xaxis_title="Wypał / Profil (Kolor Agtron)",
        yaxis_title="Skumulowana Dawka Termiczna",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Tabela z obliczeniami ---
    with st.expander("Pokaż szczegóły obliczeń dla wybranych wypałów"):
        selected_file = st.selectbox(
            "Wybierz wypał, aby zobaczyć szczegóły",
            options=df_sorted['File'].tolist(),
            format_func=lambda x: df_sorted[df_sorted['File'] == x]['Label'].values[0],
            key=f"select_table_{y_col}"
        )

        if selected_file:
            milestones = milestones_map.get(selected_file, {})
            full_df = df_sorted[df_sorted['File'] == selected_file]['full_df'].values[0]

            model_params = None
            if "Arrhenius" in title:
                model_params = plan_metadata_for_table

            # Map friendly column name back to the original DataFrame column name
            dose_col_map = {
                'Dose_Old': 'Thermal_Dose',
                'Dose_New': 'Thermal_Dose_Arrhenius'
            }
            actual_dose_col = dose_col_map.get(y_col)

            t_base_for_table = dose_t_base if "Old" in y_col else None
            table_df = get_milestone_data_for_table(full_df, milestones, 'Time_Seconds', 'IBTS Temp', actual_dose_col, model_params, t_base=t_base_for_table)
            st.dataframe(table_df, use_container_width=True, hide_index=True)


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

    if not all_roast_files or not all_plan_files:
        st.info("Brak plików wypałów lub planów do analizy.")
        return

    plan_options = {os.path.basename(p): p for p in all_plan_files}
    selected_plan_name = st.selectbox("Wybierz plan, aby użyć jego stałych do obliczeń", list(plan_options.keys()))

    plan_metadata = get_plan_metadata(selected_plan_name)
    const_A = float(plan_metadata.get('A', 0.788))
    const_Ea = float(plan_metadata.get('Ea', 26.02))
    const_R = float(plan_metadata.get('R', 0.008314))

    st.info(f"Używane stałe z planu '{selected_plan_name}': A={const_A:.4f}, Ea={const_Ea:.3f}, R={const_R:.6f}")

    all_data = []
    milestones_map = {}

    selected_files_names = st.multiselect(
        "Wybierz wypały do porównania",
        options=[os.path.basename(p) for p in all_roast_files],
        default=[os.path.basename(p) for p in all_roast_files]
    )

    roast_path_map = {os.path.basename(p): p for p in all_roast_files}
    files_to_process = [roast_path_map[name] for name in selected_files_names if name in roast_path_map]

    for r_path in files_to_process:
        f_name = os.path.basename(r_path)
        profile_name = os.path.basename(os.path.dirname(os.path.dirname(r_path)))
        try:
            r_df, milestones = parse_roasttime_csv(r_path)
            milestones_map[f_name] = milestones
            agtron = get_agtron(os.path.join(base_data_path, profile_name), f_name)
            if agtron is None: continue

            r_df = calculate_thermal_dose(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=dose_t_base, start_time_threshold=dose_start_time)
            r_df = calculate_thermal_dose_arrhenius(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', A=const_A, Ea=const_Ea, R=const_R, start_time_threshold=dose_start_time)

            all_data.append({
                'Label': f"{profile_name} / {f_name.replace('.csv','')} ({agtron:.1f})", 'Agtron': agtron,
                'File': f_name, 'Dose_Old': r_df['Thermal_Dose'].iloc[-1],
                'Dose_New': r_df['Thermal_Dose_Arrhenius'].iloc[-1], 'full_df': r_df
            })
        except Exception as e:
            print(f"Błąd przetwarzania {f_name}: {e}")

    if not all_data:
        st.warning("Brak danych do wyświetlenia.")
        return

    df_plot = pd.DataFrame(all_data)

    plan_metadata_for_table = {'A': const_A, 'Ea': const_Ea, 'R': const_R}

    render_bar_chart_and_table_general(st, df_plot, "Model Oryginalny", 'Dose_Old', "Dawka (Oryg.)", "indianred", milestones_map, None)
    render_bar_chart_and_table_general(st, df_plot, "Model Arrheniusa", 'Dose_New', "Dawka (Arrhenius)", "lightsalmon", milestones_map, plan_metadata_for_table)

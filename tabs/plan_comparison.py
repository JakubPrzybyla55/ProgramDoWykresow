
import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
from utils import (
    parse_roasttime_csv,
    calculate_thermal_dose,
    get_agtron,
    get_plan_metadata,
    update_plan_metadata,
    calculate_thermal_dose_arrhenius,
    parse_profile_csv,
    get_milestone_data_for_table
)

def render_bar_chart_and_table(st, df_plot, title, y_col, y_name, color, milestones_map):
    """Renderuje wykres słupkowy i tabelę z obliczeniami."""

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
        xaxis_title="Wypał (Kolor Agtron)",
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
                plan_metadata = get_plan_metadata(selected_file if ".csv" in selected_file else "default")
                model_params = {'A': plan_metadata['A'], 'Ea': plan_metadata['Ea'], 'R': plan_metadata['R']}

            temp_col = 'Temperatura' if 'plan' in selected_file.lower() else 'IBTS Temp'

            # Map friendly column name back to the original DataFrame column name
            dose_col_map = {
                'Dose_Old': 'Thermal_Dose',
                'Dose_New': 'Thermal_Dose_Arrhenius'
            }
            actual_dose_col = dose_col_map.get(y_col)

            t_base_for_table = dose_t_base if "Old" in y_col else None
            table_df = get_milestone_data_for_table(full_df, milestones, 'Time_Seconds', temp_col, actual_dose_col, model_params, t_base=t_base_for_table)
            st.dataframe(table_df, use_container_width=True, hide_index=True)


def render(
    st,
    selected_profile: str,
    plan_file_path: str,
    roast_files_paths: list,
    base_data_path: str,
    dose_t_base: float,
    dose_start_time: float
):
    """Renderuje zakładkę Porównanie Wypałów dla Planu."""
    st.subheader(f"Dawka Termiczna vs Kolor dla Planu: {selected_profile}")

    if not roast_files_paths or not plan_file_path:
        st.info("Brak plików planu lub wypałów do analizy w tym profilu.")
        return

    plan_name = os.path.basename(plan_file_path)
    plan_metadata = get_plan_metadata(plan_name)

    st.markdown("##### Ustawienia dla Planu Teoretycznego (Model Arrheniusa)")
    col1, col2, col3, col4 = st.columns(4)
    # UI... (reszta bez zmian)

    # --- Obliczenia ---
    all_data = []
    milestones_map = {}

    # Plan
    try:
        plan_df = parse_profile_csv(plan_file_path)
        plan_df, plan_milestones = parse_roasttime_csv(plan_file_path) # Simplified
        milestones_map[plan_name] = plan_milestones

        plan_df = calculate_thermal_dose(plan_df, temp_col='Temperatura', time_col='Time_Seconds', t_base=dose_t_base, start_time_threshold=dose_start_time)
        plan_df = calculate_thermal_dose_arrhenius(plan_df, temp_col='Temperatura', time_col='Time_Seconds', A=plan_metadata['A'], Ea=plan_metadata['Ea'], R=plan_metadata['R'], start_time_threshold=dose_start_time)

        all_data.append({
            'Label': f"PLAN ({plan_metadata['agtron']:.1f})", 'Agtron': plan_metadata['agtron'],
            'File': plan_name, 'Dose_Old': plan_df['Thermal_Dose'].iloc[-1],
            'Dose_New': plan_df['Thermal_Dose_Arrhenius'].iloc[-1], 'full_df': plan_df
        })
    except Exception as e:
        st.error(f"Błąd przetwarzania planu: {e}")

    # Wypały
    for r_path in roast_files_paths:
        f_name = os.path.basename(r_path)
        try:
            r_df, milestones = parse_roasttime_csv(r_path)
            milestones_map[f_name] = milestones
            agtron = get_agtron(os.path.join(base_data_path, selected_profile), f_name)
            if agtron is None: continue

            r_df = calculate_thermal_dose(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=dose_t_base, start_time_threshold=dose_start_time)
            r_df = calculate_thermal_dose_arrhenius(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', A=plan_metadata['A'], Ea=plan_metadata['Ea'], R=plan_metadata['R'], start_time_threshold=dose_start_time)

            all_data.append({
                'Label': f"{f_name.replace('.csv','')} ({agtron:.1f})", 'Agtron': agtron,
                'File': f_name, 'Dose_Old': r_df['Thermal_Dose'].iloc[-1],
                'Dose_New': r_df['Thermal_Dose_Arrhenius'].iloc[-1], 'full_df': r_df
            })
        except Exception as e:
            print(f"Błąd przetwarzania {f_name}: {e}")

    if not all_data:
        st.warning("Brak danych do wyświetlenia.")
        return

    df_plot = pd.DataFrame(all_data)

    render_bar_chart_and_table(st, df_plot, "Model Oryginalny", 'Dose_Old', "Dawka (Oryg.)", "indianred", milestones_map)
    render_bar_chart_and_table(st, df_plot, "Model Arrheniusa", 'Dose_New', "Dawka (Arrhenius)", "lightsalmon", milestones_map)


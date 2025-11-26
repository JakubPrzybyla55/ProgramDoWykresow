import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
import plotly.colors as pcolors

from utils import parse_roasttime_csv, calculate_thermal_dose, get_agtron

def render(
    st,
    selected_profile: str,
    roast_files_paths: list,
    selected_roast_path: str,
    base_data_path: str,
    dose_t_base: float,
    dose_start_time: float
):
    """Renders the Plan Comparison Tab."""
    st.subheader(f"Porównanie Wszystkich Wypałów dla Planu: {selected_profile}")

    if not roast_files_paths:
        st.info("Brak plików wypałów do analizy.")
        return

    all_roasts_data = []
    progress_bar = st.progress(0, text="Przetwarzanie wypałów dla tego planu...")

    colors_cycle = pcolors.qualitative.Plotly
    fig_all_dose = go.Figure()

    for i, r_path in enumerate(roast_files_paths):
        f_name = os.path.basename(r_path)
        try:
            r_df, _ = parse_roasttime_csv(r_path)
            if 'IBTS Temp' in r_df.columns:
                r_df = calculate_thermal_dose(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=dose_t_base, start_time_threshold=dose_start_time)
                if 'Thermal_Dose' in r_df.columns:
                    final_dose = r_df['Thermal_Dose'].iloc[-1]
                    agtron_val = get_agtron(os.path.join(base_data_path, selected_profile), f_name) or 0.0
                    all_roasts_data.append({"Nazwa Pliku": f_name, "Agtron": agtron_val, "Całkowita Dawka": final_dose})

                    color_idx = i % len(colors_cycle)
                    line_width = 4 if r_path == selected_roast_path else 2
                    opacity = 1.0 if r_path == selected_roast_path else 0.7
                    fig_all_dose.add_trace(go.Scatter(
                        x=r_df['Time_Seconds'], y=r_df['Thermal_Dose'], mode='lines', name=f_name,
                        line=dict(color=colors_cycle[color_idx], width=line_width), opacity=opacity,
                        hovertemplate=f"<b>{f_name}</b><br>Czas: %{{x:.0f}}s<br>Dawka: %{{y:.0f}}<extra></extra>"
                    ))
        except Exception as e:
            print(f"Błąd przetwarzania {f_name} dla symulacji: {e}")
        progress_bar.progress((i + 1) / len(roast_files_paths))
    progress_bar.empty()

    fig_all_dose.update_layout(
        template="plotly_dark", height=600, title="Krzywe Skumulowanej Dawki Termicznej",
        xaxis_title="Czas (sekundy)", yaxis_title="Dawka Termiczna", hovermode="closest",
        margin=dict(t=50, b=0, l=0, r=0)
    )
    st.plotly_chart(fig_all_dose, use_container_width=True)

    if all_roasts_data:
        st.subheader("Dane Zbiorcze")
        df_all = pd.DataFrame(all_roasts_data).sort_values(by="Agtron", ascending=False)
        st.dataframe(
            df_all,
            column_config={
                "Nazwa Pliku": st.column_config.TextColumn("Plik"),
                "Agtron": st.column_config.NumberColumn("Kolor (Agtron)", format="%.1f"),
                "Całkowita Dawka": st.column_config.NumberColumn("Dawka Total", format="%.0f"),
            },
            use_container_width=True, hide_index=True
        )
    else:
        st.warning("Nie udało się obliczyć dawki dla żadnego pliku.")

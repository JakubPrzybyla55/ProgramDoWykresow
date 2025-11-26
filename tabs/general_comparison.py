import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
import plotly.colors as pcolors

from utils import get_all_roast_files, parse_roasttime_csv, calculate_thermal_dose, get_agtron

def render(
    st,
    base_data_path: str,
    dose_t_base: float,
    dose_start_time: float
):
    """Renders the General Comparison Tab."""
    st.subheader("Porównanie Wszystkich Wypałów (Wszystkie Profile)")

    all_roast_files = get_all_roast_files(base_data_path)

    if not all_roast_files:
        st.info("Brak plików wypałów do analizy w żadnym z profili.")
        return

    all_roasts_data = []
    progress_bar = st.progress(0, text="Przetwarzanie wszystkich wypałów...")
    colors_cycle = pcolors.qualitative.Plotly
    fig_all_dose = go.Figure()

    for i, r_path in enumerate(all_roast_files):
        f_name = os.path.basename(r_path)
        try:
            profile_name_from_path = os.path.basename(os.path.dirname(os.path.dirname(r_path)))
        except:
            profile_name_from_path = "Nieznany"

        try:
            r_df, _ = parse_roasttime_csv(r_path)
            if 'IBTS Temp' in r_df.columns:
                r_df = calculate_thermal_dose(r_df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=dose_t_base, start_time_threshold=dose_start_time)
                if 'Thermal_Dose' in r_df.columns:
                    final_dose = r_df['Thermal_Dose'].iloc[-1]
                    duration = r_df['Time_Seconds'].iloc[-1]
                    agtron_val = get_agtron(os.path.join(base_data_path, profile_name_from_path), f_name) or 0.0
                    all_roasts_data.append({
                        "Profil": profile_name_from_path, "Nazwa Pliku": f_name, "Agtron": agtron_val,
                        "Całkowita Dawka": final_dose, "Czas Trwania": f"{int(duration//60)}:{int(duration%60):02d}",
                    })
                    color_idx = i % len(colors_cycle)
                    fig_all_dose.add_trace(go.Scatter(
                        x=r_df['Time_Seconds'], y=r_df['Thermal_Dose'], mode='lines',
                        name=f"{profile_name_from_path} / {f_name}",
                        line=dict(color=colors_cycle[color_idx], width=2), opacity=0.8,
                        hovertemplate=f"<b>{f_name}</b><br>Czas: %{{x:.0f}}s<br>Dawka: %{{y:.0f}}<extra></extra>"
                    ))
        except Exception as e:
            print(f"Błąd przetwarzania {f_name} dla symulacji ogólnej: {e}")
        progress_bar.progress((i + 1) / len(all_roast_files))

    progress_bar.empty()

    fig_all_dose.update_layout(
        template="plotly_dark", height=600, title="Krzywe Skumulowanej Dawki Termicznej (Wszystkie Profile)",
        xaxis_title="Czas (sekundy)", yaxis_title="Dawka Termiczna", hovermode="closest",
        margin=dict(t=50, b=0, l=0, r=0)
    )
    st.plotly_chart(fig_all_dose, use_container_width=True)

    if all_roasts_data:
        st.subheader("Dane Zbiorcze (Wszystkie Profile)")
        df_all = pd.DataFrame(all_roasts_data).sort_values(by="Agtron", ascending=False)
        st.dataframe(
            df_all,
            column_config={
                "Profil": st.column_config.TextColumn("Profil"),
                "Nazwa Pliku": st.column_config.TextColumn("Plik"),
                "Agtron": st.column_config.NumberColumn("Kolor (Agtron)", format="%.1f"),
                "Całkowita Dawka": st.column_config.NumberColumn("Dawka Total", format="%.0f"),
                "Czas Trwania": st.column_config.TextColumn("Czas"),
            },
            use_container_width=True, hide_index=True
        )
    else:
        st.warning("Nie udało się obliczyć dawki dla żadnego pliku.")

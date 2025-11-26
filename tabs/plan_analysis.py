import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import traceback

from utils import (
    parsuj_csv_roasttime,
    oblicz_ror,
    oblicz_ror_sg,
    oblicz_dawke_termiczna,
    wygladz_dane,
    dodaj_projekcje_l,
    dodaj_subplot_ustawien,
)
from state import AppState

def render(st: object, state: AppState):
    """Renders the Plan Analysis Tab."""

    # Przetwarzanie Danych
    actual_milestones = {}
    actual_df = pd.DataFrame()

    if state.selected_roast_path:
        try:
            actual_df, actual_milestones = parsuj_csv_roasttime(state.selected_roast_path)

            avg_interval = 1.0
            if not actual_df.empty and 'Time_Seconds' in actual_df.columns:
                 diffs = actual_df['Time_Seconds'].diff()
                 avg_interval = diffs.median()
                 if pd.isna(avg_interval) or avg_interval <= 0:
                     avg_interval = 1.0

            # Obliczenia RoR IBTS
            if 'IBTS Temp' in actual_df.columns:
                if state.ror_method_ibts == 'Średnia Ruchoma':
                    actual_df = oblicz_ror(actual_df, temp_col='IBTS Temp', time_col='Time_Seconds')
                    if 'Calc_RoR' in actual_df.columns:
                        smooth_samples = max(1, int(state.ibts_params['window_sec'] / avg_interval))
                        actual_df['RoR_Display'] = wygladz_dane(actual_df['Calc_RoR'], window=smooth_samples)
                else:
                    actual_df = oblicz_ror_sg(actual_df, temp_col='IBTS Temp', **state.ibts_params)
                    if 'Calc_RoR_SG' in actual_df.columns:
                        actual_df['RoR_Display'] = actual_df['Calc_RoR_SG']

            # Obliczenia RoR Probe
            if 'Bean Probe Temp' in actual_df.columns:
                if state.ror_method_probe == 'Średnia Ruchoma':
                    actual_df = oblicz_ror(actual_df, temp_col='Bean Probe Temp', time_col='Time_Seconds')
                    if 'Calc_RoR_Probe' in actual_df.columns:
                        smooth_samples = max(1, int(state.probe_params['window_sec'] / avg_interval))
                        actual_df['RoR_Display_Probe'] = wygladz_dane(actual_df['Calc_RoR_Probe'], window=smooth_samples)
                else:
                    actual_df = oblicz_ror_sg(actual_df, temp_col='Bean Probe Temp', **state.probe_params)
                    if 'Calc_RoR_SG_Probe' in actual_df.columns:
                        actual_df['RoR_Display_Probe'] = actual_df['Calc_RoR_SG_Probe']

            # Obliczenia Dawki Termicznej
            if 'IBTS Temp' in actual_df.columns:
                actual_df = oblicz_dawke_termiczna(actual_df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=state.dose_t_base, start_time_threshold=state.dose_start_time)
            if 'Bean Probe Temp' in actual_df.columns:
                actual_df = oblicz_dawke_termiczna(actual_df, temp_col='Bean Probe Temp', time_col='Time_Seconds', t_base=state.dose_t_base, start_time_threshold=state.dose_start_time)

        except Exception as e:
            st.error(f"Błąd wczytywania pliku wypału: {e}")
            traceback.print_exc()

    plan_df_sorted = state.plan_df.sort_values('Time_Seconds')

    # FIGURE 1: TEMPERATURE
    fig_temp = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.75, 0.25], subplot_titles=(f"Profil Temperatury: {state.selected_profile}", "Ustawienia"))
    if state.show_plan:
        for i, row in plan_df_sorted.iterrows():
            pos = "top center" if i % 2 == 0 else "bottom center"
            fig_temp.add_trace(go.Scatter(x=[row['Time_Seconds']], y=[row['Temperatura']], mode='markers+text', name='Plan', text=[row['Faza']], textposition=pos, marker=dict(size=12, color='cyan', symbol='x'), showlegend=(i==0)), row=1, col=1)
            dodaj_projekcje_l(fig_temp, row['Time_Seconds'], row['Temperatura'], 'cyan', row=1)
    if not actual_df.empty:
        if state.show_ibts:
            fig_temp.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['IBTS Temp'], mode='lines', name='Rzecz. IBTS', line=dict(color='orange', width=2)), row=1, col=1)
        if state.show_probe and 'Bean Probe Temp' in actual_df.columns:
            fig_temp.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['Bean Probe Temp'], mode='lines', name='Rzecz. Sonda', line=dict(color='lightgreen', width=2, dash='dot')), row=1, col=1)
        sorted_milestones = sorted(actual_milestones.items(), key=lambda x: x[1])
        for i, (name, time_sec) in enumerate(sorted_milestones):
            row = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
            if not row.empty:
                temp_val = row['IBTS Temp'].values[0]
                offset_y = 0
                if i > 0 and (time_sec - sorted_milestones[i-1][1]) < 30:
                    offset_y = 20 if (i % 2 != 0) else 0
                fig_temp.add_trace(go.Scatter(x=[time_sec], y=[temp_val], mode='markers', name=f'{name}', marker=dict(size=10, color='red', symbol='circle-open'), showlegend=False), row=1, col=1)
                fig_temp.add_annotation(x=time_sec, y=temp_val, text=name, showarrow=True, arrowhead=1, yshift=15 + offset_y if i%2==0 else -15 - offset_y, font=dict(color='red'), row=1, col=1)
                dodaj_projekcje_l(fig_temp, time_sec, temp_val, 'red', row=1)
    dodaj_subplot_ustawien(fig_temp, actual_df, state.plan_df, state.show_plan, row_idx=2)
    fig_temp.update_layout(template="plotly_dark", height=600, margin=dict(t=30, b=0, l=0, r=0), hovermode="x unified", legend=dict(orientation="v", yanchor="top", y=0.98, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.5)"))
    fig_temp.update_yaxes(title_text="Temperatura (°C)", row=1, col=1)
    fig_temp.update_yaxes(title_text="Wartość", range=state.settings_y_lim, dtick=1, row=2, col=1)
    fig_temp.update_xaxes(title_text="Czas (sekundy)", row=2, col=1)
    st.plotly_chart(fig_temp, use_container_width=True)

    # FIGURE 2: RoR
    if not actual_df.empty:
        fig_ror = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.75, 0.25], subplot_titles=("RoR (Szybkość Wzrostu)", "Ustawienia"))
        if state.show_ibts and 'RoR_Display' in actual_df.columns:
            fig_ror.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['RoR_Display'], mode='lines', name='RoR IBTS', line=dict(color='magenta', width=2)), row=1, col=1)
        if state.show_probe and 'RoR_Display_Probe' in actual_df.columns:
            fig_ror.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['RoR_Display_Probe'], mode='lines', name='RoR Sonda', line=dict(color='mediumspringgreen', width=2, dash='dot')), row=1, col=1)
        if state.show_plan:
            for _, row in plan_df_sorted.iterrows():
                 dodaj_projekcje_l(fig_ror, row['Time_Seconds'], None, 'cyan', row=1, show_y=False)
        for name, time_sec in actual_milestones.items():
             if 'RoR_Display' in actual_df.columns:
                row_actual = actual_df.iloc[(actual_df['Time_Seconds'] - time_sec).abs().argsort()[:1]]
                if not row_actual.empty:
                     ror_val = row_actual['RoR_Display'].values[0]
                     if pd.notna(ror_val):
                         fig_ror.add_trace(go.Scatter(x=[time_sec], y=[ror_val], mode='markers', name=name, marker=dict(size=8, color='red', symbol='circle-open'), showlegend=False), row=1, col=1)
                         fig_ror.add_annotation(x=time_sec, y=ror_val, text=name, showarrow=False, yshift=10, font=dict(color='red', size=9), row=1, col=1)
                         dodaj_projekcje_l(fig_ror, time_sec, ror_val, 'red', row=1)
                     else:
                         dodaj_projekcje_l(fig_ror, time_sec, None, 'red', row=1, show_y=False)
             else:
                 dodaj_projekcje_l(fig_ror, time_sec, None, 'red', row=1, show_y=False)
        dodaj_subplot_ustawien(fig_ror, actual_df, state.plan_df, state.show_plan, row_idx=2)
        fig_ror.update_layout(template="plotly_dark", height=500, margin=dict(t=30, b=0, l=0, r=0), hovermode="x unified", legend=dict(orientation="v", yanchor="top", y=0.98, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.5)"))
        fig_ror.update_yaxes(title_text="RoR (°C/min)", range=state.ror_y_lim, row=1, col=1)
        fig_ror.update_yaxes(title_text="Wartość", range=state.settings_y_lim, dtick=1, row=2, col=1)
        fig_ror.update_xaxes(title_text="Czas (sekundy)", row=2, col=1)
        st.plotly_chart(fig_ror, use_container_width=True)

    # FIGURE 3: THERMAL DOSE
    if not actual_df.empty and ('Thermal_Dose' in actual_df.columns or 'Thermal_Dose_Probe' in actual_df.columns):
        fig_dose = make_subplots(specs=[[{"secondary_y": True}]])
        fig_dose.update_layout(title_text="Skumulowana Dawka Termiczna")
        if state.show_ibts and 'IBTS Temp' in actual_df.columns:
            fig_dose.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['IBTS Temp'], name="Temp IBTS", line=dict(color='orange', width=1, dash='dash')), secondary_y=False)
        if state.show_probe and 'Bean Probe Temp' in actual_df.columns:
            fig_dose.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['Bean Probe Temp'], name="Temp Sonda", line=dict(color='lightgreen', width=1, dash='dot')), secondary_y=False)
        if state.show_ibts and 'Thermal_Dose' in actual_df.columns:
             fig_dose.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['Thermal_Dose'], name="Dawka IBTS", line=dict(color='red', width=3), fill='tozeroy', fillcolor='rgba(255, 0, 0, 0.1)'), secondary_y=True)
        if state.show_probe and 'Thermal_Dose_Probe' in actual_df.columns:
             fig_dose.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['Thermal_Dose_Probe'], name="Dawka Sonda", line=dict(color='green', width=3, dash='dash')), secondary_y=True)
        fig_dose.update_yaxes(title_text="Temperatura (°C)", secondary_y=False)
        fig_dose.update_yaxes(title_text="Dawka", secondary_y=True)
        fig_dose.update_xaxes(title_text="Czas (sekundy)")
        fig_dose.update_layout(template="plotly_dark", height=400, margin=dict(t=30, b=0, l=0, r=0), hovermode="x unified", legend=dict(orientation="v", yanchor="top", y=0.98, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.5)"))
        st.plotly_chart(fig_dose, use_container_width=True)

        # Metrics & Analysis
        st.subheader("Podsumowanie Dawki Termicznej")
        m_col1, m_col2, m_col3 = st.columns(3)
        if 'Thermal_Dose' in actual_df.columns:
            m_col1.metric("Całkowita Dawka (IBTS)", f"{actual_df['Thermal_Dose'].iloc[-1]:,.0f}")
        if 'Thermal_Dose_Probe' in actual_df.columns:
            m_col2.metric("Całkowita Dawka (Sonda)", f"{actual_df['Thermal_Dose_Probe'].iloc[-1]:,.0f}")

        try:
            x_plan, y_plan = plan_df_sorted['Time_Seconds'], plan_df_sorted['Temperatura']
            coeffs = np.polyfit(x_plan, y_plan, state.poly_degree)
            poly = np.poly1d(coeffs)
            max_time = max(x_plan.max(), actual_df['Time_Seconds'].max()) if not actual_df.empty else x_plan.max()
            time_grid = np.linspace(0, max_time, int(max_time) + 1)
            df_theoretical = pd.DataFrame({'Time_Seconds': time_grid, 'Theoretical_Temp': poly(time_grid)})
            df_theoretical = oblicz_dawke_termiczna(df_theoretical, temp_col='Theoretical_Temp', time_col='Time_Seconds', t_base=state.dose_t_base, start_time_threshold=state.dose_start_time)
            m_col3.metric("Teoretyczna Dawka (Plan)", f"{df_theoretical['Thermal_Dose'].iloc[-1]:,.0f}")
        except Exception as e:
            m_col3.metric("Teoretyczna Dawka (Plan)", "Błąd")
            print(f"Błąd obliczania dawki teoretycznej: {e}")

    # --- Analiza (Tables) ---
    if not actual_df.empty:
        st.header("Analiza")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Plan vs Rzeczywistość")
            comparison_data = []
            for _, row in state.plan_df.iterrows():
                phase_name, plan_time, plan_temp = row['Faza'], row['Time_Seconds'], row['Temperatura']
                actual_time, actual_temp = None, None
                matched_key = next((k for k in actual_milestones if k.lower() in phase_name.lower() or phase_name.lower() in k.lower()), None)
                if "start" in phase_name.lower() and 0 not in actual_milestones.values(): actual_time, matched_key = 0.0, "Start"
                elif matched_key: actual_time = actual_milestones[matched_key]
                if actual_time is not None:
                    r = actual_df.iloc[(actual_df['Time_Seconds'] - actual_time).abs().argsort()[:1]]
                    if not r.empty: actual_temp = r['IBTS Temp'].values[0]
                comparison_data.append({"Faza": phase_name, "Plan Czas": f"{int(plan_time//60)}:{int(plan_time%60):02d}", "Plan Temp": plan_temp, "Rzecz. Czas": f"{int(actual_time//60)}:{int(actual_time%60):02d}" if actual_time is not None else "-", "Rzecz. Temp": round(actual_temp, 1) if actual_temp else "-"})
            comparison_df = pd.DataFrame(comparison_data)
            if 'Rzecz. Temp' in comparison_df.columns:
                comparison_df['Rzecz. Temp'] = comparison_df['Rzecz. Temp'].astype(str).replace('nan', '-')
            st.table(comparison_df)
        with col2:
            st.subheader("Metryki Faz (Średni RoR)")
            key_events = {**actual_milestones}
            if 'Turning Point' not in key_events:
                 try:
                    early_df = actual_df[actual_df['Time_Seconds'] < 180]
                    if not early_df.empty:
                        temp_col = 'IBTS Temp' if 'IBTS Temp' in early_df.columns else 'Bean Probe Temp'
                        if temp_col in early_df.columns:
                            min_idx = early_df[temp_col].idxmin()
                            key_events['Turning Point'] = early_df.loc[min_idx, 'Time_Seconds']
                 except Exception: pass
            key_events['Start'], key_events['Drop'] = 0.0, actual_df['Time_Seconds'].max()
            sorted_events = sorted(key_events.items(), key=lambda x: x[1])
            phase_metrics = []
            for i in range(len(sorted_events) - 1):
                start_name, start_time = sorted_events[i]
                end_name, end_time = sorted_events[i+1]
                if end_time - start_time >= 10:
                    mask = (actual_df['Time_Seconds'] >= start_time) & (actual_df['Time_Seconds'] <= end_time)
                    if not actual_df.loc[mask].empty and 'RoR_Display' in actual_df.columns:
                        avg_ror = actual_df.loc[mask]['RoR_Display'].mean()
                        phase_metrics.append({"Faza": f"{start_name} -> {end_name}", "Średni RoR": round(avg_ror, 2)})
            st.table(pd.DataFrame(phase_metrics))

        # --- Wykres Dopasowania Wielomianem ---
        st.header("Analiza Teoretyczna - Dopasowanie Wielomianem do Planu")
        try:
            if 'df_theoretical' in locals() and not df_theoretical.empty:
                fig_poly = go.Figure()
                fig_poly.add_trace(go.Scatter(x=plan_df_sorted['Time_Seconds'], y=plan_df_sorted['Temperatura'], mode='markers', name='Punkty z Planu', marker=dict(size=10, color='cyan', symbol='x')))
                fig_poly.add_trace(go.Scatter(x=df_theoretical['Time_Seconds'], y=df_theoretical['Theoretical_Temp'], mode='lines', name=f'Dopasowanie (st. {state.poly_degree})', line=dict(color='lime', width=3)))
                fig_poly.update_layout(template="plotly_dark", height=400, title="Dopasowanie Krzywej Wielomianowej do Punktów Planu", xaxis_title="Czas (sekundy)", yaxis_title="Temperatura (°C)", margin=dict(t=50, b=0, l=0, r=0))
                st.plotly_chart(fig_poly, use_container_width=True)
        except NameError:
            st.warning("Nie można wygenerować wykresu dopasowania wielomianem z powodu wcześniejszego błędu.")
        except Exception as e:
            st.error(f"Wystąpił błąd podczas tworzenia wykresu dopasowania wielomianem: {e}")

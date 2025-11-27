import streamlit as st
import pandas as pd
import os
from state import AppState
from utils import parsuj_czas_do_sekund

def sort_plan_dataframe(df):
    """Sorts the plan DataFrame by 'Czas' chronologically."""
    if df.empty or 'Czas' not in df.columns:
        return df

    # Create a temporary column for sorting
    df['_sort_key'] = df['Czas'].apply(parsuj_czas_do_sekund)
    df = df.sort_values(by='_sort_key')
    df = df.drop(columns=['_sort_key'])
    return df

def render(st: object, state: AppState):
    """Renders the Plan Editor Tab."""
    st.subheader("Edytor Planu Wypału")

    edit_mode = st.radio(
        "Wybierz tryb pracy edytora:",
        ["Dodaj nowy plan", "Modyfikuj istniejący plan"],
        horizontal=True, label_visibility="collapsed"
    )

    plan_cols_config = {
        "Faza": st.column_config.TextColumn("Faza", required=True, help="Nazwa etapu, np. 'Yellowing'"),
        "Czas": st.column_config.TextColumn("Czas (mm:ss)", required=True, help="Czas od rozpoczęcia palenia."),
        "Temperatura": st.column_config.NumberColumn("Temperatura (°C)", required=True),
        "Nawiew": st.column_config.NumberColumn("Nawiew (0-9)"),
        "Moc": st.column_config.NumberColumn("Moc (0-9)")
    }

    if edit_mode == "Dodaj nowy plan":
        st.markdown("#### Tworzenie nowego planu")
        col1, col2 = st.columns(2)
        with col1:
            new_plan_profile = st.selectbox(
                "Wybierz profil, do którego dodać nowy plan",
                options=state.profiles,
                index=state.profiles.index(state.selected_profile) if state.selected_profile in state.profiles else 0,
                key="new_plan_profile_select"
            )
        with col2:
            new_plan_filename = st.text_input(
                "Nazwa pliku dla nowego planu (np. `nowy_eksperyment.csv`)",
                placeholder="plan.csv"
            )
        st.markdown("Wprowadź etapy planu poniżej. Możesz dodawać i usuwać wiersze.")

        df_new_plan = pd.DataFrame([
            {"Faza": "Preheat", "Czas": "0:00", "Temperatura": 180.0, "Nawiew": 0, "Moc": 0},
            {"Faza": "Charge", "Czas": "0:05", "Temperatura": 180.0, "Nawiew": 5, "Moc": 8},
            {"Faza": "Yellowing", "Czas": "4:00", "Temperatura": 160.0, "Nawiew": 4, "Moc": 7},
            {"Faza": "1st Crack", "Czas": "7:30", "Temperatura": 195.0, "Nawiew": 3, "Moc": 5},
            {"Faza": "Drop", "Czas": "9:00", "Temperatura": 205.0, "Nawiew": 0, "Moc": 0},
        ])

        edited_df_new = st.data_editor(df_new_plan, column_config=plan_cols_config, num_rows="dynamic", use_container_width=True, key="new_plan_editor")

        if st.button("Zapisz nowy plan", type="primary"):
            if not new_plan_filename:
                st.error("Proszę podać nazwę pliku.")
            elif not new_plan_filename.endswith('.csv'):
                st.error("Nazwa pliku musi kończyć się na `.csv`.")
            else:
                save_path_dir = os.path.join(state.base_data_path, new_plan_profile, 'Plan')
                os.makedirs(save_path_dir, exist_ok=True)
                save_path_file = os.path.join(save_path_dir, new_plan_filename)
                try:
                    # Sort before saving
                    final_df = sort_plan_dataframe(edited_df_new)
                    final_df.to_csv(save_path_file, index=False)
                    st.success(f"Zapisano plan w: `{save_path_file}`")
                    st.info("Nowy plan będzie dostępny po odświeżeniu strony lub zmianie profilu.")
                except Exception as e:
                    st.error(f"Nie udało się zapisać pliku: {e}")

    elif edit_mode == "Modyfikuj istniejący plan":
        if not state.plan_file_path:
            st.warning("Nie wybrano żadnego planu do edycji. Wybierz profil z planem w panelu bocznym.")
        else:
            st.markdown(f"#### Modyfikacja planu: `{os.path.basename(state.plan_file_path)}`")
            st.markdown("Zmodyfikuj etapy planu poniżej. Możesz dodawać i usuwać wiersze.")
            try:
                df_to_edit = pd.read_csv(state.plan_file_path)

                # Ensure Nawiew and Moc columns exist
                if 'Nawiew' not in df_to_edit.columns:
                    df_to_edit['Nawiew'] = 0
                if 'Moc' not in df_to_edit.columns:
                    df_to_edit['Moc'] = 0

                # Sort when loading
                df_to_edit = sort_plan_dataframe(df_to_edit)

                edited_df_existing = st.data_editor(df_to_edit, column_config=plan_cols_config, num_rows="dynamic", use_container_width=True, key="existing_plan_editor")
                if st.button("Zapisz zmiany w planie", type="primary"):
                    try:
                        # Sort before saving
                        final_df = sort_plan_dataframe(edited_df_existing)
                        final_df.to_csv(state.plan_file_path, index=False)
                        st.success(f"Zaktualizowano plan: `{state.plan_file_path}`")
                    except Exception as e:
                        st.error(f"Nie udało się zapisać pliku: {e}")
            except FileNotFoundError:
                 st.error(f"Nie można znaleźć pliku: {state.plan_file_path}")
            except Exception as e:
                 st.error(f"Błąd wczytywania planu do edycji: {e}")

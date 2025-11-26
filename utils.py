import pandas as pd
import io
import os
import numpy as np
import json
import plotly.graph_objects as go

# Próba importu scipy dla filtra Savitzky-Golaya
try:
    from scipy.signal import savgol_filter
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    savgol_filter = None

def parse_time_to_seconds(time_str):
    """Konwertuje ciąg czasu 'mm:ss' na sekundy (float)."""
    try:
        if pd.isna(time_str) or str(time_str).strip() in ['-', '', 'nan']:
            return None
        parts = str(time_str).split(':')
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
             return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        return float(time_str)
    except Exception:
        return None

def parse_roasttime_csv(file):
    """
    Parsuje plik CSV RoastTime.
    Zwraca:
        df: DataFrame z danymi szeregów czasowych.
        milestones: Słownik rzeczywistych zdarzeń {NazwaZdarzenia: CzasSekundy}.
    """
    content = ""
    try:
        # Streamlit UploadedFile
        if hasattr(file, 'getvalue'):
            val = file.getvalue()
            if isinstance(val, bytes):
                content = val.decode('utf-8')
            else:
                content = val
        # String path
        elif isinstance(file, str):
            if not os.path.exists(file):
                raise FileNotFoundError(f"Plik nie znaleziony: {file}")
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
        # StringIO/File-like
        elif hasattr(file, 'read'):
            data = file.read()
            if isinstance(data, bytes):
                content = data.decode('utf-8')
            else:
                content = data
    except Exception as e:
        raise ValueError(f"Nie udało się odczytać pliku: {e}")

    lines = content.split('\n')

    # --- Parsowanie kamieni milowych (sekcja metadanych) ---
    milestones = {}
    timeline_index = -1

    for i, line in enumerate(lines):
        if line.startswith("Timeline"):
            timeline_index = i
            break

        # Parsowanie Yellowing (Żółknięcie)
        if "Yellowing" in line:
            if i + 1 < len(lines):
                headers = line.split(',')
                next_line = lines[i+1]
                parts = next_line.split(',')
                try:
                    if "Start time" in headers:
                        idx = headers.index("Start time")
                    else:
                        idx = 2

                    if idx < len(parts):
                        t = parse_time_to_seconds(parts[idx])
                        if t is not None:
                            milestones['Yellowing'] = t
                except ValueError:
                    pass

        # Parsowanie 1st Crack (Pierwsze Pęknięcie)
        if "1st Crack" in line:
            if i + 2 < len(lines):
                data_line = lines[i+2]
                parts = data_line.split(',')
                try:
                     t = parse_time_to_seconds(parts[2])
                     if t is not None:
                         milestones['1st Crack'] = t
                except IndexError:
                    pass

    if timeline_index == -1:
        raise ValueError("Nie można znaleźć nagłówka 'Timeline' w pliku CSV.")

    # --- Parsowanie danych osi czasu ---
    header_index = timeline_index + 1
    header_keywords = ['temp', 'time', 'czas', 'ibts', 'probe', 'ror']

    for j in range(timeline_index, min(timeline_index + 5, len(lines))):
        line = lines[j]
        line_lower = line.lower()
        has_separator = ',' in line or ';' in line
        has_keyword = any(k in line_lower for k in header_keywords)
        if has_separator and has_keyword:
            header_index = j
            break

    csv_data = "\n".join(lines[header_index:])
    try:
        df = pd.read_csv(io.StringIO(csv_data), sep=None, engine='python')
    except:
        df = pd.read_csv(io.StringIO(csv_data))

    df.columns = df.columns.str.strip()
    columns_to_map = ['Time', 'IBTS Temp', 'IBTS ROR', 'Bean Probe Temp', 'Bean Probe ROR', 'Fan', 'Power']
    for col in columns_to_map:
        if col not in df.columns:
            for actual_col in df.columns:
                if col.lower() in actual_col.lower():
                    df.rename(columns={actual_col: col}, inplace=True)
                    break
    if 'Time' not in df.columns:
        cols = ", ".join(df.columns.tolist())
        raise ValueError(f"Nie znaleziono kolumny 'Time' w pliku CSV. Dostępne kolumny: {cols}")
    df['Time_Seconds'] = df['Time'].apply(parse_time_to_seconds)

    cols_to_numeric = ['IBTS Temp', 'IBTS ROR', 'Bean Probe Temp', 'Bean Probe ROR', 'Fan', 'Power']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    if not df.empty and 'Time_Seconds' in df.iloc[-1]:
         milestones['Drop'] = df.iloc[-1]['Time_Seconds']
    return df, milestones

def parse_profile_csv(file):
    """Parsuje plik CSV Profilu (Planu)."""
    try:
        df = pd.read_csv(file)
    except Exception as e:
        raise ValueError(f"Nie udało się odczytać pliku profilu: {e}")

    df.columns = df.columns.str.strip()
    if 'Czas' in df.columns:
        df['Time_Seconds'] = df['Czas'].apply(parse_time_to_seconds)
    elif 'Time' in df.columns:
        df['Time_Seconds'] = df['Time'].apply(parse_time_to_seconds)
    else:
        raise ValueError("Plik CSV profilu musi zawierać kolumnę 'Czas' lub 'Time'.")
    return df

def calculate_ror(df, temp_col='IBTS Temp', time_col='Time_Seconds'):
    """Oblicza RoR (Szybkość Wzrostu) metodą prostej różnicy."""
    if df.empty or time_col not in df.columns or temp_col not in df.columns:
        return df
    df = df.sort_values(by=time_col).copy()
    suffix = "_Probe" if "Probe" in temp_col else ""
    delta_temp = df[temp_col].diff()
    delta_time = df[time_col].diff().replace(0, np.nan)
    df[f'Calc_RoR{suffix}'] = (delta_temp / delta_time) * 60
    return df

def calculate_ror_sg(df, temp_col='IBTS Temp', time_col='Time_Seconds', window_length=15, polyorder=2, deriv=1):
    """Oblicza RoR przy użyciu filtra Savitzky'ego-Golaya."""
    suffix = "_Probe" if "Probe" in temp_col else ""
    col_name = f'Calc_RoR_SG{suffix}'
    if not SCIPY_AVAILABLE:
        df[col_name] = 0
        return df
    if df.empty or temp_col not in df.columns:
        return df
    if window_length % 2 == 0: window_length += 1
    if len(df) <= window_length:
        df[col_name] = 0
        return df

    avg_time_step = df[time_col].diff().median()
    if pd.isna(avg_time_step) or avg_time_step == 0:
        avg_time_step = 1.0
    try:
        series = df[temp_col].interpolate(method='linear').fillna(method='bfill').fillna(method='ffill')
        val_sg = savgol_filter(series, window_length=window_length, polyorder=polyorder, deriv=deriv)
        ror = (val_sg / avg_time_step**deriv) * (60**deriv)
        df[col_name] = ror
    except Exception as e:
        print(f"Błąd obliczania SG: {e}")
        df[col_name] = 0
    return df

def smooth_data(series, window=30):
    """Wygładza dane używając średniej ruchomej."""
    if window < 1: window = 1
    return series.rolling(window=window, min_periods=1, center=True).mean()

def get_profiles(base_path='data'):
    """Skanuje base_path i zwraca listę nazw profili."""
    if not os.path.exists(base_path): return []
    return sorted([d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))])

def get_roast_files(profile_name, base_path='data'):
    """Zwraca ścieżkę do pliku planu i listę ścieżek do plików wypałów."""
    profile_dir = os.path.join(base_path, profile_name)
    plan_dir = os.path.join(profile_dir, 'Plan')
    wypaly_dir = os.path.join(profile_dir, 'Wypaly')
    if not os.path.exists(wypaly_dir) and os.path.exists(os.path.join(profile_dir, 'Wypały')):
        wypaly_dir = os.path.join(profile_dir, 'Wypały')

    plan_file = None
    if os.path.exists(plan_dir):
        files = [f for f in os.listdir(plan_dir) if f.endswith('.csv')]
        if files: plan_file = os.path.join(plan_dir, files[0])

    roast_files = []
    if os.path.exists(wypaly_dir):
        roast_files = [os.path.join(wypaly_dir, f) for f in os.listdir(wypaly_dir) if f.endswith('.csv')]
    return plan_file, sorted(roast_files)

def get_all_roast_files(base_path='data'):
    """Skanuje wszystkie profile i zwraca listę ścieżek do wszystkich plików wypałów."""
    all_files = []
    for profile in get_profiles(base_path):
        _, roast_files = get_roast_files(profile, base_path)
        all_files.extend(roast_files)
    return all_files

def calculate_thermal_dose(df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=100.0, start_time_threshold=0.0):
    """Oblicza skumulowaną Dawkę Termiczną."""
    if df.empty or time_col not in df.columns or temp_col not in df.columns:
        return df
    df = df.copy()
    suffix = "_Probe" if "Probe" in temp_col else ""
    result_col = f'Thermal_Dose{suffix}'
    df[result_col] = np.nan
    df_calc = df[df[time_col] >= start_time_threshold].copy()
    if df_calc.empty:
        df[result_col] = 0.0
        return df
    df_calc = df_calc.sort_values(by=time_col)
    df_calc['delta_t'] = df_calc[time_col].diff().fillna(0)
    temp_avg = ((df_calc[temp_col] + df_calc[temp_col].shift(1)) / 2).fillna(df_calc[temp_col])
    weights = 2 ** ((temp_avg - t_base) / 10.0)
    increments = weights * df_calc['delta_t']
    df.loc[df_calc.index, result_col] = increments.cumsum()
    df[result_col] = df[result_col].fillna(0.0)
    return df

def load_metadata(profile_path):
    """Wczytuje metadata.json z folderu profilu."""
    meta_path = os.path.join(profile_path, 'metadata.json')
    if not os.path.exists(meta_path): return {}
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Błąd wczytywania metadata.json: {e}")
        return {}

def save_metadata(profile_path, data):
    """Zapisuje słownik data do metadata.json w folderze profilu."""
    meta_path = os.path.join(profile_path, 'metadata.json')
    try:
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Błąd zapisu metadata.json: {e}")

def get_agtron(profile_path, roast_filename):
    """Pobiera wartość Agtron dla danego pliku wypału."""
    return load_metadata(profile_path).get('agtron', {}).get(roast_filename)

def set_agtron(profile_path, roast_filename, value):
    """Ustawia wartość Agtron dla danego pliku wypału."""
    data = load_metadata(profile_path)
    if 'agtron' not in data: data['agtron'] = {}
    data['agtron'][roast_filename] = value
    save_metadata(profile_path, data)

# --- Zarządzanie metadanymi planów ---
PLANS_METADATA_PATH = 'data/plans_metadata.csv'

def load_plans_metadata():
    """Wczytuje metadane planów z pliku CSV. Jeśli plik nie istnieje, tworzy pusty DataFrame."""
    if not os.path.exists(PLANS_METADATA_PATH):
        return pd.DataFrame(columns=['plan_name', 'agtron', 'A', 'Ea', 'R'])
    try:
        return pd.read_csv(PLANS_METADATA_PATH)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=['plan_name', 'agtron', 'A', 'Ea', 'R'])


def save_plans_metadata(df):
    """Zapisuje metadane planów do pliku CSV."""
    os.makedirs(os.path.dirname(PLANS_METADATA_PATH), exist_ok=True)
    df.to_csv(PLANS_METADATA_PATH, index=False)


def get_plan_metadata(plan_name):
    """Pobiera metadane dla konkretnego planu, zwracając domyślne wartości, jeśli brak wpisu."""
    df = load_plans_metadata()
    plan_data = df[df['plan_name'] == plan_name]

    if not plan_data.empty:
        return plan_data.iloc[0].to_dict()
    else:
        # Zwraca słownik z domyślnymi wartościami
        return {
            'plan_name': plan_name,
            'agtron': 85.0,
            'A': 0.788,
            'Ea': 26.02,
            'R': 0.008314
        }

def update_plan_metadata(plan_name, new_data):
    """Aktualizuje lub dodaje metadane dla konkretnego planu."""
    df = load_plans_metadata()
    plan_exists = df['plan_name'] == plan_name

    if plan_exists.any():
        # Aktualizuje istniejący wiersz
        for key, value in new_data.items():
            df.loc[plan_exists, key] = value
    else:
        # Dodaje nowy wiersz
        new_row = {'plan_name': plan_name, **new_data}
        new_df = pd.DataFrame([new_row])
        df = pd.concat([df, new_df], ignore_index=True)

    save_plans_metadata(df)


def calculate_thermal_dose_arrhenius(df, temp_col='IBTS Temp', time_col='Time_Seconds', A=0.788, Ea=26.02, R=0.008314, start_time_threshold=0.0):
    """Oblicza skumulowaną Dawkę Termiczną modelem Arrheniusa."""
    if df.empty or time_col not in df.columns or temp_col not in df.columns:
        return df

    df = df.copy()
    suffix = "_Probe" if "Probe" in temp_col else ""
    result_col = f'Thermal_Dose_Arrhenius{suffix}'
    df[result_col] = np.nan

    df_calc = df[df[time_col] >= start_time_threshold].copy()
    if df_calc.empty:
        df[result_col] = 0.0
        return df

    df_calc = df_calc.sort_values(by=time_col)
    df_calc['delta_t'] = df_calc[time_col].diff().fillna(0)

    # Użycie średniej temperatury w interwale dla większej dokładności
    temp_avg_celsius = ((df_calc[temp_col] + df_calc[temp_col].shift(1)) / 2).fillna(df_calc[temp_col])
    temp_avg_kelvin = temp_avg_celsius + 273.15

    # Obliczenie k(T)
    k_T = A * np.exp(-Ea / (R * temp_avg_kelvin))

    increments = k_T * df_calc['delta_t']
    df.loc[df_calc.index, result_col] = increments.cumsum()
    df[result_col] = df[result_col].fillna(0.0)

    return df


# --- Funkcje pomocnicze do wykresów ---

def add_l_projection(fig, x_val, y_val, color, row=1, col=1, is_time_x=True, show_y=True, show_x=True, text_offset_y=0):
    """Dodaje projekcje w kształcie litery 'L' do wykresu."""
    y_axis_name, x_axis_name = f"y{row}" if row > 1 else "y", f"x{col}" if col > 1 else "x"
    yref_domain, xref_domain = f"{y_axis_name} domain", f"{x_axis_name} domain"

    if y_val is None:
        fig.add_vline(x=x_val, line_width=1, line_dash="dash", line_color=color, opacity=0.5, row=row, col=col)
    else:
        fig.add_shape(type="line", x0=x_val, y0=0, x1=x_val, y1=y_val, line=dict(color=color, width=1, dash="dash"), row=row, col=col)
        if show_y:
            fig.add_shape(type="line", x0=0, y0=y_val, x1=x_val, y1=y_val, line=dict(color=color, width=1, dash="dash"), row=row, col=col)
    if show_x:
        x_text = f"{int(x_val//60)}:{int(x_val%60):02d}" if is_time_x else f"{x_val:.1f}"
        fig.add_annotation(x=x_val, y=0, xref=x_axis_name, yref=yref_domain, text=x_text, showarrow=False, font=dict(size=10, color=color), yshift=-15, bgcolor="rgba(0,0,0,0.5)")
    if show_y and y_val is not None:
        fig.add_annotation(x=0, y=y_val, xref=xref_domain, yref=y_axis_name, text=f"{y_val:.1f}", showarrow=False, font=dict(size=10, color=color), xshift=-25, xanchor="right", bgcolor="rgba(0,0,0,0.5)")

def add_settings_subplot(fig_main, actual_df: pd.DataFrame, plan_df: pd.DataFrame, show_plan: bool, row_idx=2):
    """Dodaje subplot z ustawieniami (Moc/Nawiew)."""
    if not actual_df.empty:
        if 'Fan' in actual_df.columns:
            fig_main.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['Fan'], name='Rzecz. Nawiew', line_shape='hv', line=dict(color='cornflowerblue', width=2), legendgroup='settings'), row=row_idx, col=1)
        if 'Power' in actual_df.columns:
            fig_main.add_trace(go.Scatter(x=actual_df['Time_Seconds'], y=actual_df['Power'], name='Rzecz. Moc', line_shape='hv', line=dict(color='mediumpurple', width=2), legendgroup='settings'), row=row_idx, col=1)
    if show_plan:
        if 'Nawiew' in plan_df.columns:
            fig_main.add_trace(go.Scatter(x=plan_df['Time_Seconds'], y=plan_df['Nawiew'], mode='markers+text', name='Plan Nawiew', text=plan_df['Nawiew'], textposition="top center", marker=dict(color='cyan', symbol='triangle-up'), legendgroup='settings'), row=row_idx, col=1)
        if 'Moc' in plan_df.columns:
            fig_main.add_trace(go.Scatter(x=plan_df['Time_Seconds'], y=plan_df['Moc'], mode='markers+text', name='Plan Moc', text=plan_df['Moc'], textposition="bottom center", marker=dict(color='magenta', symbol='triangle-down'), legendgroup='settings'), row=row_idx, col=1)

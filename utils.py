import pandas as pd
import io
import os
import numpy as np

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
    # Pomijamy linię "Timeline" i bierzemy następną jako nagłówek
    csv_data = "\n".join(lines[timeline_index+1:])
    try:
        # Próba autodetekcji separatora
        df = pd.read_csv(io.StringIO(csv_data), sep=None, engine='python')
    except:
        # Fallback na domyślny
        df = pd.read_csv(io.StringIO(csv_data))

    df.columns = df.columns.str.strip()

    required_columns = ['Time', 'IBTS Temp', 'IBTS ROR']
    for col in required_columns:
        if col not in df.columns:
            for actual_col in df.columns:
                if col.lower() in actual_col.lower():
                    df.rename(columns={actual_col: col}, inplace=True)
                    break

    if 'Time' in df.columns:
        df['Time_Seconds'] = df['Time'].apply(parse_time_to_seconds)
    else:
        # Jeśli po wszystkich próbach nie ma kolumny Time, rzucamy błąd
        cols = ", ".join(df.columns.tolist())
        raise ValueError(f"Nie znaleziono kolumny 'Time' w pliku CSV. Dostępne kolumny: {cols}")

    cols_to_numeric = ['IBTS Temp', 'IBTS ROR', 'Bean Probe Temp', 'Bean Probe ROR', 'Fan', 'Power']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # --- Dodanie punktu Drop (ostatni punkt) ---
    if not df.empty:
        last_row = df.iloc[-1]
        if 'Time_Seconds' in last_row:
             milestones['Drop'] = last_row['Time_Seconds']

    return df, milestones

def parse_profile_csv(file):
    """
    Parsuje plik CSV Profilu (Planu).
    """
    try:
        if isinstance(file, str):
            if not os.path.exists(file):
                raise FileNotFoundError(f"Plik nie znaleziony: {file}")
            df = pd.read_csv(file)
        else:
            if hasattr(file, 'seek'):
                file.seek(0)
            df = pd.read_csv(file)
    except Exception as e:
        raise ValueError(f"Nie udało się odczytać pliku profilu: {e}")

    df.columns = df.columns.str.strip()

    if 'Czas' in df.columns:
        df['Time_Seconds'] = df['Czas'].apply(parse_time_to_seconds)
    elif 'Time' in df.columns:
        df['Time_Seconds'] = df['Time'].apply(parse_time_to_seconds)
    else:
        # Fallback na 3 kolumny
        if len(df.columns) == 3:
            df.columns = ['Faza', 'Czas', 'Temperatura']
            df['Time_Seconds'] = df['Czas'].apply(parse_time_to_seconds)
        else:
            # Sprawdźmy czy to stary format bez nawiewu/mocy
            # Jeśli nie ma Czas/Time, ale są inne kolumny, może być problem.
            # Ale jeśli jest Czas, to OK.
            if 'Czas' not in df.columns and 'Time' not in df.columns:
                 raise ValueError("Plik CSV profilu musi zawierać kolumnę 'Czas' lub 'Time'.")

    return df

def calculate_ror(df, temp_col='IBTS Temp', time_col='Time_Seconds', window_seconds=10):
    """
    Oblicza RoR (Szybkość Wzrostu) metodą prostej różnicy (pochodna dyskretna).
    """
    if df.empty or time_col not in df.columns or temp_col not in df.columns:
        return df

    df = df.sort_values(by=time_col).copy()

    # Obliczamy interwał próbkowania (zakładając w miarę stały)
    # Jeśli dane są nierówne, lepiej użyć shift opartego na indeksie, który w przybliżeniu odpowiada sekundom
    # Tutaj użyjemy shiftu o liczbę wierszy odpowiadającą mniej więcej oknu czasowemu
    # Najpierw spróbujmy znaleźć ile wierszy to 'window_seconds'

    avg_diff = df[time_col].diff().mean()
    if pd.isna(avg_diff) or avg_diff == 0:
        periods = 1
    else:
        periods = int(round(window_seconds / avg_diff))
        if periods < 1:
            periods = 1

    ror_col_name = 'Calc_RoR'
    # Jeśli liczymy dla Probe, nazwijmy inaczej? Nie, funkcja zwraca df z jedną kolumną ROR.
    # Warto byłoby sparametryzować nazwę kolumny wynikowej, ale na razie użyjmy Calc_RoR
    # Jeśli temp_col to Probe, wynik też powinien być distinct.

    # Modyfikacja: Zwracajmy serię lub dodawajmy kolumnę z sufiksem
    suffix = ""
    if "Probe" in temp_col:
        suffix = "_Probe"

    df[f'Calc_RoR{suffix}'] = df[temp_col].diff(periods=periods) / df[time_col].diff(periods=periods) * 60

    return df

def calculate_ror_sg(df, temp_col='IBTS Temp', time_col='Time_Seconds', window_length=15, polyorder=2):
    """
    Oblicza RoR przy użyciu filtra Savitzky'ego-Golaya (wygładzanie + pochodna).
    """

    suffix = ""
    if "Probe" in temp_col:
        suffix = "_Probe"
    col_name = f'Calc_RoR_SG{suffix}'

    if not SCIPY_AVAILABLE:
        # Jeśli scipy nie jest dostępne, zwracamy 0 i logujemy (lub można rzucić błąd)
        print("Scipy nie jest zainstalowane. Metoda Savitzky-Golay niedostępna.")
        df[col_name] = 0
        return df

    if df.empty or temp_col not in df.columns:
        return df

    # Savgol wymaga nieparzystej długości okna
    if window_length % 2 == 0:
        window_length += 1

    # Długość okna nie może przekraczać długości danych
    if len(df) <= window_length:
        window_length = len(df) if len(df) % 2 != 0 else len(df) - 1
        if window_length < polyorder + 2:
             # Za mało danych na sensowne obliczenia
             df[col_name] = 0
             return df

    # Używamy pochodnej (deriv=1) i skalujemy (delta)
    # Ważne: delta powinna być średnim krokiem czasowym w sekundach, ale
    # poniewaz savgol działa na indeksach, wynik jest "na próbkę".
    # Musimy to przeliczyć na "na minutę".

    avg_time_step = df[time_col].diff().median()
    if pd.isna(avg_time_step) or avg_time_step == 0:
        avg_time_step = 1.0 # fallback

    try:
        # Obliczamy pierwszą pochodną (temp/próbkę)
        # Nalezy usunac NaNy przed savgol
        series = df[temp_col].interpolate(method='linear').fillna(method='bfill').fillna(method='ffill')

        deriv = savgol_filter(series, window_length=window_length, polyorder=polyorder, deriv=1)

        # Konwersja: (Stopnie / Próbka) * (1 Próbka / X sekund) * (60 sekund / 1 minuta)
        # = Stopnie / X sekund * 60
        # = Stopnie/Sekunda * 60 = Stopnie/Minuta

        ror = (deriv / avg_time_step) * 60
        df[col_name] = ror
    except Exception as e:
        print(f"Błąd obliczania SG: {e}")
        df[col_name] = 0

    return df

def smooth_data(series, window=30):
    """
    Wygładza dane używając średniej ruchomej.
    """
    return series.rolling(window=window, min_periods=1, center=True).mean()

# --- Funkcje zarządzania plikami ---

def get_profiles(base_path='data'):
    """
    Skanuje base_path i zwraca listę nazw profili (podkatalogi).
    """
    if not os.path.exists(base_path):
        return []

    profiles = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    return sorted(profiles)

def get_roast_files(profile_name, base_path='data'):
    """
    Zwraca ścieżkę do pliku planu i listę ścieżek do plików wypałów.
    Struktura:
       data/ProfileName/Plan/*.csv (bierze pierwszy)
       data/ProfileName/Wypaly/*.csv (zwraca wszystkie)
    """
    profile_dir = os.path.join(base_path, profile_name)
    plan_dir = os.path.join(profile_dir, 'Plan')
    wypaly_dir = os.path.join(profile_dir, 'Wypaly')

    # Sprawdź 'Wypały' jeśli 'Wypaly' nie istnieje
    if not os.path.exists(wypaly_dir) and os.path.exists(os.path.join(profile_dir, 'Wypały')):
        wypaly_dir = os.path.join(profile_dir, 'Wypały')

    plan_file = None
    if os.path.exists(plan_dir):
        files = [f for f in os.listdir(plan_dir) if f.endswith('.csv')]
        if files:
            plan_file = os.path.join(plan_dir, files[0])

    roast_files = []
    if os.path.exists(wypaly_dir):
        roast_files = [os.path.join(wypaly_dir, f) for f in os.listdir(wypaly_dir) if f.endswith('.csv')]

    return plan_file, sorted(roast_files)

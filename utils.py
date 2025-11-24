import pandas as pd
import io
import os
import numpy as np
import json

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
    # Inteligentne szukanie nagłówka. Czasami jest w tej samej linii co "Timeline", czasami niżej.
    header_index = timeline_index + 1 # Domyślnie: linia po Timeline

    # Szukamy wiersza nagłówkowego w kilku kolejnych liniach
    # Szukamy słów kluczowych typowych dla nagłówków
    header_keywords = ['temp', 'time', 'czas', 'ibts', 'probe', 'ror']

    for j in range(timeline_index, min(timeline_index + 5, len(lines))):
        line = lines[j]
        line_lower = line.lower()
        # Musi zawierać separator ORAZ słowo kluczowe, aby nie pomylić z samym "Timeline"
        has_separator = ',' in line or ';' in line
        has_keyword = any(k in line_lower for k in header_keywords)

        # Wyjątek: jeśli linia to np. "Time, Temp" (header w samej linii Timeline)
        if has_separator and has_keyword:
            header_index = j
            break

    csv_data = "\n".join(lines[header_index:])
    try:
        # Próba autodetekcji separatora
        df = pd.read_csv(io.StringIO(csv_data), sep=None, engine='python')
    except:
        # Fallback na domyślny
        df = pd.read_csv(io.StringIO(csv_data))

    df.columns = df.columns.str.strip()

    # Rozszerzona lista kolumn do wyszukiwania (również opcjonalne)
    # Kolejność: Najpierw szukamy wymaganych, potem opcjonalnych
    columns_to_map = [
        'Time', 'IBTS Temp', 'IBTS ROR',
        'Bean Probe Temp', 'Bean Probe ROR',
        'Fan', 'Power'
    ]

    for col in columns_to_map:
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

def calculate_ror(df, temp_col='IBTS Temp', time_col='Time_Seconds'):
    """
    Oblicza RoR (Szybkość Wzrostu) metodą prostej różnicy (pochodna dyskretna) punkt-do-punktu.
    Formuła: (Temp2 - Temp1) * 60 / (Time2 - Time1)
    """
    if df.empty or time_col not in df.columns or temp_col not in df.columns:
        return df

    df = df.sort_values(by=time_col).copy()

    suffix = ""
    if "Probe" in temp_col:
        suffix = "_Probe"

    # Obliczamy różnice
    delta_temp = df[temp_col].diff()
    delta_time = df[time_col].diff()

    # RoR = (dTemp / dTime) * 60
    # Obsługa dzielenia przez zero (jeśli delta_time = 0, np. duplikaty czasu)
    # Zamieniamy 0 na NaN, żeby wynik był NaN, a nie Inf (co psuje wykresy)
    delta_time = delta_time.replace(0, np.nan)

    df[f'Calc_RoR{suffix}'] = (delta_temp / delta_time) * 60

    return df

def calculate_ror_sg(df, temp_col='IBTS Temp', time_col='Time_Seconds', window_length=15, polyorder=2, deriv=1):
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
        # Obliczamy pochodną rzędu 'deriv' (temp/próbkę^deriv)
        # Nalezy usunac NaNy przed savgol
        series = df[temp_col].interpolate(method='linear').fillna(method='bfill').fillna(method='ffill')

        val_sg = savgol_filter(series, window_length=window_length, polyorder=polyorder, deriv=deriv)

        # Konwersja jednostek
        # Dla deriv=1: (stopnie/próbkę) / (sekund/próbkę) * 60 = stopnie/min
        # Dla deriv=2: (stopnie/próbkę^2) / (sekund/próbkę)^2 * 60?
        # Zwykle Acceleration to stopnie/min^2.
        # Jeśli to ma być RoR (stopnie/min), to deriv=1.
        # Jeśli user chce deriv=2, to pewnie chce Acceleration (stopnie/min^2) lub krzywiznę.
        # Skalowanie: val_sg / (avg_time_step ** deriv)
        # Jeśli wynik ma być "na minutę" (lub "na minutę kwadrat"):
        # Unit correction: * 60 (dla RoR) lub * 3600 (dla Accel)?
        # Zostawmy * 60 dla kompatybilności z wykresem RoR, ale dla deriv>1 jednostki są inne.
        # User prosił o "możliwość zmiany deriv", więc dostarczamy surowy wynik przekształcony na jednostkę czasu.

        scale_factor = 60 if deriv == 1 else 1 # Dla deriv!=1 nie skalujemy automatycznie na minuty w ten sam sposób, chyba że user tego oczekuje.
        # Ale 'calculate_ror' sugeruje Rate.
        # Przyjmijmy konsekwentnie skalowanie czasu:
        # Wynik surowy to d^n T / dn Samples.
        # d Samples = dt Seconds.
        # d^n T / dt^n Seconds^n.
        # Żeby mieć "na minutę^n", mnożymy przez 60^n?
        # Zostawmy proste skalowanie * 60 dla RoR (deriv=1).
        # Dla innych zostawmy tak jak jest w logice (dzielenie przez krok czasu).

        # Jeśli deriv=1:
        # (val / dt) * 60

        if deriv == 1:
            ror = (val_sg / avg_time_step) * 60
        else:
            # Dla wyższych pochodnych, np. 2:
            # val / (dt^2)
            # Wynik w jednostkach T/s^2.
            ror = val_sg / (avg_time_step ** deriv)

            # Opcjonalnie konwersja na minuty?
            # User pewnie chce poeksperymentować.
            # Zostawmy w jednostkach sekundy w mianowniku, chyba że to RoR.
            # Ale skoro to idzie na wykres RoR, wartości będą rzędu 0.00x jeśli to s^2.
            # Zróbmy * 60^deriv.
            ror = ror * (60 ** deriv)

        df[col_name] = ror
    except Exception as e:
        print(f"Błąd obliczania SG: {e}")
        df[col_name] = 0

    return df

def smooth_data(series, window=30):
    """
    Wygładza dane używając średniej ruchomej.
    Window to liczba próbek.
    """
    if window < 1:
        window = 1
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

def calculate_thermal_dose(df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=100.0, start_time_threshold=0.0):
    """
    Oblicza skumulowaną Dawkę Termiczną.

    Wzór wagi: V(T) = 2 ** ((T - T_bazowa) / 10)
    Przyrost = V(T_srednia) * delta_t_sekundy

    Args:
        df: DataFrame z danymi.
        temp_col: Nazwa kolumny z temperaturą.
        time_col: Nazwa kolumny z czasem (w sekundach).
        t_base: Temperatura bazowa (waga=1).
        start_time_threshold: Czas początkowy (w sekundach), od którego liczymy dawkę.

    Returns:
        df: DataFrame z dodaną kolumną 'Thermal_Dose_<Sensor>' (lub podobną).
    """
    if df.empty or time_col not in df.columns or temp_col not in df.columns:
        return df

    # Pracujemy na kopii, aby nie modyfikować oryginału i zresetować kolumnę
    df = df.copy()

    suffix = "_Probe" if "Probe" in temp_col else ""
    result_col = f'Thermal_Dose{suffix}'

    # Reset kolumny (wypełnij NaN), aby usunąć stare dane w przypadku ponownego obliczania
    df[result_col] = np.nan

    # Tworzymy podzbiór do obliczeń
    df_calc = df[df[time_col] >= start_time_threshold].copy()

    if df_calc.empty:
        df[result_col] = 0.0
        return df

    df_calc = df_calc.sort_values(by=time_col)

    # Oblicz delta_t (czas trwania kroku)
    # Dla metody trapezów lub prostokątów:
    # Użyjemy metody prostokątów "forward" lub trapezów.
    # delta_t między punktem i a i+1.
    # W pandas diff() daje (i) - (i-1).

    # diff() na czasie daje czas trwania OD poprzedniego do obecnego.
    df_calc['delta_t'] = df_calc[time_col].diff().fillna(0)

    # Dla pierwszego punktu po odcięciu, delta_t jest nieokreślone (lub 0, lub od start_time_threshold).
    # Jeśli start_time_threshold to np. 5s, a pierwszy punkt to 5.2s, to delta_t = 0.2?
    # Prościej: przyjmijmy, że delta_t to różnica między kolejnymi próbkami wewnątrz wyfiltrowanego zbioru.
    # Pierwszy punkt w wyfiltrowanym zbiorze ma dawkę 0 (start akumulacji).

    # Wzór wagi dla każdego punktu (używamy temperatury w punkcie, ew. średniej z poprzednim)
    # Użyjmy temperatury w punkcie bieżącym (metoda prostokątów prawostronnych)
    # lub średniej (metoda trapezów). Metoda trapezów jest dokładniejsza.

    temp_current = df_calc[temp_col]
    temp_prev = df_calc[temp_col].shift(1)

    # Średnia temperatura w interwale
    # Dla pierwszego punktu (gdzie prev jest NaN), średnia to po prostu current (choć i tak delta_t jest 0 lub nan)
    temp_avg = (temp_current + temp_prev) / 2
    temp_avg = temp_avg.fillna(temp_current)

    # Waga
    weights = 2 ** ((temp_avg - t_base) / 10.0)

    # Przyrost
    increments = weights * df_calc['delta_t']

    # Skumulowana suma
    cumulative = increments.cumsum()

    # Przypisanie do df_calc
    df_calc[result_col] = cumulative

    # Teraz musimy to zmapować z powrotem do głównego df
    df.loc[df_calc.index, result_col] = df_calc[result_col]

    # Wypełnienie NaN zerami (dla czasów przed startem)
    df[result_col] = df[result_col].fillna(0.0)

    return df

# --- Metadata (Agtron) Management ---

def load_metadata(profile_path):
    """
    Wczytuje metadata.json z folderu profilu.
    Zwraca słownik. Jeśli plik nie istnieje lub jest uszkodzony, zwraca pusty słownik.
    Struktura:
    {
        "agtron": {
             "filename1.csv": 55.5,
             "filename2.csv": 60.0
        }
    }
    """
    meta_path = os.path.join(profile_path, 'metadata.json')
    if not os.path.exists(meta_path):
        return {}

    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Błąd wczytywania metadata.json: {e}")
        return {}

def save_metadata(profile_path, data):
    """
    Zapisuje słownik data do metadata.json w folderze profilu.
    """
    meta_path = os.path.join(profile_path, 'metadata.json')
    try:
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Błąd zapisu metadata.json: {e}")

def get_agtron(profile_path, roast_filename):
    """
    Pobiera wartość Agtron dla danego pliku wypału. Zwraca None, jeśli brak.
    """
    data = load_metadata(profile_path)
    agtron_data = data.get('agtron', {})
    return agtron_data.get(roast_filename)

def set_agtron(profile_path, roast_filename, value):
    """
    Ustawia wartość Agtron dla danego pliku wypału i zapisuje do pliku.
    """
    data = load_metadata(profile_path)
    if 'agtron' not in data:
        data['agtron'] = {}

    data['agtron'][roast_filename] = value
    save_metadata(profile_path, data)

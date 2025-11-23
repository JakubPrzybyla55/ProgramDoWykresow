import pandas as pd
import io
import os

def parse_time_to_seconds(time_str):
    """Converts a time string 'mm:ss' to seconds (float)."""
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
    Parses the RoastTime CSV file.
    Returns:
        df: DataFrame with time-series data.
        milestones: Dictionary of actual events {EventName: TimeSeconds}.
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
                raise FileNotFoundError(f"File not found: {file}")
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
        raise ValueError(f"Failed to read file: {e}")

    lines = content.split('\n')

    # --- Parse Milestones (Metadata section) ---
    milestones = {}
    timeline_index = -1

    for i, line in enumerate(lines):
        if line.startswith("Timeline"):
            timeline_index = i
            break

        # Yellowing Parsing
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

        # 1st Crack Parsing
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
        raise ValueError("Could not find 'Timeline' header in the CSV file.")

    # --- Parse Timeline Data ---
    csv_data = "\n".join(lines[timeline_index:])
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

    cols_to_numeric = ['IBTS Temp', 'IBTS ROR', 'Bean Probe Temp', 'Bean Probe ROR']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df, milestones

def parse_profile_csv(file):
    """
    Parses the Profile CSV file.
    """
    # Handle file path vs file-like object
    try:
        if isinstance(file, str):
            if not os.path.exists(file):
                raise FileNotFoundError(f"File not found: {file}")
            df = pd.read_csv(file)
        else:
            # If it's a StringIO or UploadedFile
            # Reset pointer just in case
            if hasattr(file, 'seek'):
                file.seek(0)
            df = pd.read_csv(file)
    except Exception as e:
        raise ValueError(f"Failed to read profile file: {e}")

    df.columns = df.columns.str.strip()

    if 'Czas' in df.columns:
        df['Time_Seconds'] = df['Czas'].apply(parse_time_to_seconds)
    elif 'Time' in df.columns:
        df['Time_Seconds'] = df['Time'].apply(parse_time_to_seconds)
    else:
        if len(df.columns) == 3:
            df.columns = ['Faza', 'Czas', 'Temperatura']
            df['Time_Seconds'] = df['Czas'].apply(parse_time_to_seconds)
        else:
             raise ValueError("Profile CSV must have a 'Czas' or 'Time' column.")

    return df

def calculate_ror(df, temp_col='IBTS Temp', time_col='Time_Seconds', window_seconds=10):
    """
    Calculates RoR (Rate of Rise).
    """
    if df.empty or time_col not in df.columns:
        return df

    df = df.sort_values(by=time_col).copy()
    df['Calc_RoR'] = df[temp_col].diff(periods=window_seconds) / df[time_col].diff(periods=window_seconds) * 60

    return df

def smooth_data(series, window=30):
    """
    Smooths data using a rolling mean.
    """
    return series.rolling(window=window, min_periods=1, center=True).mean()

# --- New File Management Functions ---

def get_profiles(base_path='data'):
    """
    Scans the base_path and returns a list of profile names (subdirectories).
    """
    if not os.path.exists(base_path):
        return []

    profiles = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    return sorted(profiles)

def get_roast_files(profile_name, base_path='data'):
    """
    Returns the path to the plan file and a list of paths to roast files.
    Structure:
       data/ProfileName/Plan/*.csv (takes first one)
       data/ProfileName/Wypaly/*.csv (returns all)
    """
    profile_dir = os.path.join(base_path, profile_name)
    plan_dir = os.path.join(profile_dir, 'Plan')
    wypaly_dir = os.path.join(profile_dir, 'Wypaly') # Using 'Wypaly' without special chars for safety, or check both

    # Check for 'Wypały' if 'Wypaly' doesn't exist
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

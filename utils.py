import pandas as pd
import io
import re

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
    # Handle different file-like objects
    content = ""
    try:
        # Streamlit UploadedFile (BytesIO-like)
        if hasattr(file, 'getvalue'):
            val = file.getvalue()
            if isinstance(val, bytes):
                content = val.decode('utf-8')
            else:
                content = val
        # String path
        elif isinstance(file, str):
             with open(file, 'r') as f:
                 content = f.read()
        # StringIO or file-like opened in text mode
        elif hasattr(file, 'read'):
             # Try reading
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
            # Example: Yellowing,Start index,Start time,,,,,,
            # Next line: ,461,3:50,,,,,,
            if i + 1 < len(lines):
                headers = line.split(',')
                next_line = lines[i+1]
                parts = next_line.split(',')
                try:
                    # Find column index for "Start time" if possible
                    if "Start time" in headers:
                        idx = headers.index("Start time")
                    else:
                        # Fallback based on image: index 2
                        idx = 2

                    if idx < len(parts):
                        t = parse_time_to_seconds(parts[idx])
                        if t is not None:
                            milestones['Yellowing'] = t
                except ValueError:
                    pass

        # 1st Crack Parsing
        if "1st Crack" in line:
            # Format: 1st Crack,Start,,,End,,,,,
            # Next line: ,Index,Time,,Index,Time,,,,
            # Next line: ,960,8:00,,-,-,,,,
            # Data is 2 lines below the title line
            if i + 2 < len(lines):
                data_line = lines[i+2]
                parts = data_line.split(',')
                # Time is usually at index 2 for the Start block
                try:
                     t = parse_time_to_seconds(parts[2])
                     if t is not None:
                         milestones['1st Crack'] = t
                except IndexError:
                    pass

    if timeline_index == -1:
        raise ValueError("Could not find 'Timeline' header in the CSV file.")

    # --- Parse Timeline Data ---
    # We pass the remaining content to pandas
    # Join lines from timeline_index
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

    # Numeric conversion
    cols_to_numeric = ['IBTS Temp', 'IBTS ROR', 'Bean Probe Temp', 'Bean Probe ROR']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df, milestones

def parse_profile_csv(file):
    """
    Parses the Profile CSV file.
    """
    # Handle file reading similar to above if needed, but pd.read_csv handles most
    try:
        df = pd.read_csv(file)
    except:
        # If it's a StringIO passed from tests or Streamlit
        file.seek(0)
        df = pd.read_csv(file)

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
    df = df.sort_values(by=time_col).copy()

    # Calculate gradient over window
    # We use diff with window size, assuming approx 1 row per second
    # If 1 row = 1 second, then window_seconds = number of rows
    # We should strictly verify time diffs, but for plotting this is usually sufficient.

    df['Calc_RoR'] = df[temp_col].diff(periods=window_seconds) / df[time_col].diff(periods=window_seconds) * 60

    return df

def smooth_data(series, window=30):
    """
    Smooths data using a rolling mean.
    """
    return series.rolling(window=window, min_periods=1, center=True).mean()

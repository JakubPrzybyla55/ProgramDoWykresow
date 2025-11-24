import pytest
import pandas as pd
from utils import parse_time_to_seconds, calculate_ror

# --- Testy dla parse_time_to_seconds ---

def test_parse_time_mm_ss():
    assert parse_time_to_seconds("10:00") == 600.0
    assert parse_time_to_seconds("0:30") == 30.0

def test_parse_time_hh_mm_ss():
    assert parse_time_to_seconds("1:00:00") == 3600.0

def test_parse_time_seconds_only():
    assert parse_time_to_seconds("120") == 120.0

def test_parse_time_invalid():
    assert parse_time_to_seconds("invalid") is None
    assert parse_time_to_seconds(None) is None
    assert parse_time_to_seconds("-") is None

# --- Testy dla calculate_ror ---

def test_calculate_ror_basic():
    # Przygotowanie prostych danych: 3 punkty co 60 sekund, wzrost o 10 stopni
    # RoR = (10 stopni / 60s) * 60s = 10 stopni/min
    data = {
        'Time_Seconds': [0, 60, 120],
        'IBTS Temp': [100, 110, 120]
    }
    df = pd.DataFrame(data)

    # window_seconds=60 (powinno wziąć różnicę 1 wiersza bo diff=60)
    result = calculate_ror(df, temp_col='IBTS Temp', time_col='Time_Seconds', window_seconds=60)

    assert 'Calc_RoR' in result.columns
    # Pierwszy wiersz ma NaN (bo shift)
    assert pd.isna(result.iloc[0]['Calc_RoR'])
    # Kolejne powinny mieć 10.0
    assert result.iloc[1]['Calc_RoR'] == 10.0
    assert result.iloc[2]['Calc_RoR'] == 10.0

def test_calculate_ror_empty():
    df = pd.DataFrame()
    result = calculate_ror(df)
    assert result.empty

def test_calculate_ror_missing_cols():
    df = pd.DataFrame({'A': [1, 2, 3]})
    result = calculate_ror(df)
    assert 'Calc_RoR' not in result.columns

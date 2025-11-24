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
    # Now logic: Point to point.
    data = {
        'Time_Seconds': [0, 60, 120],
        'IBTS Temp': [100, 110, 120]
    }
    df = pd.DataFrame(data)

    # Removed window_seconds
    result = calculate_ror(df, temp_col='IBTS Temp', time_col='Time_Seconds')

    assert 'Calc_RoR' in result.columns
    # Pierwszy wiersz ma NaN (bo shift)
    assert pd.isna(result.iloc[0]['Calc_RoR'])
    # Kolejne powinny mieć 10.0
    assert result.iloc[1]['Calc_RoR'] == 10.0
    assert result.iloc[2]['Calc_RoR'] == 10.0

def test_calculate_ror_irregular():
    # Test irregular intervals
    # 0->2s (dt=2), T: 100->102 (dT=2). RoR = 2/2*60 = 60
    # 2->5s (dt=3), T: 102->108 (dT=6). RoR = 6/3*60 = 120
    data = {
        'Time_Seconds': [0, 2, 5],
        'IBTS Temp': [100, 102, 108]
    }
    df = pd.DataFrame(data)
    result = calculate_ror(df, temp_col='IBTS Temp', time_col='Time_Seconds')

    assert result.iloc[1]['Calc_RoR'] == 60.0
    assert result.iloc[2]['Calc_RoR'] == 120.0

def test_calculate_ror_empty():
    df = pd.DataFrame()
    result = calculate_ror(df)
    assert result.empty

def test_calculate_ror_missing_cols():
    df = pd.DataFrame({'A': [1, 2, 3]})
    result = calculate_ror(df)
    assert 'Calc_RoR' not in result.columns

from utils import calculate_thermal_dose

# --- Testy dla calculate_thermal_dose ---

def test_calculate_thermal_dose_basic():
    # Dane: T = 100 (Waga = 1), dt = 10s
    # T_base = 100
    # Start = 0
    # Waga = 2^((100-100)/10) = 2^0 = 1
    # Dawka = 1 * 10 = 10 (na krok)

    data = {
        'Time_Seconds': [0, 10, 20],
        'IBTS Temp': [100, 100, 100]
    }
    df = pd.DataFrame(data)

    result = calculate_thermal_dose(df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=100, start_time_threshold=0)

    col = 'Thermal_Dose'
    assert col in result.columns

    # t=0: Dawka=0 (start)
    # t=10: dt=10, AvgTemp=100, W=1, Inc=10 -> Sum=10
    # t=20: dt=10, AvgTemp=100, W=1, Inc=10 -> Sum=20

    # Note: Implementation uses cumsum. First point (after filter) gets 0 accumulation if delta_t is 0 (first point usually delta_t=NaN or 0 depending on implementation)
    # My implementation:
    # df_calc['delta_t'] = df_calc[time_col].diff().fillna(0)  -> First point delta_t=0
    # So first point Dose=0.
    # Second point delta_t=10. Dose = 0 + 1*10 = 10.

    assert result.iloc[0][col] == 0.0
    assert result.iloc[1][col] == 10.0
    assert result.iloc[2][col] == 20.0

def test_calculate_thermal_dose_temp_increase():
    # T rośnie: 100 -> 110
    # T_base = 100
    # t: 0 -> 10
    # T_avg (0-10s) = (100+110)/2 = 105
    # Waga = 2^((105-100)/10) = 2^0.5 = 1.414...
    # Dose = 1.414 * 10 = 14.14

    data = {
        'Time_Seconds': [0, 10],
        'IBTS Temp': [100, 110]
    }
    df = pd.DataFrame(data)
    result = calculate_thermal_dose(df, t_base=100)

    dose_1 = result.iloc[1]['Thermal_Dose']
    expected = (2**0.5) * 10
    assert abs(dose_1 - expected) < 0.1

def test_calculate_thermal_dose_threshold():
    # Dane: 0s, 2s, 10s, 20s
    # Threshold = 5s
    # Punkty brane pod uwagę: 10s, 20s.
    # 0s i 2s odrzucone (Dose=0)
    # Punkt 10s: Pierwszy w filtrze. delta_t=0 (bo diff z niczym wewnątrz grupy). Dose=0.
    # Punkt 20s: delta_t=10. Temp np 100. W=1. Dose = 10.

    data = {
        'Time_Seconds': [0, 2, 10, 20],
        'IBTS Temp': [100, 100, 100, 100]
    }
    df = pd.DataFrame(data)
    result = calculate_thermal_dose(df, start_time_threshold=5)

    assert result.iloc[0]['Thermal_Dose'] == 0.0
    assert result.iloc[1]['Thermal_Dose'] == 0.0
    assert result.iloc[2]['Thermal_Dose'] == 0.0 # Start akumulacji
    assert result.iloc[3]['Thermal_Dose'] == 10.0

def test_calculate_thermal_dose_probe():
    data = {
        'Time_Seconds': [0, 10],
        'Bean Probe Temp': [100, 100]
    }
    df = pd.DataFrame(data)
    result = calculate_thermal_dose(df, temp_col='Bean Probe Temp')

    assert 'Thermal_Dose_Probe' in result.columns
    assert result.iloc[1]['Thermal_Dose_Probe'] == 10.0

import pytest
import pandas as pd
from utils import parsuj_czas_do_sekund, oblicz_ror, oblicz_dawke_termiczna, parsuj_csv_profilu, oblicz_ror_sg

# --- Testy dla parsuj_czas_do_sekund ---

def test_parsuj_czas_mm_ss():
    assert parsuj_czas_do_sekund("10:00") == 600.0
    assert parsuj_czas_do_sekund("0:30") == 30.0

def test_parsuj_czas_hh_mm_ss():
    assert parsuj_czas_do_sekund("1:00:00") == 3600.0

def test_parsuj_czas_sekundy_tylko():
    assert parsuj_czas_do_sekund("120") == 120.0

def test_parsuj_czas_nieprawidlowy():
    assert parsuj_czas_do_sekund("invalid") is None
    assert parsuj_czas_do_sekund(None) is None
    assert parsuj_czas_do_sekund("-") is None

# --- Testy dla oblicz_ror ---

def test_oblicz_ror_podstawowy():
    data = {
        'Time_Seconds': [0, 60, 120],
        'IBTS Temp': [100, 110, 120]
    }
    df = pd.DataFrame(data)
    result = oblicz_ror(df, temp_col='IBTS Temp', time_col='Time_Seconds')
    assert 'Calc_RoR' in result.columns
    assert pd.isna(result.iloc[0]['Calc_RoR'])
    assert result.iloc[1]['Calc_RoR'] == 10.0
    assert result.iloc[2]['Calc_RoR'] == 10.0

def test_oblicz_ror_nieregularny():
    data = {
        'Time_Seconds': [0, 2, 5],
        'IBTS Temp': [100, 102, 108]
    }
    df = pd.DataFrame(data)
    result = oblicz_ror(df, temp_col='IBTS Temp', time_col='Time_Seconds')
    assert result.iloc[1]['Calc_RoR'] == 60.0
    assert result.iloc[2]['Calc_RoR'] == 120.0

def test_oblicz_ror_pusty():
    df = pd.DataFrame()
    result = oblicz_ror(df)
    assert result.empty

def test_oblicz_ror_brak_kolumn():
    df = pd.DataFrame({'A': [1, 2, 3]})
    result = oblicz_ror(df)
    assert 'Calc_RoR' not in result.columns

# --- Testy dla oblicz_dawke_termiczna ---

def test_oblicz_dawke_termiczna_podstawowy():
    data = {
        'Time_Seconds': [0, 10, 20],
        'IBTS Temp': [100, 100, 100]
    }
    df = pd.DataFrame(data)
    result = oblicz_dawke_termiczna(df, temp_col='IBTS Temp', time_col='Time_Seconds', t_base=100, start_time_threshold=0)
    col = 'Thermal_Dose'
    assert col in result.columns
    assert result.iloc[0][col] == 0.0
    assert result.iloc[1][col] == 10.0
    assert result.iloc[2][col] == 20.0

def test_oblicz_dawke_termiczna_wzrost_temperatury():
    data = {
        'Time_Seconds': [0, 10],
        'IBTS Temp': [100, 110]
    }
    df = pd.DataFrame(data)
    result = oblicz_dawke_termiczna(df, t_base=100)
    dose_1 = result.iloc[1]['Thermal_Dose']
    expected = (2**0.5) * 10
    assert abs(dose_1 - expected) < 0.1

def test_oblicz_dawke_termiczna_prog_czasowy():
    data = {
        'Time_Seconds': [0, 2, 10, 20],
        'IBTS Temp': [100, 100, 100, 100]
    }
    df = pd.DataFrame(data)
    result = oblicz_dawke_termiczna(df, start_time_threshold=5)
    assert result.iloc[0]['Thermal_Dose'] == 0.0
    assert result.iloc[1]['Thermal_Dose'] == 0.0
    assert result.iloc[2]['Thermal_Dose'] == 0.0
    assert result.iloc[3]['Thermal_Dose'] == 10.0

def test_oblicz_dawke_termiczna_sonda():
    data = {
        'Time_Seconds': [0, 10],
        'Bean Probe Temp': [100, 100]
    }
    df = pd.DataFrame(data)
    result = oblicz_dawke_termiczna(df, temp_col='Bean Probe Temp')
    assert 'Thermal_Dose_Probe' in result.columns
    assert result.iloc[1]['Thermal_Dose_Probe'] == 10.0

# --- Nowe testy ---

def test_parsuj_csv_profilu_poprawny(tmp_path):
    """Testuje parsowanie poprawnego pliku CSV profilu."""
    p = tmp_path / "plan.csv"
    p.write_text("Faza,Czas,Temperatura\nYellowing,5:00,160.0")
    df = parsuj_csv_profilu(str(p))
    assert not df.empty
    assert "Time_Seconds" in df.columns
    assert df.iloc[0]["Time_Seconds"] == 300.0

def test_parsuj_csv_profilu_brak_kolumny_czasu(tmp_path):
    """Testuje obsługę błędu, gdy brakuje kolumny Czas/Time."""
    p = tmp_path / "plan.csv"
    p.write_text("Faza,Temperatura\nYellowing,160.0")
    with pytest.raises(ValueError, match="musi zawierać kolumnę 'Czas' lub 'Time'"):
        parsuj_csv_profilu(str(p))

def test_oblicz_ror_sg_dziala_bez_bledow():
    """Testuje, czy obliczanie RoR metodą SG nie zwraca błędów."""
    df = pd.DataFrame({
        'Time_Seconds': range(0, 30),
        'IBTS Temp': [100 + i*2 for i in range(30)]
    })
    try:
        from utils import SCIPY_AVAILABLE
        if SCIPY_AVAILABLE:
            df_res = oblicz_ror_sg(df, window_length=15, polyorder=2)
            assert 'Calc_RoR_SG' in df_res.columns
            assert not df_res['Calc_RoR_SG'].isnull().all()
    except ImportError:
        pytest.skip("scipy not available, skipping SG test")

def test_dose_calculation_integration():
    # Create a dummy dataframe representing a roast
    # Time from 0 to 10 seconds, Temp increasing
    data = {
        'Time_Seconds': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'IBTS Temp': [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150]
    }
    df = pd.DataFrame(data)

    # Calculate dose with start time 0 and base 100
    df_res = oblicz_dawke_termiczna(df, t_base=100, start_time_threshold=0)

    assert 'Thermal_Dose' in df_res.columns
    # Check that dose is increasing
    assert df_res['Thermal_Dose'].iloc[-1] > df_res['Thermal_Dose'].iloc[0]
    assert df_res['Thermal_Dose'].iloc[0] == 0.0

    # Calculate with start time threshold = 5
    df_res_th = oblicz_dawke_termiczna(df, t_base=100, start_time_threshold=5)

    # Indices 0-4 (Time 0-4) should be 0
    assert df_res_th.loc[0, 'Thermal_Dose'] == 0.0
    assert df_res_th.loc[4, 'Thermal_Dose'] == 0.0

    # Index 5 (Time 5) starts accumulation
    assert df_res_th.loc[5, 'Thermal_Dose'] == 0.0
    assert df_res_th.loc[6, 'Thermal_Dose'] > 0.0

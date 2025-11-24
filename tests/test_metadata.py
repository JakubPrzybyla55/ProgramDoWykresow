import os
import json
import pytest
import shutil
import pandas as pd
import numpy as np
from utils import load_metadata, save_metadata, get_agtron, set_agtron, parse_roasttime_csv, calculate_thermal_dose

TEST_PROFILE_PATH = 'data/TestProfile'
TEST_META_FILE = os.path.join(TEST_PROFILE_PATH, 'metadata.json')

@pytest.fixture
def setup_test_env():
    # Setup
    if not os.path.exists(TEST_PROFILE_PATH):
        os.makedirs(TEST_PROFILE_PATH)

    yield

    # Teardown
    if os.path.exists(TEST_PROFILE_PATH):
        shutil.rmtree(TEST_PROFILE_PATH)

def test_metadata_load_save(setup_test_env):
    # Test empty load
    data = load_metadata(TEST_PROFILE_PATH)
    assert data == {}

    # Test save
    sample_data = {"agtron": {"file1.csv": 55.5}}
    save_metadata(TEST_PROFILE_PATH, sample_data)

    assert os.path.exists(TEST_META_FILE)

    # Test load again
    loaded_data = load_metadata(TEST_PROFILE_PATH)
    assert loaded_data == sample_data

def test_get_set_agtron(setup_test_env):
    filename = "roast1.csv"
    val = 60.1

    # Test set
    set_agtron(TEST_PROFILE_PATH, filename, val)

    # Verify file content manually
    with open(TEST_META_FILE, 'r') as f:
        content = json.load(f)
    assert content['agtron'][filename] == val

    # Test get
    retrieved = get_agtron(TEST_PROFILE_PATH, filename)
    assert retrieved == val

    # Test get non-existent
    assert get_agtron(TEST_PROFILE_PATH, "nonexistent.csv") is None

def test_metadata_update(setup_test_env):
    # Setup initial state
    set_agtron(TEST_PROFILE_PATH, "f1.csv", 10.0)

    # Update different file
    set_agtron(TEST_PROFILE_PATH, "f2.csv", 20.0)

    data = load_metadata(TEST_PROFILE_PATH)
    assert data['agtron']['f1.csv'] == 10.0
    assert data['agtron']['f2.csv'] == 20.0

    # Update existing
    set_agtron(TEST_PROFILE_PATH, "f1.csv", 11.1)
    data = load_metadata(TEST_PROFILE_PATH)
    assert data['agtron']['f1.csv'] == 11.1

def test_dose_calculation_integration():
    # Create a dummy dataframe representing a roast
    # Time from 0 to 10 seconds, Temp increasing
    data = {
        'Time_Seconds': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'IBTS Temp': [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150]
    }
    df = pd.DataFrame(data)

    # Calculate dose with start time 0 and base 100
    df_res = calculate_thermal_dose(df, t_base=100, start_time_threshold=0)

    assert 'Thermal_Dose' in df_res.columns
    # Check that dose is increasing
    assert df_res['Thermal_Dose'].iloc[-1] > df_res['Thermal_Dose'].iloc[0]
    assert df_res['Thermal_Dose'].iloc[0] == 0.0

    # Calculate with start time threshold = 5
    df_res_th = calculate_thermal_dose(df, t_base=100, start_time_threshold=5)

    # Indices 0-4 (Time 0-4) should be 0
    assert df_res_th.loc[0, 'Thermal_Dose'] == 0.0
    assert df_res_th.loc[4, 'Thermal_Dose'] == 0.0

    # Index 5 (Time 5) starts accumulation
    assert df_res_th.loc[5, 'Thermal_Dose'] == 0.0
    assert df_res_th.loc[6, 'Thermal_Dose'] > 0.0

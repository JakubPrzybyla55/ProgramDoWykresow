import os
import json
import pytest
import shutil
import pandas as pd
import numpy as np
from utils import wczytaj_metadane, zapisz_metadane, pobierz_agtron, ustaw_agtron, oblicz_dawke_termiczna

@pytest.fixture
def test_profile_path(tmp_path):
    """Tworzy tymczasowy katalog profilu dla testów."""
    profile_dir = tmp_path / "TestProfile"
    profile_dir.mkdir()
    return profile_dir

def test_wczytaj_zapisz_metadane(test_profile_path):
    # Test wczytania z pustego
    data = wczytaj_metadane(str(test_profile_path))
    assert data == {}

    # Test zapisu
    sample_data = {"agtron": {"file1.csv": 55.5}}
    zapisz_metadane(str(test_profile_path), sample_data)

    meta_file = test_profile_path / "metadata.json"
    assert meta_file.exists()

    # Test ponownego wczytania
    loaded_data = wczytaj_metadane(str(test_profile_path))
    assert loaded_data == sample_data

def test_pobierz_ustaw_agtron(test_profile_path):
    filename = "roast1.csv"
    val = 60.1
    meta_file = test_profile_path / "metadata.json"

    # Test ustawienia
    ustaw_agtron(str(test_profile_path), filename, val)

    # Ręczna weryfikacja pliku
    with open(meta_file, 'r') as f:
        content = json.load(f)
    assert content['agtron'][filename] == val

    # Test pobrania
    retrieved = pobierz_agtron(str(test_profile_path), filename)
    assert retrieved == val

    # Test pobrania nieistniejącego
    assert pobierz_agtron(str(test_profile_path), "nonexistent.csv") is None

def test_aktualizacja_metadanych(test_profile_path):
    # Ustawienie stanu początkowego
    ustaw_agtron(str(test_profile_path), "f1.csv", 10.0)

    # Aktualizacja innym plikiem
    ustaw_agtron(str(test_profile_path), "f2.csv", 20.0)

    data = wczytaj_metadane(str(test_profile_path))
    assert data['agtron']['f1.csv'] == 10.0
    assert data['agtron']['f2.csv'] == 20.0

    # Aktualizacja istniejącego
    ustaw_agtron(str(test_profile_path), "f1.csv", 11.1)
    data = wczytaj_metadane(str(test_profile_path))
    assert data['agtron']['f1.csv'] == 11.1

import pytest
import os
import subprocess
import time
from playwright.sync_api import Page, expect

# Fixture do uruchamiania Streamlit w tle
@pytest.fixture(scope="module")
def streamlit_app():
    # Sprawdź czy już coś nie działa na 8501
    # Uruchom app.py
    # Zwróć base_url

    # Zakładamy, że jesteśmy w root repo
    cmd = ["streamlit", "run", "app.py", "--server.port=8501", "--server.headless=true"]
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Daj czas na start
    time.sleep(5)

    yield "http://localhost:8501"

    # Cleanup
    process.terminate()
    process.wait()

def test_app_loads(page: Page, streamlit_app):
    page.goto(streamlit_app)
    expect(page).to_have_title("Analizator Wypału Kawy")

def test_sidebar_exists(page: Page, streamlit_app):
    page.goto(streamlit_app)
    # Streamlit sidebar selector
    expect(page.get_by_test_id("stSidebar")).to_be_visible()


import os
from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Streamlit is running on port 8501
    page.goto("http://localhost:8501")

    # Wait for title
    expect(page).to_have_title("Analizator Wypału Kawy")

    # Select a profile (it usually defaults to first one, but let's ensure)
    # We want "CostaRica_Anearobic" or similar if available.
    # It seems the sidebar has a selectbox.

    # Wait for the page to load (sidebar elements)
    page.wait_for_selector("text=Wybierz Profil Kawy")

    # Let's scroll down to see the new chart and settings
    # The new chart should have title "Skumulowana Dawka Termiczna"

    # Check sidebar for new settings
    thermal_dose_expander = page.locator("text=Ustawienia Dawki Termicznej")
    expect(thermal_dose_expander).to_be_visible()

    # Click the expander to reveal the settings
    thermal_dose_expander.click()
    page.wait_for_timeout(500) # wait for animation

    expect(page.locator("text=Temperatura Bazowa (°C)")).to_be_visible()
    expect(page.locator("text=Start Obliczeń (sek)")).to_be_visible()

    # Scroll to the bottom to see the new chart
    # We will only verify the title and the presence of the sidebar
    expect(page).to_have_title("Analizator Wypału Kawy")
    expect(page.locator("text=Wybierz Profil Kawy")).to_be_visible()

    # Take screenshot
    page.screenshot(path="verification/verification.png", full_page=True)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)


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
    # We can use locator for the title of the new chart
    dose_chart_title = page.locator("text=Skumulowana Dawka Termiczna")

    # Explicitly wait for the chart to be visible before scrolling
    expect(dose_chart_title).to_be_visible()
    dose_chart_title.scroll_into_view_if_needed()

    # Wait a bit for plotly to render
    page.wait_for_timeout(3000)

    # Take screenshot
    page.screenshot(path="verification/verification.png", full_page=True)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

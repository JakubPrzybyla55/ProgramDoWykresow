
import os
from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Streamlit is running on port 8501
    page.goto("http://localhost:8501")

    # Wait for title
    expect(page).to_have_title("Analizator Wypału Kawy")

    # Wait for sidebar
    page.wait_for_selector("text=Wybierz Profil Kawy")

    # Check sidebar for new settings
    expect(page.locator("text=Ustawienia Dawki Termicznej")).to_be_visible()

    # Wait for the chart to appear (it might take some time to process data)
    # We look for the unique title of the new chart
    try:
        page.wait_for_selector("text=Skumulowana Dawka Termiczna", timeout=10000)
    except:
        print("Timeout waiting for chart title")

    # Scroll to bottom
    page.keyboard.press("End")
    page.wait_for_timeout(2000)

    # Take screenshot
    page.screenshot(path="verification/verification.png", full_page=True)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)


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

    # Check if we have loaded a profile and roast
    # It might take a moment for the main content to load
    page.wait_for_timeout(2000)

    # Take a screenshot to debug what is visible
    page.screenshot(path="verification/debug_screenshot.png", full_page=True)

    # Check sidebar for new settings
    if page.locator("text=Ustawienia Dawki Termicznej").is_visible():
        print("Settings found")
    else:
        print("Settings NOT found")

    # Try to find the chart title
    if page.locator("text=Skumulowana Dawka Termiczna").is_visible():
         print("Chart title found")
    else:
         print("Chart title NOT found")
         # Print all h4/h3 text
         for h in page.locator("h3").all_inner_texts():
             print(f"H3: {h}")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

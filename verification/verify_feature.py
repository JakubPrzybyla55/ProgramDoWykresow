from playwright.sync_api import Page, expect, sync_playwright

def verify_charts(page: Page):
    # 1. Open App
    page.goto("http://localhost:8501")

    # 2. Select Profile
    # The sidebar has a selectbox for profile. Streamlit selectboxes are tricky.
    # Usually label is "Wybierz Profil".
    # Wait for the app to load
    page.wait_for_timeout(3000)

    # Select "CostaRica_Anearobic" if not already selected.
    # It seems the app defaults to empty or first one.
    # Let's try to find the selectbox.
    # We might need to select "Porównanie Wypałów (dla Planu)" tab first.

    tabs = page.get_by_role("tab", name="Porównanie Wypałów (dla Planu)")
    tabs.click()

    page.wait_for_timeout(2000)

    # Check if we need to select profile.
    # Look for "Brak plików wypałów do analizy w tym profilu."
    if page.get_by_text("Brak plików wypałów do analizy w tym profilu.").is_visible():
        print("Selecting profile...")
        # Assume sidebar is open.
        # Click the selectbox.
        # Streamlit selectbox is often a combobox or similar.
        # Find label "Wybierz Profil"
        # It might be in the sidebar.
        page.get_by_label("Wybierz Profil").click()
        page.get_by_text("CostaRica_Anearobic").click()
        page.wait_for_timeout(3000)

    # 3. Verify Charts
    # Look for titles
    expect(page.get_by_text("Dawka Termiczna (Model 1 - Oryginalny)")).to_be_visible()
    expect(page.get_by_text("Dawka Termiczna (Model 2 - Arrhenius)")).to_be_visible()

    # 4. Screenshot
    page.screenshot(path="verification/verification.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_charts(page)
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification/error.png")
            raise e
        finally:
            browser.close()

import re
from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Go to the application
    page.goto("http://127.0.0.1:5001/")

    # Use a unique username for each run
    import time
    unique_username = f"playwright_user_{int(time.time())}"

    # Register a new user
    page.get_by_placeholder("Username").nth(1).fill(unique_username)
    page.get_by_placeholder("Password").nth(1).fill("password123")
    page.get_by_role("button", name="Register").click()

    # Wait for registration success message
    expect(page.locator("#auth-message")).to_have_text("User created successfully")

    # Login with the new user
    page.get_by_placeholder("Username").first.fill(unique_username)
    page.get_by_placeholder("Password").first.fill("password123")
    page.get_by_role("button", name="Login").click()

    # Wait for the test container to be visible
    expect(page.locator("#test-container")).to_be_visible()

    # Start a verbal test
    page.get_by_role("combobox").select_option("verbal")
    page.get_by_role("button", name="Start Test").click()

    # Wait for the test area to be visible and check for a question
    expect(page.locator("#test-area")).to_be_visible()
    expect(page.locator("#question-text")).to_contain_text("This is verbal question")

    # Take a screenshot of the test page
    page.screenshot(path="jules-scratch/verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

print("Playwright script finished and screenshot taken.")

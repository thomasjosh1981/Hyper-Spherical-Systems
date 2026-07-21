import os
from playwright.sync_api import sync_playwright

html_path = "file:///i:/workspace/hyper_spherical/docs/brochure.html"
pdf_path = r"i:\workspace\hyper_spherical\docs\Hyper_Spherical_Brochure.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    try:
        page = browser.new_page()
        page.goto(html_path, wait_until="networkidle")
        page.pdf(path=pdf_path, format="Letter", print_background=True, prefer_css_page_size=True)
        print(f"Successfully generated {pdf_path}")
    finally:
        browser.close()

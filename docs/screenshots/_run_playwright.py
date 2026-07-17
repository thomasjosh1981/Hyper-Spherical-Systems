"""Open the local HTML viewer, screenshot it, and extract panel text."""
import sys
from playwright.sync_api import sync_playwright

URL = "file:///C:/Users/twist/workspace/project_tesseract/docs/screenshots/viewer.html"
OUT = r"C:\Users\twist\workspace\project_tesseract\docs\screenshots\full_page.png"

errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    try:
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        # Capture console errors / pageerrors
        page.on("console", lambda msg: errors.append(f"[console.{msg.type}] {msg.text}")
                if msg.type in ("error", "warning") else None)
        page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))

        page.goto(URL, wait_until="load")

        # Full-page screenshot
        page.screenshot(path=OUT, full_page=True)

        # Body text
        body_text = page.inner_text("body")

        # Each <div class="tab"> section
        tab_texts = page.locator("div.tab").all_inner_texts()

        # For each tab, also get the H2 and <img> info
        tab_info = []
        tab_locator = page.locator("div.tab")
        n_tabs = tab_locator.count()
        for i in range(n_tabs):
            t = tab_locator.nth(i)
            h2 = t.locator("h2").inner_text() if t.locator("h2").count() else ""
            img_count = t.locator("img").count()
            alt = t.locator("img").first.get_attribute("alt") if img_count else None
            src = t.locator("img").first.get_attribute("src") if img_count else None
            src_kind = "base64-png" if (src and src.startswith("data:image/png;base64,")) else (
                "other" if src else None)
            tab_info.append({
                "index": i,
                "h2": h2,
                "img_count": img_count,
                "img_alt": alt,
                "img_src_kind": src_kind,
                "img_src_len": len(src) if src else 0,
                "inner_text": t.inner_text(),
            })

        print("=== SCREENSHOT ===")
        print("Path:", OUT)
        print()
        print("=== BODY TEXT ===")
        print(body_text)
        print()
        print(f"=== TAB PANELS (count={len(tab_texts)}) ===")
        for i, t in enumerate(tab_texts):
            print(f"\n--- tab[{i}] inner_text ---")
            print(t)
        print()
        print("=== TAB INFO (structured) ===")
        for info in tab_info:
            print(info)
        print()
        print("=== ERRORS/WARNINGS ===")
        if not errors:
            print("(none captured)")
        else:
            for e in errors:
                print(e)
    finally:
        browser.close()

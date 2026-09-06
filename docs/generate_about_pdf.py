import os
import markdown
from playwright.sync_api import sync_playwright

md_path = r"i:\workspace\hyper_spherical\docs\ABOUT.md"
html_path = r"i:\workspace\hyper_spherical\docs\ABOUT_temp.html"
pdf_path = r"i:\workspace\hyper_spherical\docs\ABOUT.pdf"

# 1. Read Markdown
with open(md_path, "r", encoding="utf-8") as f:
    md_text = f.read()

# 2. Convert to HTML with extensions
html_body = markdown.markdown(md_text, extensions=['fenced_code', 'tables'])

# 3. Wrap in HTML template with Github Markdown CSS
html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown-dark.min.css">
    <style>
        body {{
            box-sizing: border-box;
            min-width: 200px;
            max-width: 980px;
            margin: 0 auto;
            padding: 45px;
            background-color: #0d1117;
        }}
    </style>
</head>
<body class="markdown-body">
{html_body}
</body>
</html>
"""

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_template)

# 4. Use Playwright to generate PDF
html_uri = f"file:///{html_path.replace(chr(92), '/')}"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    try:
        page = browser.new_page()
        page.goto(html_uri, wait_until="networkidle")
        page.pdf(path=pdf_path, format="Letter", print_background=True, prefer_css_page_size=True, margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"})
        print(f"Successfully generated {pdf_path}")
    finally:
        browser.close()

# Clean up temp html
if os.path.exists(html_path):
    os.remove(html_path)

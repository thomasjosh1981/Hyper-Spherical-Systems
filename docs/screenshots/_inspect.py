import re, sys
with open(r'C:/Users/twist/workspace/project_tesseract/docs/screenshots/viewer.html', 'r', encoding='utf-8') as f:
    html = f.read()
print('Total length:', len(html))
print('data:image/png;base64 occurrences:', html.count('data:image/png;base64'))
print("class='tab' occurrences:", html.count("class='tab'"))
print('class="tab" occurrences:', html.count('class="tab"'))
print('<img tag occurrences:', len(re.findall(r'<img\b', html)))
print('h2 occurrences:', len(re.findall(r'<h2>', html)))
for m in re.finditer(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL):
    print('H2:', repr(m.group(1)))
for i, m in enumerate(re.finditer(r'src="(data:image/png;base64,[A-Za-z0-9+/=]{0,60})', html)):
    print(f'IMG {i} src start:', repr(m.group(1)))

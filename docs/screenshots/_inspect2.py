import re
with open(r'C:/Users/twist/workspace/project_tesseract/docs/screenshots/viewer.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find each <div class="tab">...</div> block
# Use non-greedy DOTALL
blocks = re.findall(r'<div class="tab">(.*?)</div>', html, re.DOTALL)
print('Number of tab blocks found:', len(blocks))
for i, b in enumerate(blocks):
    print(f'\n=== TAB BLOCK {i} (len={len(b)}) ===')
    # Strip the img tag (huge base64) and show the rest
    cleaned = re.sub(r'<img[^>]+>', '<IMG_BASE64...>', b)
    print(cleaned[:2000])

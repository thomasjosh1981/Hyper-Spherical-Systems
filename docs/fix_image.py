from PIL import Image, ImageDraw, ImageFont

def get_dark_patch(img, size):
    # grab a dark patch from the top right corner
    return img.crop((850, 50, 850 + size[0], 50 + size[1]))

def replace_text(img, draw, font, bbox, text, text_pos):
    # bbox = (x1, y1, x2, y2)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    
    # paste dark patch
    patch = get_dark_patch(img, (width, height))
    img.paste(patch, (bbox[0], bbox[1]))
    
    # Draw new text. Some text has multiple lines.
    lines = text.split('\n')
    y_offset = text_pos[1]
    for line in lines:
        draw.text((text_pos[0], y_offset), line, fill=(200, 230, 255), font=font)
        y_offset += 14 # approx line height

def fix_image():
    img = Image.open('hyperspherical_nodes.png')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 12)
    except:
        font = ImageFont.load_default()

    # 1. DYNAMIC ROUTING LAYERS
    replace_text(img, draw, font, (640, 440, 720, 480), "DYNAMIC\nROUTING\nLAYERS", (640, 445))
    
    # 2. MUTATING ROUTING LAYERS (was MSTANTIS)
    replace_text(img, draw, font, (190, 580, 270, 620), "MUTATING\nROUTING\nLAYERS", (190, 585))
    
    # 3. EPISODIC MEMORY BANKS (was EPISNDIC)
    replace_text(img, draw, font, (535, 630, 630, 665), "EPISODIC\nMEMORY\nBANKS", (540, 635))
    
    # 4. HYPER NODES (was NODE TYPE 4A - left)
    replace_text(img, draw, font, (180, 410, 275, 425), "HYPER NODES", (180, 412))
    
    # 5. SUB NODES (was NODE TYPE 4A - right)
    replace_text(img, draw, font, (890, 680, 970, 710), "SUB NODES", (890, 685))
    
    # 6. OUTPUT (PREDICTION/REASONING) (was INPUT (OATA STREAM) - left)
    replace_text(img, draw, font, (20, 510, 95, 550), "OUTPUT\n(PREDICTION/\nREASONING)", (20, 510))
    
    # 7. INPUT (DATA STREAM) (was OUTPUT... - right)
    replace_text(img, draw, font, (915, 515, 995, 555), "INPUT\n(DATA\nSTREAM)", (920, 515))
    
    # 8. OUTPUT (PREDICTION/REASONING) (was INPUT - bottom left)
    replace_text(img, draw, font, (295, 920, 395, 950), "OUTPUT\n(PREDICTION/REASONING)", (300, 920))
    
    # 9. INPUT (DATA STREAM) (was OUTPUT - bottom center)
    replace_text(img, draw, font, (505, 950, 650, 980), "INPUT\n(DATA STREAM)", (510, 955))

    # 10. SEMANTIC EMBED ZONES (was SEMANTIC EMBEDDINGS ZONE)
    replace_text(img, draw, font, (20, 650, 115, 690), "SEMANTIC\nEMBED\nZONES", (20, 650))
    
    # Fix the weird "NOBE TYPEE" at top right (560, 220)
    replace_text(img, draw, font, (560, 215, 620, 250), "DYNAMIC\nROUTING", (560, 220))

    img.save('hyperspherical_nodes.png')

if __name__ == '__main__':
    fix_image()

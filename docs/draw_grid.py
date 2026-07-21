from PIL import Image, ImageDraw, ImageFont
import sys

def draw_grid():
    img = Image.open('hyperspherical_nodes.png')
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    for x in range(0, width, 50):
        color = (255, 0, 0) if x % 100 == 0 else (255, 255, 255)
        draw.line([(x, 0), (x, height)], fill=color, width=1)
        if x % 100 == 0:
            draw.text((x+2, 2), str(x), fill=(255, 0, 0))
            
    for y in range(0, height, 50):
        color = (255, 0, 0) if y % 100 == 0 else (255, 255, 255)
        draw.line([(0, y), (width, y)], fill=color, width=1)
        if y % 100 == 0:
            draw.text((2, y+2), str(y), fill=(255, 0, 0))
            
    img.save('grid.png')

if __name__ == '__main__':
    draw_grid()

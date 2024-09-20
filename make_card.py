from PIL import Image, ImageDraw, ImageFont
from datetime import datetime


def draw_text(draw, text, font_size, center_position, color=(0, 0, 0), bold=False):
    font_path = 'arialbd.ttf' if bold else 'arial.ttf'
    font = ImageFont.truetype(font_path, font_size)
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    position = (center_position[0] - text_width // 2, center_position[1] - text_height // 2)
    draw.text(position, text, fill=color, font=font)


def make_card(name, position, thank_you_text):
    image_path = 'photo_2024-07-15_14-00-51.png'
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    draw_text(draw, 'ПОДЯКА', 68, (585, 115), (106, 157, 246), True)
    draw_text(draw, position, 16, (585, 200))
    draw_text(draw, name, 36, (585, 240), (57, 120, 213), True)
    draw_text(draw, thank_you_text, 19, (585, 300))
    draw_text(draw, f'{datetime.now().strftime("%d.%m.%Y")}', 14, (857, 402))

    return image


if __name__ == '__main__':
    make_card('Дубині Сергію', 'Інженер експерементального виробництва',
              'За включеність в вирішення проблем по АГС')

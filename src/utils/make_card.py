from PIL import Image, ImageDraw, ImageFont
from datetime import datetime


def draw_text(draw, text, font_size, center_position, color=(0, 0, 0), bold=False):
    font_path = 'assets/fonts/ARIALBD.TTF' if bold else 'assets/fonts/ARIAL.TTF'
    font = ImageFont.truetype(font_path, font_size)

    def split_text(text, font, max_width):
        words = text.split()
        lines = []
        current_line = words[0]
        for word in words[1:]:
            test_line = f'{current_line} {word}'
            if draw.textbbox((0, 0), test_line, font=font)[2] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        return lines

    max_width = 600
    lines = split_text(text, font, max_width)

    while len(lines) > 2:
        font_size -= 1
        font = ImageFont.truetype(font_path, font_size)
        lines = split_text(text, font, max_width)

    text_height = sum(draw.textbbox((0, 0), line, font=font)[3] for line in lines)
    y_offset = center_position[1] - text_height // 2

    if len(lines) == 2:
        y_offset -= 10

    for line in lines:
        text_bbox = draw.textbbox((0, 0), line, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        position = (center_position[0] - text_width // 2, y_offset)
        draw.text(position, line, fill=color, font=font)
        y_offset += text_bbox[3]


def make_card(name, position, thank_you_text):
    image_path = 'assets/images/commendation_template.png'
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    draw_text(draw, 'ПОДЯКА', 68, (585, 115), (106, 157, 246), True)
    draw_text(draw, position, 16, (585, 200))
    draw_text(draw, name, 36, (585, 240), (57, 120, 213), True)
    draw_text(draw, thank_you_text, 19, (585, 300))
    draw_text(draw, f'{datetime.now().strftime("%d.%m.%Y")}', 14, (857, 402))

    return image


if __name__ == '__main__':
    make_card('Прізвище Ім\'я', 'Тестова посада',
              'Текст подяки').show()

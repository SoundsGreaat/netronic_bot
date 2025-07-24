import re
import emoji

from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

from config import COMMENDATION_TEMPLATE, FONT_EVOLVENTA, FONT_EVOLVENTA_BOLD, FONT_PACIFICO, FONT_NOTO, FONT_ARIAL, \
    FONT_ARIAL_BOLD, COMMENDATION_TEMPLATE_OLD


def draw_text(draw, text, font_size, center_position, color=(0, 0, 0), bold=False, font='primary'):
    from config import FONT_NOTO

    if font == 'primary':
        font_path = FONT_EVOLVENTA_BOLD if bold else FONT_EVOLVENTA
    elif font == 'secondary':
        font_path = FONT_PACIFICO

    main_font = ImageFont.truetype(font_path, font_size)
    emoji_font = ImageFont.truetype(FONT_NOTO, font_size)

    clean_text = text.replace('\ufe0f', '')

    def split_text_with_emojis(s):
        result = []
        buffer = ''
        is_emoji_buffer = None

        for char in s:
            is_emoji = emoji.is_emoji(char)
            if is_emoji_buffer is None:
                is_emoji_buffer = is_emoji
                buffer = char
            elif is_emoji == is_emoji_buffer:
                buffer += char
            else:
                result.append((buffer, is_emoji_buffer))
                buffer = char
                is_emoji_buffer = is_emoji
        if buffer:
            result.append((buffer, is_emoji_buffer))
        return result

    def split_text_lines(text, font, max_width):
        words = text.split()
        lines = []
        current_line = words[0]
        for word in words[1:]:
            test_line = f'{current_line} {word}'
            width = draw.textbbox((0, 0), test_line, font=font)[2]
            if width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        return lines

    max_width = 1200
    lines = split_text_lines(clean_text, main_font, max_width)
    while len(lines) > 2:
        font_size -= 1
        main_font = ImageFont.truetype(font_path, font_size)
        emoji_font = ImageFont.truetype(FONT_NOTO, font_size)
        lines = split_text_lines(clean_text, main_font, max_width)

    total_height = sum(draw.textbbox((0, 0), line, font=main_font)[3] for line in lines)
    y = center_position[1] - total_height // 2
    if len(lines) == 2:
        y += 5

    for line in lines:
        chunks = split_text_with_emojis(line)
        x = center_position[0]
        total_line_width = sum(draw.textbbox((0, 0), chunk, font=emoji_font if is_emoji else main_font)[2] for chunk, is_emoji in chunks)
        x -= total_line_width // 2

        for chunk, is_emoji in chunks:
            fnt = emoji_font if is_emoji else main_font
            bbox = draw.textbbox((0, 0), chunk, font=fnt)
            draw.text((x, y), chunk, font=fnt, fill=color)
            x += bbox[2] - bbox[0]
        y += bbox[3]


def make_card(name, position, thank_you_text, value_text=None, from_name=None, from_position=None):
    image_path = COMMENDATION_TEMPLATE
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    value_text = re.sub(r'[^a-zA-Zа-яА-ЯёЁіІїЇєЄґҐ ]', '', value_text) if value_text else ''
    draw_text(draw, position, 38, (1000, 380), bold=True)
    draw_text(draw, name, 72, (1000, 515), font='secondary')
    draw_text(draw, value_text, 45, (1000, 730))
    draw_text(draw, thank_you_text, 45, (1000, 830))
    draw_text(draw, f'{datetime.now().strftime("%d.%m.%Y")}', 30, (495, 1120))
    draw_text(draw, from_name, 30, (1496, 1070))
    draw_text(draw, from_position, 30, (1496, 1170))

    return image


def draw_text_old(draw, text, font_size, center_position, color=(0, 0, 0), bold=False):
    font_path = FONT_ARIAL_BOLD if bold else FONT_ARIAL
    font = ImageFont.truetype(font_path, font_size)

    def split_text(text, font, max_width):
        if not text:
            return []
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


def make_card_old(name, position, thank_you_text, header_text='ПОДЯКА'):
    image_path = COMMENDATION_TEMPLATE_OLD
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    draw_text_old(draw, header_text, 68, (585, 115), (106, 157, 246), True)
    draw_text_old(draw, position, 16, (585, 200))
    draw_text_old(draw, name, 36, (585, 240), (57, 120, 213), True)
    draw_text_old(draw, thank_you_text, 19, (585, 300))
    draw_text_old(draw, f'{datetime.now().strftime("%d.%m.%Y")}', 14, (857, 402))

    return image


if __name__ == '__main__':
    make_card_old(
        'Прізвище Ім\'я',
        'ПОСАДА',
        'Текст подяки Текст подяки Текст подяки Текст подяки Текст подяки🥰💘'
    ).show()

    make_card(
        'Прізвище Ім\'я',
        'ПОСАДА',
        'Текст подяки Текст подяки Текст подяки Текст подяки Текст подяки🥰💘',
        '🎯Відповідальність і проактивність',
        'Від Прізвище Ім\'я', 'Від ПОСАДА'
    ).show()

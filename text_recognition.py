"""Recognize and return text from screen areas."""

import string

from PIL import Image
from PIL import ImageGrab
from PIL import ImageOps
import pytesseract


def recognize_text(x, y, width, height, index,
                   image_magnification, binarization_threshold, is_dark_theme,
                   text_type='integers'):
    """Recognize and return text from a specified screen area."""
    if text_type == 'integers':
        config = (
            f'-c tessedit_char_whitelist={string.digits}{string.whitespace},'
            ' --psm 7')
    elif text_type == 'decimal_numbers':
        config = (
            f'-c tessedit_char_whitelist={string.digits}{string.whitespace},.'
            ' --psm 7')
    elif text_type == 'securities_code_column':
        config = (
            f'-c tessedit_char_whitelist={string.digits}ACDFGHJKLMNPRSTUWXY'
            ' --psm 6')

    split_text = []
    while not split_text:
        try:
            image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            image = image.resize((image_magnification * width,
                                  image_magnification * height),
                                 Image.Resampling.LANCZOS)
            image = image.point(lambda p:
                                255 if p > binarization_threshold else 0)
            if is_dark_theme:
                image = ImageOps.invert(image)

            recognized_text = pytesseract.image_to_string(image, config=config)
            if text_type in ('integers', 'decimal_numbers'):
                split_text = list(map(lambda s: float(s.replace(',', '')),
                                      recognized_text.split(' ')))
            elif text_type == 'securities_code_column':
                for item in recognized_text.splitlines():
                    split_text.append(item)
        except ValueError:
            pass

    if index is None:
        return split_text
    return split_text[int(index)]

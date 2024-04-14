from PIL import Image
from PIL import ImageGrab
from PIL import ImageOps
import pytesseract


def recognize_text(section, x, y, width, height, index, text_type='integers'):
    if text_type == 'integers':
        config = r'-c tessedit_char_whitelist=\ ,0123456789 --psm 7'
    elif text_type == 'decimal_numbers':
        config = r'-c tessedit_char_whitelist=\ .,0123456789 --psm 7'
    elif text_type == 'securities_code_column':
        config = ('-c tessedit_char_whitelist=0123456789ACDFGHJKLMNPRSTUWXY '
                  '--psm 6')

    split_string = []
    image_magnification = int(section['image_magnification'])
    binarization_threshold = int(section['binarization_threshold'])
    while not split_string:
        try:
            image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            image = image.resize((image_magnification * width,
                                  image_magnification * height),
                                 Image.Resampling.LANCZOS)
            image = image.point(lambda p:
                                255 if p > binarization_threshold else 0)
            if section.getboolean('is_dark_theme'):
                image = ImageOps.invert(image)

            string = pytesseract.image_to_string(image, config=config)
            if text_type in ('integers', 'decimal_numbers'):
                split_string = list(map(lambda s: float(s.replace(',', '')),
                                        string.split(' ')))
            elif text_type == 'securities_code_column':
                for item in string.splitlines():
                    split_string.append(item)
        except ValueError:
            pass

    if index is None:
        return split_string
    return split_string[int(index)]

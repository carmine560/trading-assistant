def recognize_text(section, x, y, width, height, index, text_type='integers'):
    """Recognize text from an image.

    Args:
        section: dictionary containing configuration parameters
        x: x-coordinate of the top left corner of the image
        y: y-coordinate of the top left corner of the image
        width: width of the image
        height: height of the image
        index: index of the string to return
        text_type: type of text to recognize. Default is 'integers'

    Returns:
        If index is None, returns a list of recognized
        strings. Otherwise, returns the string at the given index.

    Raises:
        ImportError: If the required libraries are not installed
        Exception: If the image cannot be processed"""
    from PIL import Image
    from PIL import ImageGrab
    from PIL import ImageOps
    import pytesseract

    image_magnification = int(section['image_magnification'])
    binarization_threshold = int(section['binarization_threshold'])
    currently_dark_theme = section.getboolean('currently_dark_theme')

    if text_type == 'integers':
        config = '-c tessedit_char_whitelist=\ ,0123456789 --psm 7'
    elif text_type == 'decimal_numbers':
        config = '-c tessedit_char_whitelist=\ .,0123456789 --psm 7'
    elif text_type == 'numeric_column':
        config = '-c tessedit_char_whitelist=0123456789 --psm 6'

    split_string = []
    while not split_string:
        try:
            image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            image = image.resize((image_magnification * width,
                                  image_magnification * height),
                                 Image.LANCZOS)
            image = image.point(lambda p:
                                255 if p > binarization_threshold else 0)
            if currently_dark_theme:
                image = ImageOps.invert(image)

            string = pytesseract.image_to_string(image, config=config)
            if text_type == 'integers' or text_type == 'decimal_numbers':
                split_string = list(map(lambda s: float(s.replace(',', '')),
                                        string.split(' ')))
            elif text_type == 'numeric_column':
                for item in string.splitlines():
                    split_string.append(item)
        except:
            pass

    if index is None:
        return split_string
    else:
        return split_string[int(index)]

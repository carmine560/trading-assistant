import os
import re
import sys

def backup_file(source, backup_root=None, number_of_backups=-1):
    from datetime import datetime
    import shutil

    if os.path.exists(source):
        if not backup_root:
            backup_root = \
                os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                             'backups')

        if number_of_backups:
            if not os.path.isdir(backup_root):
                try:
                    os.makedirs(backup_root)
                except OSError as e:
                    print(e)
                    sys.exit(1)

            backup = os.path.join(
                backup_root,
                os.path.splitext(os.path.basename(source))[0]
                + datetime.fromtimestamp(
                    os.path.getmtime(source)).strftime('-%Y%m%dT%H%M%S')
                + os.path.splitext(source)[1])
            if not os.path.exists(backup):
                try:
                    shutil.copy2(source, backup)
                except Exception as e:
                    print(e)
                    sys.exit(1)

            if number_of_backups > 0:
                backups = os.listdir(backup_root)
                excess = len(backups) - number_of_backups
                if excess > 0:
                    for f in backups[:excess]:
                        try:
                            os.remove(os.path.join(backup_root, f))
                        except OSError as e:
                            print(e)
                            sys.exit(1)
        else:
            if os.path.isdir(backup_root):
                try:
                    shutil.rmtree(backup_root)
                except Exception as e:
                    print(e)
                    sys.exit(1)

def create_shortcut(basename, target_path, arguments, hotkey=None):
    import win32com.client

    shell = win32com.client.Dispatch('WScript.Shell')
    program_group = get_program_group()
    if not os.path.isdir(program_group):
        try:
            os.mkdir(program_group)
        except OSError as e:
            print(e)
            sys.exit(1)

    title = re.sub('[\W_]+', ' ', basename).rstrip().title()
    shortcut = shell.CreateShortCut(os.path.join(program_group,
                                                 title + '.lnk'))
    shortcut.WindowStyle = 7
    shortcut.IconLocation = create_icon(basename)
    shortcut.TargetPath = target_path
    shortcut.Arguments = arguments
    shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(sys.argv[0]))
    if hotkey:
        shortcut.Hotkey = 'CTRL+ALT+' + hotkey

    shortcut.save()

def delete_shortcut(basename):
    icon = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                        basename + '.ico')
    if os.path.exists(icon):
        try:
            os.remove(icon)
        except OSError as e:
            print(e)
            sys.exit(1)

    program_group = get_program_group()
    title = re.sub('[\W_]+', ' ', basename).rstrip().title()
    shortcut = os.path.join(program_group, title + '.lnk')
    if os.path.exists(shortcut):
        try:
            os.remove(shortcut)
        except OSError as e:
            print(e)
            sys.exit(1)
    if os.path.isdir(program_group) and not os.listdir(program_group):
        try:
            os.rmdir(program_group)
        except OSError as e:
            print(e)
            sys.exit(1)

    # FIXME
    taskbar = os.path.expandvars('$APPDATA\\Microsoft\\Internet Explorer\\Quick Launch\\User Pinned\\TaskBar')
    pinned_shortcut = os.path.join(taskbar, title + '.lnk')
    if os.path.exists(pinned_shortcut):
        try:
            os.remove(pinned_shortcut)
        except OSError as e:
            print(e)
            sys.exit(1)

def get_program_group():
    import win32com.client

    shell = win32com.client.Dispatch('WScript.Shell')
    basename = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    title = re.sub('[\W_]+', ' ', basename).rstrip().title()
    program_group = os.path.join(shell.SpecialFolders('Programs'), title)
    return program_group

def create_icon(basename):
    import winreg

    from PIL import Image, ImageDraw, ImageFont

    acronym = ''
    for word in re.split('[\W_]+', basename):
        if len(word):
            acronym = acronym + word[0].upper()

    image_width = image_height = 256
    image = Image.new('RGBA', (image_width, image_height), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
        try:
            is_light_theme, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
        except OSError:
            is_light_theme = True
    if is_light_theme:
        fill = 'black'
    else:
        fill = 'white'

    if len(acronym) == 0:
        return False
    elif len(acronym) == 1:
        font = ImageFont.truetype('consolab.ttf', 401)

        offset_x, offset_y, text_width, text_height = \
            draw.textbbox((0, 0), acronym, font=font)
        draw.text(((image_width - text_width) / 2, -offset_y), acronym,
                  font=font, fill=fill)
    elif len(acronym) == 2:
        font = ImageFont.truetype('consolab.ttf', 180)

        offset_x, offset_y, text_width, text_height = \
            draw.textbbox((0, 0), acronym, font=font)
        draw.text(((image_width - text_width) / 2,
                   (image_height - text_height) / 2 - offset_y), acronym,
                  font=font, fill=fill)
    elif len(acronym) >= 3:
        font = ImageFont.truetype('consolab.ttf', 180)

        upper = acronym[0:2]
        offset_x, offset_y, text_width, text_height = \
            draw.textbbox((0, 0), upper, font=font)
        draw.text(((image_width - text_width) / 2, -offset_y), upper,
                  font=font, fill=fill)

        lower = acronym[2:4]
        offset_x, offset_y, text_width, text_height = \
            draw.textbbox((0, 0), lower, font=font)
        draw.text(((image_width - text_width) / 2,
                   image_height - text_height), lower, font=font,
                  fill=fill)

    icon = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                        basename + '.ico')
    image.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    return icon

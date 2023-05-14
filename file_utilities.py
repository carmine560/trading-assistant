import os
import re
import sys

def archive_encrypt_directory(source, output_directory, fingerprint=''):
    import io
    import tarfile

    import gnupg

    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w:xz') as tar:
        tar.add(source, arcname=os.path.basename(source))

    tar_stream.seek(0)
    gpg = gnupg.GPG()
    if not fingerprint:
        fingerprint = gpg.list_keys()[0]['fingerprint']

    output = os.path.join(output_directory,
                          os.path.basename(source) + '.tar.xz.gpg')
    # TODO
    gpg.encrypt_file(tar_stream, fingerprint, output=output)

def decrypt_extract_file(source, output_directory):
    import io
    import shutil
    import tarfile

    import gnupg

    gpg = gnupg.GPG()
    with open(source, 'rb') as f:
        decrypted_data = gpg.decrypt_file(f)

    tar_stream = io.BytesIO(decrypted_data.data)
    with tarfile.open(fileobj=tar_stream, mode='r:xz') as tar:
        root = os.path.join(output_directory, tar.getmembers()[0].name)
        backup = root + '.bak'

        if os.path.isdir(root):
            if os.path.isdir(backup):
                try:
                    shutil.rmtree(backup)
                except Exception as e:
                    print(e)
                    sys.exit(1)
            elif os.path.isfile(backup):
                print(backup, 'file exists')
                sys.exit(1)

            os.rename(root, backup)
        elif os.path.isfile(root):
            print(root, 'file exists')
            sys.exit(1)

        try:
            tar.extractall(path=output_directory)
        except Exception as e:
            print(e)
            sys.exit(1)

        if os.path.isdir(backup):
            try:
                shutil.rmtree(backup)
            except Exception as e:
                print(e)
                sys.exit(1)

def backup_file(source, backup_directory=None, number_of_backups=-1):
    from datetime import datetime
    import shutil

    if os.path.exists(source):
        if not backup_directory:
            backup_directory = os.path.join(os.path.dirname(source), 'backups')

        if number_of_backups:
            if not os.path.isdir(backup_directory):
                try:
                    os.makedirs(backup_directory)
                except OSError as e:
                    print(e)
                    sys.exit(1)

            backup = os.path.join(
                backup_directory,
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
                pattern = os.path.splitext(os.path.basename(source))[0] \
                    + r'-\d{8}T\d{6}' + os.path.splitext(source)[1]
                backups = [f for f in os.listdir(backup_directory)
                           if re.fullmatch(pattern, f)]
                excess = len(backups) - number_of_backups
                if excess > 0:
                    for f in backups[:excess]:
                        try:
                            os.remove(os.path.join(backup_directory, f))
                        except OSError as e:
                            print(e)
                            sys.exit(1)
        else:
            if os.path.isdir(backup_directory):
                try:
                    shutil.rmtree(backup_directory)
                except Exception as e:
                    print(e)
                    sys.exit(1)

# TODO
def create_icon(basename, icon_directory=None):
    import winreg

    from PIL import Image, ImageDraw, ImageFont

    acronym = ''
    for word in re.split('[\W_]+', basename):
        if word:
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

    if icon_directory:
        icon = os.path.join(icon_directory, basename + '.ico')
    else:
        icon = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                            basename + '.ico')

    image.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    return icon

def create_shortcut(basename, target_path, arguments, program_group_base=None,
                    icon_directory=None, hotkey=None):
    import win32com.client

    shell = win32com.client.Dispatch('WScript.Shell')
    program_group = get_program_group(program_group_base)
    if not os.path.isdir(program_group):
        try:
            os.mkdir(program_group)
        except OSError as e:
            print(e)
            sys.exit(1)

    title = re.sub('[\W_]+', ' ', basename).strip().title()
    shortcut = shell.CreateShortCut(os.path.join(program_group,
                                                 title + '.lnk'))
    shortcut.WindowStyle = 7
    shortcut.IconLocation = create_icon(basename,
                                        icon_directory=icon_directory)
    shortcut.TargetPath = target_path
    shortcut.Arguments = arguments
    shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(sys.argv[0]))
    if hotkey:
        shortcut.Hotkey = 'CTRL+ALT+' + hotkey

    shortcut.save()

def delete_shortcut(basename, program_group_base=None, icon_directory=None):
    if icon_directory:
        icon = os.path.join(icon_directory, basename + '.ico')
    else:
        icon = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                            basename + '.ico')
    if os.path.exists(icon):
        try:
            os.remove(icon)
        except OSError as e:
            print(e)
            sys.exit(1)

    program_group = get_program_group(program_group_base)
    title = re.sub('[\W_]+', ' ', basename).strip().title()
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

def get_program_group(program_group_base=None):
    import win32com.client

    shell = win32com.client.Dispatch('WScript.Shell')
    if not program_group_base:
        basename = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        program_group_base = re.sub('[\W_]+', ' ', basename).strip().title()

    program_group = os.path.join(shell.SpecialFolders('Programs'),
                                 program_group_base)
    return program_group

def writing_file(target_path):
    import time

    if os.path.exists(target_path) \
       and time.time() - os.path.getmtime(target_path) < 1:
        return True
    else:
        return False

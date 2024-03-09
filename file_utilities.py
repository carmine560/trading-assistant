import os
import re
import sys
import time

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
    gpg.encrypt_file(tar_stream, fingerprint, armor=False, output=output)

def backup_file(source, backup_directory=None, number_of_backups=-1,
                should_compare=True):
    from datetime import datetime
    import shutil

    decrypted_source = source
    encrypted_source = source + '.gpg'
    if os.path.exists(encrypted_source):
        source = encrypted_source
        should_compare = False

    if os.path.exists(source):
        if not backup_directory:
            backup_directory = os.path.join(os.path.dirname(source), 'backups')

        if number_of_backups:
            check_directory(backup_directory)
            if source == encrypted_source:
                source_base = os.path.splitext(
                    os.path.basename(decrypted_source))[0]
                source_suffix = os.path.splitext(decrypted_source)[1] + '.gpg'
            else:
                source_base = os.path.splitext(os.path.basename(source))[0]
                source_suffix = os.path.splitext(source)[1]

            backup = os.path.join(
                backup_directory,
                source_base + datetime.fromtimestamp(
                    os.path.getmtime(source)).strftime('-%Y%m%dT%H%M%S')
                + source_suffix)
            regex = (source_base + r'-\d{8}T\d{6}' + source_suffix)
            backups = sorted([f for f in os.listdir(backup_directory)
                              if re.fullmatch(regex, f)])

            if not os.path.exists(backup):
                should_copy = True
                if should_compare and backups:
                    with open(source, 'rb') as f:
                        source_contents = f.read()
                    with open(os.path.join(backup_directory, backups[-1]),
                              'rb') as f:
                        last_backup_contents = f.read()
                    if source_contents == last_backup_contents:
                        should_copy = False
                if should_copy:
                    try:
                        shutil.copy2(source, backup)
                        backups.append(os.path.basename(backup))
                    except Exception as e:
                        print(e)
                        sys.exit(1)

            if number_of_backups > 0:
                excess = len(backups) - number_of_backups
                if excess > 0:
                    for f in backups[:excess]:
                        try:
                            os.remove(os.path.join(backup_directory, f))
                        except OSError as e:
                            print(e)
                            sys.exit(1)

        elif os.path.isdir(backup_directory):
            try:
                shutil.rmtree(backup_directory)
            except Exception as e:
                print(e)
                sys.exit(1)

def create_bash_completion(script_base, options, values, interpreters,
                           completion):
    options_str = ' '.join(options)

    variable_str = '    values="'
    line = ''
    max_line_length = 79
    lines = []
    for value in values:
        if len(variable_str) + len(line) + len(value) + 4 > max_line_length:
            lines.append(line.rstrip(' '))
            line = ''

        line += f"'{value}' "

    lines.append(line.rstrip(' '))
    values_str = f"\n{' ' * len(variable_str)}".join(lines)

    expression_str = ' || '.join(f'$previous == {option}'
                                 for option in options)
    interpreters_str = ' '.join(interpreters)
    completion_str = fr'''_{script_base}()
{{
    local script current previous options values
    script=${{COMP_WORDS[1]}}
    current=${{COMP_WORDS[COMP_CWORD]}}
    previous=${{COMP_WORDS[COMP_CWORD-1]}}
    options="{options_str}"
{variable_str}{values_str}"

    if [[ $script =~ {script_base}\.py ]]; then
        if [[ $current == -* ]]; then
            COMPREPLY=($(compgen -W "$options" -- $current))
            return 0
        fi
        if [[ {expression_str} ]]; then
            COMPREPLY=($(compgen -W "$values" -- $current))
            return 0
        fi
    else
        COMPREPLY=($(compgen -f -- $current))
        return 0
    fi
}}
complete -F _{script_base} {interpreters_str}
'''

    with open(completion, 'w', newline='\n') as f:
        f.write(completion_str)

def check_directory(directory):
    if not os.path.isdir(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            print(e)
            sys.exit(1)

def create_icon(base, icon_directory=None):
    def get_scaled_font(text, font_path, desired_width, desired_height,
                        variation_name=''):
        temp_font_size = 100
        temp_font = ImageFont.truetype(font_path, temp_font_size)
        if variation_name:
            temp_font.set_variation_by_name(variation_name)

        draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        left, top, right, bottom = draw.multiline_textbbox((0, 0), text,
                                                           font=temp_font)
        temp_text_width = right - left
        temp_text_height = bottom - top

        scaling_factor_width = desired_width / temp_text_width
        scaling_factor_height = desired_height / temp_text_height
        scaling_factor = min(scaling_factor_width, scaling_factor_height)
        actual_font_size = int(temp_font_size * scaling_factor)
        actual_font = ImageFont.truetype(font_path, actual_font_size)
        if variation_name:
            actual_font.set_variation_by_name(variation_name)
        return actual_font

    import winreg

    from PIL import Image, ImageDraw, ImageFont

    acronym = ''.join(word[0].upper()
                      for word in re.split(r'[\W_]+', base) if word)
    font_path = 'bahnschrift.ttf'
    variation_name = 'Bold'
    image_width = image_height = 256
    desired_width = desired_height = image_width - 2
    image = Image.new('RGBA', (image_width, image_height), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
        try:
            is_light_theme, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
        except OSError:
            is_light_theme = True

    fill = 'black' if is_light_theme else 'white'

    if not acronym:
        return False
    elif len(acronym) < 3:
        font = get_scaled_font(acronym, font_path, desired_width,
                               desired_height, variation_name=variation_name)
        left, top, right, bottom = draw.textbbox((0, 0), acronym, font=font)
        draw.text(((image_width - (right - left)) / 2 - left,
                   (image_height - (bottom - top)) / 2 - top), acronym,
                  fill=fill, font=font)
    else:
        text = f'{acronym[:2]}\n{acronym[2:4]}'
        font = get_scaled_font(text, font_path, desired_width, desired_height,
                               variation_name=variation_name)
        left, top, right, bottom = draw.multiline_textbbox((0, 0), text,
                                                           font=font)
        draw.multiline_text(((image_width - (right - left)) / 2 - left,
                             (image_height - (bottom - top)) / 2 - top), text,
                            fill=fill, font=font, align='center')

    if icon_directory:
        icon = os.path.join(icon_directory, base + '.ico')
    else:
        icon = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                            base + '.ico')

    image.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    return icon

def create_powershell_completion(script_base, options, values, interpreters,
                                 completion):
    interpreters_regex = f"({'|'.join(interpreters)})"
    interpreters_array = f"@({', '.join(map(repr, interpreters))})"
    options_str = '|'.join(options)

    variable_str = '        $options = @('
    line = ''
    max_line_length = 79
    lines = []
    for value in values:
        if len(variable_str) + len(line) + len(value) + 5 > max_line_length:
            lines.append(line.rstrip(' '))
            line = ''

        line += f"'{value}', "

    lines.append(line.rstrip(', '))
    values_str = f"\n{' ' * len(variable_str)}".join(lines)

    completion_str = fr'''$scriptblock = {{
    param($wordToComplete, $commandAst, $cursorPosition)
    $commandLine = $commandAst.ToString()
    $regex = `
      '{interpreters_regex}(\.exe)?\s+.*{script_base}\.py(\s+.*)?\s+({options_str})'
    if ($commandLine -cmatch $regex) {{
{variable_str}{values_str})
        $options | Where-Object {{ $_ -like "$wordToComplete*" }} |
          ForEach-Object {{
              [System.Management.Automation.CompletionResult]::new(
                  $_, $_, 'ParameterValue', $_)
          }}
    }}
}}
Register-ArgumentCompleter -Native -CommandName {interpreters_array} `
  -ScriptBlock $scriptblock
'''

    with open(completion, 'w') as f:
        f.write(completion_str)

def create_shortcut(base, target_path, arguments, program_group_base=None,
                    icon_directory=None, hotkey=None):
    import win32com.client

    program_group = get_program_group(program_group_base)
    check_directory(program_group)
    shell = win32com.client.Dispatch('WScript.Shell')
    title = re.sub(r'[\W_]+', ' ', base).strip().title()
    shortcut = shell.CreateShortCut(os.path.join(program_group,
                                                 title + '.lnk'))
    shortcut.WindowStyle = 7
    shortcut.IconLocation = create_icon(base,
                                        icon_directory=icon_directory)
    shortcut.TargetPath = target_path
    shortcut.Arguments = arguments
    shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(sys.argv[0]))
    if hotkey:
        shortcut.Hotkey = 'CTRL+ALT+' + hotkey

    shortcut.save()

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
                print(backup, 'file exists.')
                sys.exit(1)

            os.rename(root, backup)
        elif os.path.isfile(root):
            print(root, 'file exists.')
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

def delete_shortcut(base, program_group_base=None, icon_directory=None):
    if icon_directory:
        icon = os.path.join(icon_directory, base + '.ico')
    else:
        icon = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                            base + '.ico')
    if os.path.exists(icon):
        try:
            os.remove(icon)
        except OSError as e:
            print(e)
            sys.exit(1)

    program_group = get_program_group(program_group_base)
    title = re.sub(r'[\W_]+', ' ', base).strip().title()
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

def extract_commands(source, command='command'):
    import ast

    commands = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Compare):
                left = test.left
                if isinstance(left, ast.Name) and left.id == command:
                    comparator = test.comparators[0]
                    if isinstance(comparator, ast.Constant):
                        commands.append(comparator.value)
    return commands

def get_file_description(executable):
    import win32api

    try:
        language, codepage = win32api.GetFileVersionInfo(
            executable, r'\VarFileInfo\Translation')[0]
        string_file_info = (u'\\StringFileInfo\\%04X%04X\\%s'
                            % (language, codepage, 'FileDescription'))
        file_description = win32api.GetFileVersionInfo(executable,
                                                       string_file_info)
    except:
        file_description = False

    return file_description

def get_program_group(program_group_base=None):
    import win32com.client

    shell = win32com.client.Dispatch('WScript.Shell')
    if not program_group_base:
        base = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        program_group_base = re.sub(r'[\W_]+', ' ', base).strip().title()

    program_group = os.path.join(shell.SpecialFolders('Programs'),
                                 program_group_base)
    return program_group

def is_writing(target_path):
    import time

    if (os.path.exists(target_path)
        and time.time() - os.path.getmtime(target_path) < 1):
        return True
    else:
        return False

def move_to_trash(path):
    import subprocess

    try:
        subprocess.run(['trash-put', path], check=True)
        print(f'Moved {path} to trash.')
    except Exception as e:
        print(f'Failed to move {path} to trash: {str(e)}')

def write_chapter(video, current_title, previous_title=None):
    if is_writing(video):
        ffmpeg_metadata = os.path.splitext(video)[0] + '.txt'
        start = int(1000 * (time.time() - os.path.getctime(video)))
        default_duration = 60000
        end = start + default_duration

        if os.path.exists(ffmpeg_metadata):
            with open(ffmpeg_metadata, 'r') as f:
                lines = f.readlines()
            for i in reversed(range(len(lines))):
                if 'END=' in lines[i]:
                    lines[i] = re.sub(r'END=\d+', f'END={start - 1}', lines[i])
                    with open(ffmpeg_metadata, 'w') as f:
                        f.writelines(lines)
                    break

            chapter = f'''
[CHAPTER]
TIMEBASE=1/1000
START={start}
END={end}
title={current_title}
'''
            with open(ffmpeg_metadata, 'a') as f:
                f.write(chapter)
        else:
            chapters = f''';FFMETADATA1

[CHAPTER]
TIMEBASE=1/1000
START=0
END={start - 1}
title={previous_title}

[CHAPTER]
TIMEBASE=1/1000
START={start}
END={end}
title={current_title}
'''
            with open(ffmpeg_metadata, 'w') as f:
                f.write(chapters)

import os
import re
import sys

def archive_encrypt_directory(source, output_directory, fingerprint=''):
    """Encrypt and archive a directory.

    Args:
        source: The path of the directory to be encrypted and archived.
        output_directory: The path of the directory where the encrypted
        and archived file will be saved.
        fingerprint: The fingerprint of the GPG key to be used for
        encryption. If not provided, the first key in the keyring will
        be used.

    Returns:
        None

    Raises:
        None"""
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
    # TODO: reduce file size.
    gpg.encrypt_file(tar_stream, fingerprint, output=output)

def decrypt_extract_file(source, output_directory):
    """Decrypt and extract a file.

    Args:
        source: The path to the encrypted file.
        output_directory: The path to the directory where the decrypted
        file will be extracted.

    Raises:
        Exception: If there is an error in decrypting or extracting the
        file."""
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
    """Backs up a file to a specified directory.

    Args:
        source: The source file to be backed up.
        backup_directory: The directory where the backup file will be
        stored. If not provided, a 'backups' directory will be created
        in the same directory as the source file.
        number_of_backups: The maximum number of backups to keep. If set
        to a negative value, all backups will be kept.

    Raises:
        OSError: If there is an error in deleting or copying the
        file."""
    from datetime import datetime
    import shutil

    if os.path.exists(source):
        if not backup_directory:
            backup_directory = os.path.join(os.path.dirname(source), 'backups')

        if number_of_backups:
            check_directory(backup_directory)
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

def check_directory(directory):
    """Check if a directory exists, and create it if it doesn't.

    Args:
        directory: A string representing the directory path.

    Raises:
        OSError: If the directory cannot be created.
        sys.exit(1): If the directory does not exist and cannot be
        created."""
    if not os.path.isdir(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            print(e)
            sys.exit(1)

def create_icon(basename, icon_directory=None):
    """Creates an icon file from a given basename.

    Args:
        basename (str): The base name of the icon file.
        icon_directory (str, optional): The directory to save the icon
        file. Defaults to None.

    Returns:
        str: The path of the created icon file.

    Raises:
        OSError: If the subkey cannot be opened.
        NotImplementedError: If the animal is silent.

    Dependencies:
        - winreg
        - PIL

    Note:
        The icon file is saved in the following sizes: 16x16, 32x32,
        48x48, and 256x256."""
    def get_scaled_font(text, font_path, desired_width, desired_height,
                        variation_name=''):
        """Returns a scaled font object for the given text, font path,
        desired width and height.

        Args:
            text (str): The text to be written
            font_path (str): The path to the font file
            desired_width (int): The desired width of the text
            desired_height (int): The desired height of the text
            variation_name (str): The variation name of the font
            (optional)

        Returns:
            The scaled font object

        Raises:
            None"""
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
                      for word in re.split('[\W_]+', basename) if word)
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
    elif len(acronym) == 1:
        font = get_scaled_font(acronym, font_path, desired_width,
                               desired_height, variation_name=variation_name)
        left, top, right, bottom = draw.textbbox((0, 0), acronym, font=font)
        draw.text(((image_width - (right - left)) / 2 - left,
                   (image_height - (bottom - top)) / 2 - top), acronym,
                  fill=fill, font=font)
    elif len(acronym) == 2:
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
        icon = os.path.join(icon_directory, basename + '.ico')
    else:
        icon = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                            basename + '.ico')

    image.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    return icon

def create_shortcut(basename, target_path, arguments, program_group_base=None,
                    icon_directory=None, hotkey=None):
    """Creates a shortcut for a given program.

    Args:
        basename: The name of the shortcut
        target_path: The path of the program to be executed
        arguments: The arguments to be passed to the program
        program_group_base: The name of the program group
        icon_directory: The directory containing the icon for the
        shortcut
        hotkey: The hotkey to be used for the shortcut

    Returns:
        None"""
    import win32com.client

    program_group = get_program_group(program_group_base)
    check_directory(program_group)
    shell = win32com.client.Dispatch('WScript.Shell')
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
    """Deletes a shortcut file and its associated icon file.

    Args:
        basename (str): The base name of the shortcut file.
        program_group_base (str, optional): The base name of the program
        group. Defaults to None.
        icon_directory (str, optional): The directory containing the
        icon file. Defaults to None.

    Raises:
        OSError: If there is an error deleting the shortcut or icon
        file.

    Returns:
        None."""
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
    """Get the program group path.

    Args:
        program_group_base: The name of the program group. If not
        provided, it will be derived from the name of the script.

    Returns:
        The path of the program group.

    Raises:
        None."""
    import win32com.client

    shell = win32com.client.Dispatch('WScript.Shell')
    if not program_group_base:
        basename = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        program_group_base = re.sub('[\W_]+', ' ', basename).strip().title()

    program_group = os.path.join(shell.SpecialFolders('Programs'),
                                 program_group_base)
    return program_group

def is_writing(target_path):
    """Check if a file is being written to.

    Args:
        target_path: Path to the file to check

    Returns:
        True if the file exists and was modified within the last second,
        False otherwise."""
    import time

    if os.path.exists(target_path) \
       and time.time() - os.path.getmtime(target_path) < 1:
        return True
    else:
        return False

def extract_commands(source, command='command'):
    """Extracts commands from source code.

    Args:
        source : str
            The source code to extract commands from.
        command : str, optional
            The name of the command to extract. Default is 'command'.

    Returns:
        A list of commands extracted from the source code.

    Raises:
        None."""
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

def create_powershell_completion(script_base, options, values, interpreter,
                                 completion):
    """Creates a PowerShell completion script for a given Python script.

    Args:
        script_base: The base name of the Python script.
        options: A list of valid options for the script.
        values: A list of valid values for the options.
        interpreter: The name of the Python interpreter.
        completion: The path to the completion script to be created.

    Returns:
        None

    Raises:
        None"""
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

    completion_str = f'''$scriptblock = {{
    param($wordToComplete, $commandAst, $cursorPosition)
    $commandLine = $commandAst.ToString()
    $regex = '{interpreter}(\.exe)?\s+.*{script_base}\.py(\s+.*)?\s+({options_str})'
    if ($commandLine -cmatch $regex) {{
{variable_str}{values_str})
        $options | Where-Object {{ $_ -like "$wordToComplete*" }} |
          ForEach-Object {{
              [System.Management.Automation.CompletionResult]::new(
                  $_, $_, 'ParameterValue', $_)
          }}
    }}
}}
Register-ArgumentCompleter -Native -CommandName {interpreter} -ScriptBlock $scriptblock
'''

    with open(completion, 'w') as f:
        f.write(completion_str)

def create_bash_completion(script_base, options, values, interpreter,
                           completion):
    """Create a bash completion script for a given script.

    Args:
        script_base: The base name of the script
        options: A list of options to be completed
        values: A list of values to be completed
        interpreter: The interpreter to use for the completion
        completion: The file path to write the completion script to

    Returns:
        None"""
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
    completion_str = f'''_{script_base}()
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
complete -F _{script_base} {interpreter}
'''

    with open(completion, 'w', newline='\n') as f:
        f.write(completion_str)

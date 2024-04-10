from io import StringIO
import ast
import configparser
import os
import sys
import time

from prompt_toolkit import ANSI
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion
import gnupg

try:
    import pyautogui
    import win32api
    GUI_IMPORT_ERROR = None
except ModuleNotFoundError as import_error:
    GUI_IMPORT_ERROR = import_error

import file_utilities

ANSI_BOLD = '\033[1m'
ANSI_CURRENT = '\033[32m'
ANSI_ERROR = '\033[31m'
ANSI_IDENTIFIER = '\033[36m'
ANSI_RESET = '\033[m'
ANSI_UNDERLINE = '\033[4m'
ANSI_WARNING = '\033[33m'
INDENT = '    '

if sys.platform == 'win32':
    os.system('color')

class CustomWordCompleter(Completer):
    def __init__(self, words, ignore_case=False):
        self.words = words
        self.ignore_case = ignore_case

    def get_completions(self, document, complete_event):
        word_before_cursor = document.current_line_before_cursor.lstrip()
        for word in self.words:
            if self.ignore_case:
                if word.lower().startswith(word_before_cursor.lower()):
                    yield Completion(word, -len(word_before_cursor))
            else:
                if word.startswith(word_before_cursor):
                    yield Completion(word, -len(word_before_cursor))

def check_config_changes(default_config, config_path, excluded_sections=(),
                         user_option_ignored_sections=(),
                         backup_parameters=None):
    def truncate_string(string):
        max_length = 256
        if len(string) > max_length:
            string = string[:max_length] + '...'
        return string

    def display_changes(config, config_path, previous_section, section, option,
                        option_status):
        if section != previous_section[0]:
            print(f'[{ANSI_BOLD}{section}{ANSI_RESET}]')
            previous_section[0] = section

        print(option_status)
        answer = tidy_answer(['default', 'quit'])
        if answer == 'default':
            config.remove_option(section, option)
            write_config(config, config_path)
        elif answer == 'quit':
            return False
        return True

    if backup_parameters:
        file_utilities.backup_file(config_path, **backup_parameters)

    user_config = configparser.ConfigParser()
    read_config(user_config, config_path)

    previous_section = [None]
    for section in default_config.sections():
        if (section not in excluded_sections
            and default_config.options(section)):
            for option in default_config[section]:
                if (user_config.has_option(section, option)
                    and default_config[section][option]
                    != user_config[section][option]):
                    default_value = (
                        truncate_string(default_config[section][option])
                                  if default_config[section][option]
                                  else '(empty)')
                    user_value = (truncate_string(user_config[section][option])
                                  if user_config[section][option]
                                  else '(empty)')

                    option_status = (
                        f'{ANSI_IDENTIFIER}{option}{ANSI_RESET}: '
                        f'{default_value} → '
                        f'{ANSI_CURRENT}{user_value}{ANSI_RESET}')
                    if not display_changes(user_config, config_path,
                                           previous_section, section, option,
                                           option_status):
                        return
            if section not in user_option_ignored_sections:
                for option in user_config[section]:
                    if not default_config.has_option(section, option):
                        default_value = '(not exist)'
                        user_value = (
                            truncate_string(user_config[section][option])
                            if user_config[section][option]
                            else '(empty)')
                        option_status = (
                            f'{ANSI_IDENTIFIER}{option}{ANSI_RESET}: '
                            f'{ANSI_WARNING}{default_value}{ANSI_RESET} → '
                            f'{user_value}')
                        if not display_changes(user_config, config_path,
                                               previous_section, section,
                                               option, option_status):
                            return

def configure_position(level=0, value=''):
    if GUI_IMPORT_ERROR:
        print(GUI_IMPORT_ERROR)
        return False

    value = prompt_for_input(f'coordinates/{ANSI_UNDERLINE}c{ANSI_RESET}lick',
                             level=level, value=value)
    if value and value[0].lower() == 'c':
        previous_key_state = win32api.GetKeyState(0x01)
        coordinates = ''
        print(
            f'{INDENT * level}{ANSI_WARNING}waiting for click...{ANSI_RESET}')
        while True:
            key_state = win32api.GetKeyState(0x01)
            if key_state != previous_key_state:
                if key_state not in [0, 1]:
                    coordinates = ', '.join(map(str, pyautogui.position()))
                    print(f'{INDENT * level}coordinates: {coordinates}')
                    break

            time.sleep(0.001)
        return coordinates

    parts = value.split(',')
    if len(parts) == 2:
        x = parts[0].strip()
        y = parts[1].strip()
        if x.isdigit() and y.isdigit():
            return f'{x}, {y}'

    return configure_position(level=level,
                              value=f'{ANSI_RESET}{ANSI_ERROR}{value}')

def delete_option(config, section, option, config_path,
                  backup_parameters=None):
    if backup_parameters:
        file_utilities.backup_file(config_path, **backup_parameters)

    if config.has_option(section, option):
        config.remove_option(section, option)
        write_config(config, config_path)
        return True

    print(option, 'option does not exist.')
    return False

def evaluate_value(value):
    evaluated_value = None
    try:
        evaluated_value = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        pass
    except (TypeError, MemoryError, RecursionError) as e:
        print(e)
        sys.exit(1)
    return evaluated_value

def get_strict_boolean(config, section, option):
    value = config.get(section, option)
    if value.lower() not in {'true', 'false'}:
        raise ValueError(f'Invalid boolean value for {option} in {section}.')
    return config.getboolean(section, option)

def list_section(config, section):
    options = []
    if config.has_section(section):
        for option in config[section]:
            options.append(option)
        return options

    print(section, 'section does not exist.')
    return False

def modify_dictionary(dictionary, level=0, prompts=None, all_values=None):
    value_prompt = prompts.get('value', 'value')

    for key, value in dictionary.items():
        print(f'{INDENT * level}{ANSI_IDENTIFIER}{key}{ANSI_RESET}: '
              f'{ANSI_CURRENT}{value}{ANSI_RESET}')
        answer = tidy_answer(['modify', 'empty', 'quit'], level=level)
        if answer == 'modify':
            dictionary[key] = modify_value(value_prompt, level=level,
                                           value=value, all_values=all_values)
        elif answer == 'empty':
            dictionary[key] = ''
        elif answer == 'quit':
            break

    return str(dictionary)

def modify_option(config, section, option, config_path, backup_parameters=None,
                  initial_value=None, prompts=None, items=None,
                  all_values=None, limits=()):
    if backup_parameters:
        file_utilities.backup_file(config_path, **backup_parameters)
    if initial_value:
        config[section].setdefault(option, initial_value)
    if prompts is None:
        prompts = {}

    if config.has_option(section, option):
        print(f'{ANSI_IDENTIFIER}{option}{ANSI_RESET} = '
              f'{ANSI_CURRENT}{config[section][option]}{ANSI_RESET}')
        # TODO: use can_insert for default/delete
        try:
            boolean_value = get_strict_boolean(config, section, option)
            answer = tidy_answer(['modify', 'toggle', 'empty', 'default',
                                  'quit'])
        except ValueError:
            answer = tidy_answer(['modify', 'empty', 'default', 'quit'])

        if answer == 'modify':
            evaluated_value = evaluate_value(config[section][option])
            if isinstance(evaluated_value, dict):
                config[section][option] = modify_dictionary(
                    evaluated_value, level=1, prompts=prompts,
                    all_values=all_values)
            elif isinstance(evaluated_value, tuple):
                config[section][option] = modify_tuple(
                    evaluated_value, level=1, prompts=prompts,
                    all_values=all_values)
            elif (isinstance(evaluated_value, list)
                  and all(isinstance(item, tuple)
                          for item in evaluated_value)):
                if evaluated_value == [()]:
                    evaluated_value = []

                tuple_list = modify_tuple_list(
                    evaluated_value, prompts=prompts, items=items)
                if tuple_list:
                    config[section][option] = str(tuple_list)
                else:
                    delete_option(config, section, option, config_path)
                    return False
            else:
                config[section][option] = modify_value(
                    prompts.get('value', 'value'),
                    value=config[section][option], limits=limits)
        elif answer == 'toggle':
            config[section][option] = str(not boolean_value)
        elif answer == 'empty':
            config[section][option] = ''
        elif answer == 'default':
            delete_option(config, section, option, config_path)
            return False
        elif answer in {'', 'quit'}:
            if config[section][option] == initial_value:
                delete_option(config, section, option, config_path)
                return False
            return answer

        write_config(config, config_path)
        return True

    print(option, 'option does not exist.')
    return False

def modify_section(config, section, config_path, backup_parameters=None,
                   can_insert=False, prompts=None, items=None,
                   all_values=None):
    if backup_parameters:
        file_utilities.backup_file(config_path, **backup_parameters)
    if prompts is None:
        prompts = {}

    if config.has_section(section):
        for option in config[section]:
            result = modify_option(config, section, option, config_path,
                                   prompts=prompts, items=items,
                                   all_values=all_values)
            if result in {'quit'}:
                return result

        if can_insert:
            is_inserted = False
            while True:
                print(f'{ANSI_WARNING}'
                      f"{prompts.get('end_of_list', 'end of section')}"
                      f'{ANSI_RESET}')
                answer = tidy_answer(['insert', 'quit'])
                if answer == 'insert':
                    option = modify_value(prompts.get('key', 'option'))
                    if all_values:
                        config[section][option] = modify_tuple(
                            (), level=1, prompts=prompts,
                            all_values=all_values)
                        if config[section][option] != '()':
                            is_inserted = True
                    else:
                        config[section][option] = modify_value('value')
                        if config[section][option]:
                            is_inserted = True
                else:
                    break
            if is_inserted:
                write_config(config, config_path)

        return True

    print(section, 'section does not exist.')
    return False

def modify_tuple(tuple_entry, level=0, prompts=None, all_values=None):
    tuple_entry = list(tuple_entry)
    values_prompt = prompts.get('values', ())

    index = 0
    while index <= len(tuple_entry):
        if index == len(tuple_entry):
            print(f'{INDENT * level}'
                  f"{ANSI_WARNING}{prompts.get('end_of_list', 'end of tuple')}"
                  f'{ANSI_RESET}')
            answers = ['insert', 'back', 'quit']
        else:
            print(f'{INDENT * level}'
                  f'{ANSI_CURRENT}{tuple_entry[index]}{ANSI_RESET}')
            if values_prompt:
                answers = ['modify', 'empty', 'back', 'quit']
            else:
                answers = ['insert', 'modify', 'delete', 'back', 'quit']
        if index == 0:
            answers.remove('back')

        answer = tidy_answer(answers, level=level)

        if answer in {'insert', 'modify'}:
            value = '' if answer == 'insert' else tuple_entry[index]
            value_prompt = (values_prompt[index]
                            if values_prompt[index:index + 1]
                            else prompts.get('value', 'value'))
            if all_values and len(all_values) == 1:
                value = modify_value(value_prompt, level=level, value=value,
                                     all_values=all_values[0])
            elif all_values and all_values[index:index + 1]:
                value = modify_value(value_prompt, level=level, value=value,
                                     all_values=all_values[index])
            else:
                value = modify_value(value_prompt, level=level, value=value)
            if answer == 'insert':
                tuple_entry.insert(index, value)
            else:
                tuple_entry[index] = value
        elif answer == 'empty':
            tuple_entry[index] = ''
        elif answer == 'delete':
            del tuple_entry[index]
            index -= 1
        elif answer == 'back':
            index -= 2
        elif answer == 'quit':
            break

        index += 1
        if values_prompt and index == len(values_prompt):
            break

    return str(tuple(tuple_entry))

def modify_tuple_list(tuple_list, level=0, prompts=None, items=None):
    if not isinstance(tuple_list, list):
        tuple_list = []
    if items is None:
        items = {}

    value_prompt = prompts.get('value', 'value')
    additional_value_prompt = prompts.get('additional_value',
                                          'additional value')

    index = 0
    while index <= len(tuple_list):
        if index == len(tuple_list):
            print(f'{INDENT * level}'
                  f"{ANSI_WARNING}{prompts.get('end_of_list', 'end of list')}"
                  f'{ANSI_RESET}')
            answers = ['insert', 'back', 'quit']
        else:
            print(f'{INDENT * level}'
                  f'{ANSI_CURRENT}{tuple_list[index]}{ANSI_RESET}')
            answers = ['insert', 'modify', 'delete', 'back', 'quit']
        if index == 0:
            answers.remove('back')

        answer = tidy_answer(answers, level=level)

        if answer in {'insert', 'modify'}:
            if answer == 'insert':
                key = value = additional_value = ''
            else:
                key, value, additional_value = (
                    tuple_list[index] + ('', ''))[:3]

            key = modify_value(prompts.get('key', 'key'), level=level,
                               value=key, all_values=items.get('all_keys'))
            preset_values = (
                items.get('preset_values')
                if key in items.get('preset_values_keys', set()) else None)
            if key in items.get('no_value_keys', set()):
                tuple_entry = (key,)
            elif key in items.get('optional_value_keys', set()):
                value = modify_value(value_prompt, level=level, value=value,
                                     all_values=('None',))
                tuple_entry = ((key,) if value.lower() in {'', 'none'}
                                 else (key, value))
            elif key in items.get('additional_value_keys', set()):
                value = modify_value(value_prompt, level=level, value=value)
                additional_value = modify_value(additional_value_prompt,
                                                level=level,
                                                value=additional_value)
                tuple_entry = (key, value, additional_value)
            elif key in items.get('optional_additional_value_keys', set()):
                value = modify_value(value_prompt, level=level, value=value)
                additional_value = modify_value(
                    additional_value_prompt, level=level,
                    value=additional_value, all_values=('None',))
                tuple_entry = (
                    (key, value) if additional_value.lower() in {'', 'none'}
                    else (key, value, additional_value))
            elif key in items.get('positioning_keys', set()):
                value = configure_position(level=level, value=value)
                tuple_entry = (key, value)
            elif key in items.get('control_flow_keys', set()):
                value = modify_value(value_prompt, level=level, value=value,
                                     all_values=preset_values)
                nested_answer = tidy_answer(['build', 'call'], level=level)
                if nested_answer == 'build':
                    if isinstance(additional_value, str):
                        additional_value = None

                    level += 1
                    additional_value = modify_tuple_list(
                        additional_value, level=level, prompts=prompts,
                        items=items)
                    level -= 1
                elif nested_answer == 'call':
                    if isinstance(additional_value, list):
                        additional_value = None

                    additional_value = modify_value(
                        prompts.get('preset_additional_value',
                                    'preset additional value'),
                        level=level, value=additional_value,
                        all_values=items.get('preset_additional_values'))

                tuple_entry = (key, value, additional_value)
            else:
                value = modify_value(value_prompt, level=level, value=value,
                                     all_values=preset_values)
                tuple_entry = (key, value)
            if answer == 'insert':
                tuple_list.insert(index, tuple_entry)
            else:
                tuple_list[index] = tuple_entry
        elif answer == 'delete':
            del tuple_list[index]
            index -= 1
        elif answer == 'back':
            index -= 2
        elif answer == 'quit':
            break

        index += 1

    return tuple_list

def modify_value(prompt, level=0, value='', all_values=None, limits=()):
    value = prompt_for_input(prompt, level=level, value=value,
                             all_values=all_values)

    minimum_value, maximum_value = limits or (None, None)
    numeric_value = None
    if isinstance(minimum_value, int) and isinstance(maximum_value, int):
        try:
            numeric_value = int(float(value))
        except ValueError as e:
            print(e)
            sys.exit(2)
    if isinstance(minimum_value, float) and isinstance(maximum_value, float):
        try:
            numeric_value = float(value)
        except ValueError as e:
            print(e)
            sys.exit(2)
    if numeric_value is not None:
        if minimum_value is not None:
            numeric_value = max(minimum_value, numeric_value)
        if maximum_value is not None:
            numeric_value = min(maximum_value, numeric_value)

        value = str(numeric_value)

    if all_values and value not in all_values and all_values != ('None',):
        value = modify_value(prompt, level=level,
                             value=f'{ANSI_RESET}{ANSI_ERROR}{value}',
                             all_values=all_values)

    return value

def prompt_for_input(prompt, level=0, value='', all_values=None):
    if value:
        prompt_prefix = (f'{INDENT * level}{prompt} '
                         f'{ANSI_CURRENT}{value}{ANSI_RESET}: ')
    else:
        prompt_prefix = f'{INDENT * level}{prompt}: '

    completer = None
    if all_values:
        completer = CustomWordCompleter(all_values, ignore_case=True)
    elif value:
        completer = CustomWordCompleter([value], ignore_case=True)

    if completer:
        value = (pt_prompt(ANSI(prompt_prefix), completer=completer).strip()
                 or value)
    else:
        value = input(prompt_prefix).strip()
    return value

def read_config(config, config_path):
    encrypted_config_path = config_path + '.gpg'
    if os.path.exists(encrypted_config_path):
        with open(encrypted_config_path, 'rb') as f:
            encrypted_config = f.read()

        gpg = gnupg.GPG()
        decrypted_config = gpg.decrypt(encrypted_config)
        config.read_string(decrypted_config.data.decode())
    else:
        config.read(config_path, encoding='utf-8')

def tidy_answer(answers, level=0):
    initialism = ''

    previous_initialism = ''
    for word_index, word in enumerate(answers):
        for char_index, _ in enumerate(word):
            if word[char_index].lower() not in initialism:
                mnemonics = word[char_index]
                initialism = initialism + mnemonics.lower()
                break
        if initialism == previous_initialism:
            print('Undetermined mnemonics.')
            sys.exit(1)
        else:
            previous_initialism = initialism
            highlighted_word = word.replace(
                mnemonics, f'{ANSI_UNDERLINE}{mnemonics}{ANSI_RESET}', 1)
            if word_index == 0:
                prompt = highlighted_word
            else:
                prompt = f'{prompt}/{highlighted_word}'

    answer = input(f'{INDENT * level}{prompt}: ').strip().lower()
    if answer:
        if answer[0] not in initialism:
            answer = ''
        else:
            for index, _ in enumerate(initialism):
                if initialism[index] == answer[0]:
                    answer = answers[index]
    return answer

def write_config(config, config_path):
    encrypted_config_path = config_path + '.gpg'
    if os.path.exists(encrypted_config_path):
        config_string = StringIO()
        config.write(config_string)
        gpg = gnupg.GPG()
        gpg.encoding = 'utf-8'
        fingerprint = ''
        if config.has_option('General', 'fingerprint'):
            fingerprint = config['General']['fingerprint']
        if not fingerprint:
            fingerprint = gpg.list_keys()[0]['fingerprint']

        encrypted_config = gpg.encrypt(config_string.getvalue(), fingerprint,
                                       armor=False)
        with open(encrypted_config_path, 'wb') as f:
            f.write(encrypted_config.data)
    else:
        with open(config_path, 'w', encoding='utf-8') as f:
            config.write(f)

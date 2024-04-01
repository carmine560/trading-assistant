from io import StringIO
import ast
import configparser
import os
import sys
import time

from prompt_toolkit import ANSI
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion, WordCompleter
from prompt_toolkit.shortcuts import CompleteStyle
import gnupg

try:
    import pyautogui
    import win32api
    GUI_IMPORT_ERROR = None
except ModuleNotFoundError as import_error:
    GUI_IMPORT_ERROR = import_error

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
                         backup_function=None, backup_parameters=None):
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

    if backup_function:
        backup_function(config_path, **backup_parameters)

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

def configure_position(answer, level=0, value=''):
    if GUI_IMPORT_ERROR:
        print(GUI_IMPORT_ERROR)
        return False

    prompt_prefix = f'{INDENT * level}input/{ANSI_UNDERLINE}c{ANSI_RESET}lick'
    if answer == 'modify' and value:
        completer = WordCompleter([value])
        value = pt_prompt(
            ANSI(prompt_prefix + ': '), completer=completer,
            complete_style=CompleteStyle.READLINE_LIKE).strip() or value
    else:
        value = input(prompt_prefix + ': ').strip()

    if value and value[0].lower() == 'c':
        previous_key_state = win32api.GetKeyState(0x01)
        coordinates = ''
        while True:
            key_state = win32api.GetKeyState(0x01)
            if key_state != previous_key_state:
                if key_state not in [0, 1]:
                    x, y = pyautogui.position()
                    coordinates = f'{x}, {y}'
                    break

            time.sleep(0.001)
        return coordinates
    return value

def delete_option(config, section, option, config_path, backup_function=None,
                  backup_parameters=None):
    if backup_function:
        backup_function(config_path, **backup_parameters)

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

def list_section(config, section):
    options = []
    if config.has_section(section):
        for option in config[section]:
            options.append(option)
        return options

    print(section, 'section does not exist.')
    return False

def modify_data(prompt, level=0, data='', all_data=None, minimum_value=None,
                maximum_value=None):
    if data:
        prompt_prefix = (f'{INDENT * level}{prompt} '
                         f'{ANSI_CURRENT}{data}{ANSI_RESET}: ')
    else:
        prompt_prefix = f'{INDENT * level}{prompt}: '

    completer = None
    if all_data:
        completer = CustomWordCompleter(all_data, ignore_case=True)
    elif data:
        completer = CustomWordCompleter([data], ignore_case=True)

    if completer:
        data = pt_prompt(ANSI(prompt_prefix),
                         completer=completer,).strip() or data
    else:
        data = input(prompt_prefix).strip()

    numeric_value = None
    if isinstance(minimum_value, int) and isinstance(maximum_value, int):
        try:
            numeric_value = int(float(data))
        except ValueError as e:
            print(e)
            sys.exit(2)
    if isinstance(minimum_value, float) and isinstance(maximum_value, float):
        try:
            numeric_value = float(data)
        except ValueError as e:
            print(e)
            sys.exit(2)
    if numeric_value is not None:
        if minimum_value is not None:
            numeric_value = max(minimum_value, numeric_value)
        if maximum_value is not None:
            numeric_value = min(maximum_value, numeric_value)

        data = str(numeric_value)

    return data

def modify_dictionary(dictionary_data, level=0, prompts=None,
                      dictionary_values=None):
    value_prompt = prompts.get('value', 'value')

    for key, value in dictionary_data.items():
        print(f'{INDENT * level}{ANSI_IDENTIFIER}{key}{ANSI_RESET}: '
              f'{ANSI_CURRENT}{value}{ANSI_RESET}')
        answer = tidy_answer(['modify', 'empty', 'quit'], level=level)
        if answer == 'modify':
            dictionary_data[key] = modify_data(value_prompt, level=level,
                                               data=value,
                                               all_data=dictionary_values)
        elif answer == 'empty':
            dictionary_data[key] = ''
        elif answer == 'quit':
            break

    return str(dictionary_data)

def modify_option(config, section, option, config_path, backup_function=None,
                  backup_parameters=None, prompts=None, categorized_keys=None,
                  tuple_values=None, dictionary_values=None,
                  minimum_value=None, maximum_value=None):
    if backup_function:
        backup_function(config_path, **backup_parameters)
    if prompts is None:
        prompts = {}
    if categorized_keys is None:
        categorized_keys = {}

    if config.has_option(section, option):
        print(f'{ANSI_IDENTIFIER}{option}{ANSI_RESET} = '
              f'{ANSI_CURRENT}{config[section][option]}{ANSI_RESET}')
        try:
            boolean_value = config[section].getboolean(option)
            answer = tidy_answer(['modify', 'toggle', 'empty', 'default',
                                  'quit'])
        except ValueError:
            answer = tidy_answer(['modify', 'empty', 'default', 'quit'])

        if answer == 'modify':
            evaluated_value = evaluate_value(config[section][option])
            if (isinstance(evaluated_value, list)
                and all(isinstance(item, tuple) for item in evaluated_value)):
                modify_tuple_list(config, section, option, config_path,
                                  categorized_keys=categorized_keys)
            elif isinstance(evaluated_value, tuple):
                config[section][option] = modify_tuple(
                    evaluated_value, False, level=1, prompts=prompts,
                    tuple_values=tuple_values)
            elif isinstance(evaluated_value, dict):
                config[section][option] = modify_dictionary(
                    evaluated_value, level=1, prompts=prompts,
                    dictionary_values=dictionary_values)
            else:
                config[section][option] = modify_data(
                    prompts.get('value', 'value'),
                    data=config[section][option], minimum_value=minimum_value,
                    maximum_value=maximum_value)
        elif answer == 'toggle':
            config[section][option] = str(not boolean_value)
        elif answer == 'empty':
            config[section][option] = ''
        elif answer == 'default':
            config.remove_option(section, option)
        elif answer == 'quit':
            return answer

        write_config(config, config_path)
        return True

    print(option, 'option does not exist.')
    return False

def modify_section(config, section, config_path, backup_function=None,
                   backup_parameters=None, can_insert=False,
                   value_type='string', prompts=None, categorized_keys=None,
                   tuple_values=None):
    if backup_function:
        backup_function(config_path, **backup_parameters)
    if prompts is None:
        prompts = {}
    if categorized_keys is None:
        categorized_keys = {}

    if config.has_section(section):
        for option in config[section]:
            result = modify_option(config, section, option, config_path,
                                   prompts=prompts,
                                   categorized_keys=categorized_keys,
                                   tuple_values=tuple_values)
            if result in ('quit', False):
                return result

        if can_insert:
            end_of_list_prompt = prompts.get('end_of_list', 'end of section')
            is_inserted = False
            while True:
                print(f'{ANSI_WARNING}{end_of_list_prompt}{ANSI_RESET}')
                answer = tidy_answer(['insert', 'quit'])
                if answer == 'insert':
                    option = modify_data(prompts.get('key', 'option'))
                    if value_type == 'string':
                        config[section][option] = modify_data('value')
                        if config[section][option]:
                            is_inserted = True
                    elif value_type == 'tuple':
                        config[section][option] = modify_tuple(
                            (), True, level=1, prompts=prompts,
                            tuple_values=tuple_values)
                        if config[section][option] != '()':
                            is_inserted = True
                else:
                    break
            if is_inserted:
                write_config(config, config_path)

        return True

    print(section, 'section does not exist.')
    return False

def modify_tuple(tuple_data, is_created, level=0, prompts=None,
                 tuple_values=None):
    tuple_data = list(tuple_data)
    value_prompt = prompts.get('value', 'value')
    values_prompt = prompts.get('values')
    end_of_list_prompt = prompts.get('end_of_list', 'end of tuple')

    index = 0
    while index <= len(tuple_data):
        if is_created or index == len(tuple_data):
            print(f'{INDENT * level}'
                  f'{ANSI_WARNING}{end_of_list_prompt}{ANSI_RESET}')
            answer = tidy_answer(['insert', 'quit'], level=level)
        else:
            print(f'{INDENT * level}'
                  f'{ANSI_CURRENT}{tuple_data[index]}{ANSI_RESET}')
            if values_prompt:
                answer = tidy_answer(['modify', 'empty', 'quit'], level=level)
            else:
                answer = tidy_answer(['insert', 'modify', 'delete', 'quit'],
                                     level=level)

        if values_prompt and index < len(values_prompt):
            value_prompt = values_prompt[index]
        if answer == 'insert':
            if tuple_values and tuple_values[index:index + 1]:
                value = modify_data(value_prompt, level=level,
                                    all_data=tuple_values[index])
            elif tuple_values and len(tuple_values) == 1:
                value = modify_data(value_prompt, level=level,
                                    all_data=tuple_values[0])
            else:
                value = modify_data(value_prompt, level=level)
            if value:
                tuple_data.insert(index, value)
        elif answer == 'modify':
            if tuple_values and tuple_values[index:index + 1]:
                tuple_data[index] = modify_data(value_prompt, level=level,
                                                data=tuple_data[index],
                                                all_data=tuple_values[index])
            elif tuple_values and len(tuple_values) == 1:
                tuple_data[index] = modify_data(value_prompt, level=level,
                                                data=tuple_data[index],
                                                all_data=tuple_values[0])
            else:
                tuple_data[index] = modify_data(value_prompt, level=level,
                                                data=tuple_data[index])
        elif answer == 'empty':
            tuple_data[index] = ''
        elif answer == 'delete':
            del tuple_data[index]
            index -= 1
        elif answer == 'quit':
            break

        index += 1
        if values_prompt and index == len(values_prompt):
            break

    return str(tuple(tuple_data))

def modify_tuple_list(config, section, option, config_path,
                      backup_function=None, backup_parameters=None,
                      prompts=None, categorized_keys=None):
    if backup_function:
        backup_function(config_path, **backup_parameters)
    if prompts is None:
        prompts = {}
    if categorized_keys is None:
        categorized_keys = {}

    is_created = False
    if not config.has_section(section):
        config[section] = {}
    if not config.has_option(section, option):
        is_created = True
        config[section][option] = '[]'

    tuples = modify_tuples(evaluate_value(config[section][option]), is_created,
                           prompts=prompts, categorized_keys=categorized_keys)
    if tuples:
        config[section][option] = str(tuples)
        write_config(config, config_path)
        return True

    delete_option(config, section, option, config_path)
    return False

def modify_tuples(tuples, is_created, level=0, prompts=None,
                  categorized_keys=None):
    if not isinstance(tuples, list):
        tuples = []

    key_prompt = prompts.get('key', 'key')
    value_prompt = prompts.get('value', 'value')
    additional_value_prompt = prompts.get('additional_value',
                                          'additional value')
    preset_additional_value_prompt = prompts.get('preset_additional_value',
                                                 'preset additional value')
    end_of_list_prompt = prompts.get('end_of_list', 'end of list')

    index = 0
    while index <= len(tuples):
        if is_created or index == len(tuples):
            print(f'{INDENT * level}'
                  f'{ANSI_WARNING}{end_of_list_prompt}{ANSI_RESET}')
            answer = tidy_answer(['insert', 'quit'], level=level)
        else:
            print(f'{INDENT * level}'
                  f'{ANSI_CURRENT}{tuples[index]}{ANSI_RESET}')
            answer = tidy_answer(['insert', 'modify', 'delete', 'quit'],
                                 level=level)

        if answer == 'insert':
            key = modify_data(key_prompt, level=level,
                              all_data=categorized_keys.get('all_keys'))
            if key in categorized_keys.get('control_flow_keys'):
                # TODO: add trigger
                value = modify_data(value_prompt, level=level)
                answer = tidy_answer(['build', 'call'], level=level)
                if answer == 'build':
                    level += 1
                    additional_value = modify_tuples(
                        [], True, level=level, prompts=prompts,
                        categorized_keys=categorized_keys)
                    level -= 1
                elif answer == 'call':
                    additional_value = modify_data(
                        preset_additional_value_prompt, level=level,
                        all_data=categorized_keys.get(
                            'preset_additional_values'))

                tuples.insert(index, (key, value, additional_value))
            elif key in categorized_keys.get('additional_value_keys'):
                value = modify_data(value_prompt, level=level)
                additional_value = modify_data(additional_value_prompt,
                                               level=level)
                # TODO: write_chapter
                if value and additional_value:
                    tuples.insert(index, (key, value, additional_value))
            elif key in categorized_keys.get('no_value_keys'):
                tuples.insert(index, (key,))
            elif key in categorized_keys.get('positioning_keys'):
                value = configure_position(answer, level=level)
                tuples.insert(index, (key, value))
            else:
                value = modify_data(value_prompt, level=level)
                # TODO: count_trades
                if value:
                    tuples.insert(index, (key, value))
        elif answer == 'modify':
            key = tuples[index][0]
            value = additional_value = ''
            if len(tuples[index]) > 1:
                value = tuples[index][1]
            if len(tuples[index]) > 2:
                additional_value = tuples[index][2]

            key = modify_data(key_prompt, level=level, data=key,
                              all_data=categorized_keys.get('all_keys'))
            if key in categorized_keys.get('control_flow_keys'):
                value = modify_data(value_prompt, level=level, data=value)
                answer = tidy_answer(['build', 'call'], level=level)
                if answer == 'build':
                    level += 1
                    additional_value = modify_tuples(
                        additional_value, is_created, level=level,
                        prompts=prompts, categorized_keys=categorized_keys)
                    level -= 1
                elif answer == 'call':
                    additional_value = modify_data(
                        preset_additional_value_prompt, level=level,
                        all_data=categorized_keys.get(
                            'preset_additional_values'))

                tuples[index] = (key, value, additional_value)
            elif key in categorized_keys.get('additional_value_keys'):
                value = modify_data(value_prompt, level=level, data=value)
                additional_value = modify_data(additional_value_prompt,
                                               level=level,
                                               data=additional_value)
                if value and additional_value:
                    tuples[index] = (key, value, additional_value)
                else:
                    del tuples[index]
                    index -= 1
            elif key in categorized_keys.get('no_value_keys'):
                tuples[index] = (key,)
            elif key in categorized_keys.get('positioning_keys'):
                value = configure_position(answer, level=level, value=value)
                tuples[index] = (key, value)
            else:
                value = modify_data(value_prompt, level=level, data=value)
                if value:
                    tuples[index] = (key, value)
        elif answer == 'delete':
            del tuples[index]
            index -= 1
        elif answer == 'quit':
            index = len(tuples)

        index += 1

    return tuples

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
            if not word[char_index].lower() in initialism:
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
        if not answer[0] in initialism:
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

import ast
import os
import sys

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

def check_config_changes(default_config, config_path, excluded_sections=(),
                         backup_function=None, backup_parameters=None):
    # TODO: config[trade.actions_title]
    import configparser

    def truncate_string(string):
        max_length = 256
        if len(string) > max_length:
            string = string[:max_length] + '...'
        return string

    def display_changes(config, config_path, section, option, option_status):
        global previous_section
        if section != previous_section:
            print(f'[{ANSI_BOLD}{section}{ANSI_RESET}]')
            previous_section = section

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

    global previous_section
    previous_section = None
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
                    if not display_changes(user_config, config_path, section,
                                           option, option_status):
                        return
            for option in user_config[section]:
                if not default_config.has_option(section, option):
                    default_value = '(not exist)'
                    user_value = (truncate_string(user_config[section][option])
                                  if user_config[section][option]
                                  else '(empty)')
                    option_status = (
                        f'{ANSI_IDENTIFIER}{option}{ANSI_RESET}: '
                        f'{ANSI_WARNING}{default_value}{ANSI_RESET} → '
                        f'{user_value}')
                    if not display_changes(user_config, config_path, section,
                                           option, option_status):
                        return

def configure_position(answer, level=0, value=''):
    import time

    import pyautogui
    import win32api

    from prompt_toolkit import ANSI
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.shortcuts import CompleteStyle

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
        current_number = 0
        coordinates = ''
        while True:
            key_state = win32api.GetKeyState(0x01)
            if key_state != previous_key_state:
                if key_state not in [0, 1]:
                    x, y = pyautogui.position()
                    coordinates = str(x) + ', ' + str(y)
                    break

            time.sleep(0.001)

        return coordinates
    else:
        return value

def delete_option(config, section, option, config_path, backup_function=None,
                  backup_parameters=None):
    if backup_function:
        backup_function(config_path, **backup_parameters)

    if config.has_option(section, option):
        config.remove_option(section, option)
        write_config(config, config_path)
        return True
    else:
        print(option, 'option does not exist.')
        return False

def list_section(config, section):
    options = []
    if config.has_section(section):
        for option in config[section]:
            options.append(option)
        return options
    else:
        print(section, 'section does not exist.')
        return False

def modify_data(prompt, level=0, data='', all_data=[]):
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.shortcuts import CompleteStyle

    completer = None
    if all_data:
        completer = WordCompleter(all_data, ignore_case=True)
    elif data:
        completer = WordCompleter([data])

    prompt_prefix = INDENT * level + prompt
    if completer:
        data = pt_prompt(
            prompt_prefix + ': ', completer=completer,
            complete_style=CompleteStyle.READLINE_LIKE).strip() or data
    elif data:
        data = input(prompt_prefix + ' '
                     + ANSI_CURRENT + data + ANSI_RESET + ': ').strip() or data
    else:
        data = input(prompt_prefix + ': ').strip()
    return data

def modify_dictionary(data, level=0, prompts={}, dictionary_info={}):
    data = ast.literal_eval(data)
    value_prompt = prompts.get('value', 'value')
    possible_values = dictionary_info.get('possible_values')

    for key, value in data.items():
        print(f'{INDENT * level}{ANSI_IDENTIFIER}{key}{ANSI_RESET}: '
              f'{ANSI_CURRENT}{data[key]}{ANSI_RESET}')
        answer = tidy_answer(['modify', 'empty', 'quit'], level=level)
        if answer == 'modify':
            if possible_values:
                data[key] = modify_data(value_prompt, level=level,
                                        all_data=possible_values)
            else:
                data[key] = modify_data(value_prompt, level=level,
                                        data=data[key])
        elif answer == 'empty':
            data[key] = ''
        elif answer == 'quit':
            break

    return str(data)

def modify_option(config, section, option, config_path, backup_function=None,
                  backup_parameters=None, prompts={}, categorized_keys={},
                  tuple_info={}, dictionary_info={}):
    import re

    if backup_function:
        backup_function(config_path, **backup_parameters)

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
            if re.sub(r'\s+', '', config[section][option])[:2] == '[(':
                modify_tuple_list(config, section, option, config_path,
                                  categorized_keys=categorized_keys)
            elif re.sub(r'\s+', '', config[section][option])[:1] == '(':
                config[section][option] = modify_tuple(
                    config[section][option], False, level=1,
                    tuple_info=tuple_info)
            elif re.sub(r'\s+', '', config[section][option])[:1] == '{':
                config[section][option] = modify_dictionary(
                    config[section][option], level=1, prompts=prompts,
                    dictionary_info=dictionary_info)
            else:
                config[section][option] = modify_data(
                    prompts.get('value', 'value'),
                    data=config[section][option])
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
    else:
        print(option, 'option does not exist.')
        return False

def modify_section(config, section, config_path, backup_function=None,
                   backup_parameters=None, is_inserting=False,
                   value_format='string', prompts={}, categorized_keys={},
                   tuple_info={}):
    if backup_function:
        backup_function(config_path, **backup_parameters)

    if config.has_section(section):
        for option in config[section]:
            result = modify_option(config, section, option, config_path,
                                   categorized_keys=categorized_keys,
                                   tuple_info=tuple_info)
            if result == 'quit' or result == False:
                return result

        if is_inserting:
            end_of_list_prompt = prompts.get('end_of_list', 'end of section')
            is_inserted = False
            while is_inserting:
                print(ANSI_WARNING + end_of_list_prompt + ANSI_RESET)
                # TODO: unify
                answer = tidy_answer(['insert'])
                if answer == 'insert':
                    option = modify_data('option')
                    if value_format == 'string':
                        config[section][option] = modify_data('value')
                        if config[section][option]:
                            is_inserted = True
                    elif value_format == 'tuple':
                        config[section][option] = '()'
                        config[section][option] = modify_tuple(
                            config[section][option], True, level=1,
                            tuple_info=tuple_info)
                        if config[section][option] != '()':
                            is_inserted = True
                else:
                    is_inserting = False
            if is_inserted:
                write_config(config, config_path)

        return True
    else:
        print(section, 'section does not exist.')
        return False

def modify_tuple(data, is_created, level=0, prompts={}, tuple_info={}):
    data = list(ast.literal_eval(data))
    value_prompt = prompts.get('value', 'value')
    end_of_list_prompt = prompts.get('end_of_list', 'end of tuple')
    element_index = tuple_info.get('element_index')
    possible_values = tuple_info.get('possible_values')

    index = 0
    while index <= len(data):
        if is_created or index == len(data):
            print(INDENT * level
                  + ANSI_WARNING + end_of_list_prompt + ANSI_RESET)
            answer = tidy_answer(['insert', 'quit'], level=level)
        else:
            print(INDENT * level
                  + ANSI_CURRENT + str(data[index]) + ANSI_RESET)
            answer = tidy_answer(['insert', 'modify', 'delete', 'quit'],
                                 level=level)

        if answer == 'insert':
            if ((element_index == -1 or index == element_index)
                and possible_values):
                value = modify_data(value_prompt, level=level,
                                    all_data=possible_values)
            else:
                value = modify_data(value_prompt, level=level)
            if value:
                data.insert(index, value)
        elif answer == 'modify':
            if ((element_index == -1 or index == element_index)
                and possible_values):
                data[index] = modify_data(value_prompt, level=level,
                                          all_data=possible_values)
            else:
                data[index] = modify_data(value_prompt, level=level,
                                          data=data[index])
        elif answer == 'delete':
            del data[index]
            index -= 1
        elif answer == 'quit':
            index = len(data)

        index += 1

    return str(tuple(data))

def modify_tuple_list(config, section, option, config_path,
                      backup_function=None, backup_parameters=None, prompts={},
                      categorized_keys={}):
    if backup_function:
        backup_function(config_path, **backup_parameters)

    is_created = False
    if not config.has_section(section):
        config[section] = {}
    if not config.has_option(section, option):
        is_created = True
        config[section][option] = '[]'

    tuples = modify_tuples(ast.literal_eval(config[section][option]),
                           is_created, prompts=prompts,
                           categorized_keys=categorized_keys)
    if tuples:
        config[section][option] = str(tuples)
        write_config(config, config_path)
        return True
    else:
        delete_option(config, section, option, config_path)
        return False

def modify_tuples(tuples, is_created, level=0, prompts={},
                  categorized_keys={}):
    key_prompt = prompts.get('key', 'key')
    value_prompt = prompts.get('value', 'value')
    additional_value_prompt = prompts.get('additional_value',
                                          'additional value')
    end_of_list_prompt = prompts.get('end_of_list', 'end of list')

    all_keys = categorized_keys.get('all_keys', [])
    control_flow_keys = categorized_keys.get('control_flow_keys', ())
    additional_value_keys = categorized_keys.get('additional_value_keys', ())
    no_value_keys = categorized_keys.get('no_value_keys', ())
    positioning_keys = categorized_keys.get('positioning_keys', ())

    index = 0
    while index <= len(tuples):
        if is_created or index == len(tuples):
            print(INDENT * level
                  + ANSI_WARNING + end_of_list_prompt + ANSI_RESET)
            answer = tidy_answer(['insert', 'quit'], level=level)
        else:
            print(INDENT * level
                  + ANSI_CURRENT + str(tuples[index]) + ANSI_RESET)
            answer = tidy_answer(['insert', 'modify', 'delete', 'quit'],
                                 level=level)

        if answer == 'insert':
            key = modify_data(key_prompt, level=level, all_data=all_keys)
            if any(k == key for k in control_flow_keys):
                value = modify_data(value_prompt, level=level)
                level += 1
                additional_value = modify_tuples(
                    [], True, level=level, prompts=prompts,
                    categorized_keys=categorized_keys)
                level -= 1
                tuples.insert(index, (key, value, additional_value))
            elif any(k == key for k in additional_value_keys):
                value = modify_data(value_prompt, level=level)
                additional_value = modify_data(additional_value_prompt,
                                               level=level)
                if value and additional_value:
                    tuples.insert(index, (key, value, additional_value))
            elif any(k == key for k in no_value_keys):
                tuples.insert(index, (key,))
            elif any(k == key for k in positioning_keys):
                value = configure_position(answer, level=level)
                tuples.insert(index, (key, value))
            else:
                value = modify_data(value_prompt, level=level)
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
                              all_data=all_keys)
            if any(k == key for k in control_flow_keys):
                value = modify_data(value_prompt, level=level, data=value)
                level += 1
                additional_value = modify_tuples(
                    additional_value, is_created, level=level, prompts=prompts,
                    categorized_keys=categorized_keys)
                level -= 1
                tuples[index] = (key, value, additional_value)
            elif any(k == key for k in additional_value_keys):
                value = modify_data(value_prompt, level=level, data=value)
                additional_value = modify_data(additional_value_prompt,
                                               level=level,
                                               data=additional_value)
                if value and additional_value:
                    tuples[index] = (key, value, additional_value)
                else:
                    del tuples[index]
                    index -= 1
            elif any(k == key for k in no_value_keys):
                tuples[index] = (key,)
            elif any(k == key for k in positioning_keys):
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
        import gnupg

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
        for char_index in range(len(word)):
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
                mnemonics, ANSI_UNDERLINE + mnemonics + ANSI_RESET, 1)
            if word_index == 0:
                prompt = highlighted_word
            else:
                prompt = prompt + '/' + highlighted_word

    answer = input(INDENT * level + prompt + ': ').strip().lower()
    if answer:
        if not answer[0] in initialism:
            answer = ''
        else:
            for index in range(len(initialism)):
                if initialism[index] == answer[0]:
                    answer = answers[index]
    return answer

def write_config(config, config_path):
    encrypted_config_path = config_path + '.gpg'
    if os.path.exists(encrypted_config_path):
        from io import StringIO
        import gnupg

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

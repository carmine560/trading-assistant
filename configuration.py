import ast
import os
import sys

ANSI_DEFAULT = '\033[32m'
ANSI_ANNOTATION = '\033[33m'
ANSI_HIGHLIGHT = '\033[4m'
ANSI_RESET = '\033[m'

def check_config_directory(config_file):
    config_directory = os.path.dirname(config_file)
    if not os.path.isdir(config_directory):
        try:
            os.mkdir(config_directory)
        except OSError as e:
            print(e)
            sys.exit(1)

def list_section(config, section):
    if config.has_section(section):
        for option in config[section]:
            print(option)

def modify_section(config, section, config_file):
    if config.has_section(section):
        for option in config[section]:
            if not modify_option(config, section, option, config_file):
                break

def modify_option(config, section, option, config_file, value_prompt='value'):
    import re

    global ANSI_DEFAULT
    global ANSI_RESET
    if config.has_option(section, option):
        print(option + ' = '
              + ANSI_DEFAULT + config[section][option] + ANSI_RESET)
        answer = tidy_answer(['modify', 'empty', 'default', 'quit'])

        if answer == 'modify':
            if re.sub('\s+', '', config[section][option])[0:2] == '[(':
                modify_tuple_option(config, section, option, config_file)
            else:
                value = config[section][option]
                value = input(value_prompt + ': ').strip() or value
                config[section][option] = value
        elif answer == 'empty':
            config[section][option] = ''
        elif answer == 'default':
            config.remove_option(section, option)
        elif answer == 'quit':
            return False

        check_config_directory(config_file)
        with open(config_file, 'w', encoding='utf-8') as f:
            config.write(f)
            return True

def modify_tuple_option(config, section, option, config_file, key_prompt='key',
                        value_prompt='value', end_of_list_prompt='end of list',
                        boolean_keys=[], positioning_keys=[]):
    created = False
    if not config.has_section(section):
        config[section] = {}
    if not config.has_option(section, option):
        created = True
        config[section][option] = '[]'

    tuples = modify_tuples(ast.literal_eval(config[section][option]),
                           created, key_prompt=key_prompt,
                           value_prompt=value_prompt,
                           end_of_list_prompt=end_of_list_prompt,
                           boolean_keys=boolean_keys,
                           positioning_keys=positioning_keys)
    if tuples:
        config[section][option] = str(tuples)
        check_config_directory(config_file)
        with open(config_file, 'w', encoding='utf-8') as f:
            config.write(f)
        return True
    else:
        delete_option(config, section, option, config_file)
        return False

def tidy_answer(answers, level=0):
    initialism = ''

    previous_initialism = ''
    global ANSI_HIGHLIGHT
    global ANSI_RESET
    for word_index, word in enumerate(answers):
        for char_index in range(len(word)):
            if not word[char_index].lower() in initialism:
                mnemonics = word[char_index]
                initialism = initialism + mnemonics.lower()
                break
        if initialism == previous_initialism:
            print('undetermined mnemonics')
            sys.exit(1)
        else:
            previous_initialism = initialism
            highlighted_word = word.replace(
                mnemonics, ANSI_HIGHLIGHT + mnemonics + ANSI_RESET, 1)
            if word_index == 0:
                prompt = highlighted_word
            elif word_index == len(answers) - 1:
                prompt = prompt + '/' + highlighted_word + ': '
            else:
                prompt = prompt + '/' + highlighted_word

    answer = input('    ' * level + prompt).strip().lower()
    if answer:
        if not answer[0] in initialism:
            answer = ''
        else:
            for index in range(len(initialism)):
                if initialism[index] == answer[0]:
                    answer = answers[index]
    return answer

def modify_tuples(tuples, created, level=0, key_prompt='key',
                  value_prompt='value', end_of_list_prompt='end of list',
                  boolean_keys=[], positioning_keys=[]):
    global ANSI_DEFAULT
    global ANSI_ANNOTATION
    global ANSI_RESET
    if sys.platform == 'win32':
        os.system('color')

    index = 0
    while index <= len(tuples):
        if created:
            print('    ' * level
                  + ANSI_ANNOTATION + end_of_list_prompt + ANSI_RESET)
            answer = tidy_answer(['insert', 'quit'], level=level)
        else:
            if index < len(tuples):
                print('    ' * level
                      + ANSI_DEFAULT + str(tuples[index]) + ANSI_RESET)
                answer = tidy_answer(['insert', 'modify', 'empty', 'delete',
                                      'quit'], level=level)
            else:
                print('    ' * level
                      + ANSI_ANNOTATION + end_of_list_prompt + ANSI_RESET)
                answer = tidy_answer(['insert', 'quit'], level=level)

        if answer == 'insert':
            key = input('    ' * level + key_prompt + ': ').strip()
            if any(k == key for k in boolean_keys):
                value = input('    ' * level + value_prompt + ': ').strip()
                level += 1
                nested_tuples = modify_tuples(
                    [], True, level=level, key_prompt=key_prompt,
                    value_prompt=value_prompt,
                    end_of_list_prompt=end_of_list_prompt,
                    boolean_keys=boolean_keys,
                    positioning_keys=positioning_keys)
                level -= 1
                tuples.insert(index, (key, value, nested_tuples))
            elif any(k == key for k in positioning_keys):
                value = configure_position(answer)
                tuples.insert(index, (key, value))
            else:
                value = input('    ' * level + value_prompt + ': ').strip()
                if value:
                    tuples.insert(index, (key, value))
                else:
                    tuples.insert(index, (key,))
        elif answer == 'modify':
            key = tuples[index][0]
            if len(tuples[index]) == 3:
                value = tuples[index][1]
                nested_tuples = tuples[index][2]
            elif len(tuples[index]) == 2:
                value = tuples[index][1]
            elif len(tuples[index]) == 1:
                value = ''

            key = input('    ' * level + key_prompt + ' '
                        + ANSI_DEFAULT + key + ANSI_RESET
                        + ': ').strip() or key
            if any(k == key for k in boolean_keys):
                value = input('    ' * level + value_prompt + ' '
                              + ANSI_DEFAULT + value + ANSI_RESET
                              + ': ').strip() or value
                level += 1
                nested_tuples = modify_tuples(
                    nested_tuples, created, level=level, key_prompt=key_prompt,
                    value_prompt=value_prompt,
                    end_of_list_prompt=end_of_list_prompt,
                    boolean_keys=boolean_keys,
                    positioning_keys=positioning_keys)
                level -= 1
                tuples[index] = (key, value, nested_tuples)
            elif any(k == key for k in positioning_keys):
                value = configure_position(answer, value)
                tuples[index] = (key, value)
            elif len(tuples[index]) == 2:
                value = input('    ' * level + value_prompt + ' '
                              + ANSI_DEFAULT + value + ANSI_RESET
                              + ': ').strip() or value
            else:
                value = input('    ' * level + value_prompt + ': ').strip()
                if value:
                    tuples[index] = (key, value)
                else:
                    tuples[index] = (key,)
        elif answer == 'empty':
            tuples[index] = (tuples[index][0],)
        elif answer == 'delete':
            del tuples[index]
            index -= 1
        elif answer == 'quit':
            index = len(tuples)

        index += 1

    return tuples

def configure_position(answer, value=''):
    import time

    import pyautogui
    import win32api

    global ANSI_HIGHLIGHT
    global ANSI_DEFAULT
    if answer == 'insert':
        value = input('input/'
                      + ANSI_HIGHLIGHT + 'c' + ANSI_RESET + 'lick: ').strip()
    elif answer == 'modify':
        value = input('input/' + ANSI_HIGHLIGHT + 'c' + ANSI_RESET + 'lick '
                      + ANSI_DEFAULT + value + ANSI_RESET + ': ').strip() \
                      or value

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

def delete_option(config, section, option, config_file):
    if config.has_option(section, option):
        config.remove_option(section, option)
        check_config_directory(config_file)
        with open(config_file, 'w', encoding='utf-8') as f:
            config.write(f)

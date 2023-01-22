import sys

ANSI_DEFAULT = '\033[32m'
ANSI_ANNOTATION = '\033[33m'
ANSI_HIGHLIGHT = '\033[4m'
ANSI_RESET = '\033[m'

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
    global ANSI_DEFAULT
    global ANSI_RESET
    if config.has_option(section, option):
        print(option + ' = '
              + ANSI_DEFAULT + config[section][option] + ANSI_RESET)
        # TODO
        # if empty
        answer = tidy_answer(['modify', 'empty', 'default', 'quit'])

        if answer == 'modify':
            value = config[section][option]
            value = input(value_prompt + ': ').strip() or value
            config[section][option] = value
        elif answer == 'empty':
            config[section][option] = ''
        elif answer == 'default':
            config.remove_option(section, option)
        elif answer == 'quit':
            return False

        with open(config_file, 'w', encoding='utf-8') as f:
            config.write(f)
            return True

def modify_tuple_list(config, section, option, config_file, key_prompt='key',
                      value_prompt='value', end_of_list_prompt='end of list',
                      positioning_keys=[]):
    import ast
    import os

    create = False
    if not config.has_section(section):
        config[section] = {}
    if not config.has_option(section, option):
        create = True
        config[section][option] = '[]'

    i = 0
    tuple_list = ast.literal_eval(config[section][option])
    global ANSI_DEFAULT
    global ANSI_ANNOTATION
    global ANSI_RESET
    if sys.platform == 'win32':
        os.system('color')
    while i <= len(tuple_list):
        if create:
            answer = tidy_answer(['insert', 'quit'])
        else:
            if i < len(tuple_list):
                print(ANSI_DEFAULT + str(tuple_list[i]) + ANSI_RESET)
                answer = tidy_answer(['insert', 'modify', 'delete', 'quit'])
            else:
                print(ANSI_ANNOTATION + end_of_list_prompt + ANSI_RESET)
                answer = tidy_answer(['insert', 'quit'])

        if answer == 'insert':
            key = input(key_prompt + ': ').strip()
            if any(k == key for k in positioning_keys):
                value = configure_position(answer)
            else:
                value = input(value_prompt + ': ').strip()
            if value:
                tuple_list.insert(i, (key, value))
            else:
                tuple_list.insert(i, (key,))
        elif answer == 'modify':
            key = tuple_list[i][0]
            if len(tuple_list[i]) == 2:
                value = tuple_list[i][1]
            elif len(tuple_list[i]) == 1:
                value = ''

            key = input(key_prompt + ' ' + ANSI_DEFAULT + key + ANSI_RESET
                        + ': ').strip() or key
            if any(k == key for k in positioning_keys):
                value = configure_position(answer, value)
            elif len(tuple_list[i]) == 2:
                value = input(value_prompt + ' ' + ANSI_DEFAULT + value
                              + ANSI_RESET + ': ').strip() or value
            else:
                value = input(value_prompt + ': ').strip()
            if value:
                tuple_list[i] = (key, value)
            else:
                tuple_list[i] = (key,)
        elif answer == 'delete':
            del tuple_list[i]
            i -= 1
        elif answer == 'quit':
            i = len(tuple_list)

        i += 1

    if tuple_list:
        config[section][option] = str(tuple_list)
        with open(config_file, 'w', encoding='utf-8') as f:
            config.write(f)
        return True
    else:
        delete_option(config, section, option, config_file)

def tidy_answer(answer_list):
    initialism = ''

    previous_initialism = ''
    global ANSI_HIGHLIGHT
    global ANSI_RESET
    for word_index, word in enumerate(answer_list):
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
            elif word_index == len(answer_list) - 1:
                prompt = prompt + '/' + highlighted_word + ': '
            else:
                prompt = prompt + '/' + highlighted_word

    answer = input(prompt).strip().lower()
    if answer:
        if not answer[0] in initialism:
            answer = ''
        else:
            for index in range(len(initialism)):
                if initialism[index] == answer[0]:
                    answer = answer_list[index]
    return answer

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
        with open(config_file, 'w', encoding='utf-8') as f:
            config.write(f)

import sys

def list_section(config, section):
    if config.has_section(section):
        for key in config[section]:
            print(key)

def modify_tuple_list(config, section, option, positioning_keys=[]):
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
    if sys.platform == 'win32':
        os.system('color')
    while i <= len(tuple_list):
        if create:
            answer = tidy_answer(['insert', 'quit'])
        else:
            if i < len(tuple_list):
                print(tuple_list[i])
                answer = tidy_answer(['insert', 'modify', 'delete', 'quit'])
            else:
                print('end of list')
                answer = tidy_answer(['insert', 'quit'])

        if len(answer):
            if answer[0] == 'i':
                key = input('key: ')
                if any(key == positioning_key
                       for positioning_key in positioning_keys):
                    value = input('input/[c]lick: ')
                    if len(value) and value[0].lower() == 'c':
                        value = configure_position()
                else:
                    value = input('value: ')
                if len(value) == 0 or value == 'None':
                    value = None

                tuple_list.insert(i, (key, value))
            elif answer[0] == 'm':
                key = tuple_list[i][0]
                value = tuple_list[i][1]
                key = input('key [' + str(key) + '] ') or key
                if any(i == key for i in positioning_keys):
                    value = input('input/[c]lick [' + str(value) + '] ') \
                        or value
                    if len(value) and value[0].lower() == 'c':
                        value = configure_position()
                else:
                    value = input('value [' + str(value) + '] ') or value
                if len(value) == 0 or value == 'None':
                    value = None

                tuple_list[i] = key, value
            elif answer[0] == 'd':
                del tuple_list[i]
                i -= 1
            elif answer[0] == 'q':
                i = len(tuple_list)

        i += 1

    if len(tuple_list):
        config[section][option] = str(tuple_list)
        with open(config.config_path, 'w', encoding='utf-8') as f:
            config.write(f)
        return True
    else:
        delete_option(config, section, option)

def tidy_answer(answer_list):
    abbreviation = ''
    previous_abbreviation = ''
    for word_index, word in enumerate(answer_list):
        for char_index in range(len(word)):
            if not word[char_index].lower() in abbreviation:
                mnemonics = word[char_index]
                abbreviation = abbreviation + mnemonics.lower()
                break
        if abbreviation == previous_abbreviation:
            print('undetermined mnemonics')
            sys.exit(1)
        else:
            previous_abbreviation = abbreviation
            highlighted_word = word.replace(
                mnemonics, '\033[1m' + mnemonics + '\033[m', 1)
            if word_index == 0:
                prompt = highlighted_word
            elif word_index == len(answer_list) - 1:
                prompt = prompt + '/' + highlighted_word + ': '
            else:
                prompt = prompt + '/' + highlighted_word

    answer = input(prompt).lower()
    if answer and not answer[0] in abbreviation:
        answer = ''
    return answer

def configure_position():
    import time

    import pyautogui
    import win32api

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

def delete_option(config, section, option):
    if config.has_option(section, option):
        config.remove_option(section, option)
        with open(config.config_path, 'w', encoding='utf-8') as f:
            config.write(f)

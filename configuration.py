import ast
import os
import sys

ANSI_DEFAULT = '\033[32m'
ANSI_ANNOTATION = '\033[33m'
ANSI_HIGHLIGHT = '\033[4m'
ANSI_RESET = '\033[m'

def list_section(config, section):
    """List all options in a section of a configuration file.

    Args:
        config: A configparser object representing the configuration
        file
        section: The name of the section to list options from

    Returns:
        None

    Raises:
        None"""
    if config.has_section(section):
        for option in config[section]:
            print(option)

def modify_section(config, section, config_file, keys={}):
    """Modify a section in a configuration file.

    Args:
        config: ConfigParser object representing the configuration file
        section: Name of the section to be modified
        config_file: Path to the configuration file
        keys: Dictionary containing key-value pairs to be updated in the
        section

    Returns:
        True if the section is modified successfully, False otherwise

    Raises:
        None"""
    if config.has_section(section):
        for option in config[section]:
            result = modify_option(config, section, option, config_file,
                                   keys=keys)
            if result == 'quit' or result == False:
                return result
        return True
    else:
        print(section, 'section does not exist')
        return False

def modify_option(config, section, option, config_file, prompts={}, keys={}):
    """Modifies an option in a configuration file.

    Args:
        config (ConfigParser): A ConfigParser object representing the
        configuration file.
        section (str): The section in which the option is located.
        option (str): The option to be modified.
        config_file (str): The path to the configuration file.
        prompts (dict): A dictionary containing prompts for modifying
        the option.
        keys (dict): A dictionary containing keys for modifying the
        option.

    Returns:
        True if the option was successfully modified, False otherwise.

    Raises:
        ValueError: If the value of the option is not a boolean."""
    import re

    if config.has_option(section, option):
        print(option, '=',
              ANSI_DEFAULT + config[section][option] + ANSI_RESET)
        try:
            boolean_value = config[section].getboolean(option)
            answer = tidy_answer(['toggle', 'default', 'quit'])
        except ValueError:
            answer = tidy_answer(['modify', 'default', 'quit'])

        if answer == 'modify':
            if re.sub('\s+', '', config[section][option])[0:2] == '[(':
                modify_tuple_option(config, section, option, config_file,
                                    keys=keys)
            else:
                config[section][option] = modify_data(
                    prompts.get('value', 'value'),
                    data=config[section][option])
        elif answer == 'toggle':
            config[section][option] = str(not boolean_value)
        elif answer == 'default':
            config.remove_option(section, option)
        elif answer == 'quit':
            return answer

        write_config(config, config_file)
        return True
    else:
        print(option, 'option does not exist')
        return False

def modify_tuple_option(config, section, option, config_file, prompts={},
                        keys={}):
    """Modify a tuple option in a configuration file.

    Args:
        config (ConfigParser): configuration object
        section (str): section name in the configuration file
        option (str): option name in the configuration file
        config_file (str): path to the configuration file
        prompts (dict): dictionary of prompts to display to the user
        keys (dict): dictionary of keys to use for the tuple

    Returns:
        True if the tuple was modified successfully, False otherwise

    Raises:
        None"""
    created = False
    if not config.has_section(section):
        config[section] = {}
    if not config.has_option(section, option):
        created = True
        config[section][option] = '[]'

    tuples = modify_tuples(ast.literal_eval(config[section][option]),
                           created, prompts=prompts, keys=keys)
    if tuples:
        config[section][option] = str(tuples)
        write_config(config, config_file)
        return True
    else:
        delete_option(config, section, option, config_file)
        return False

def modify_tuples(tuples, created, level=0, prompts={}, keys={}):
    """Modifies a list of tuples.

    Args:
        tuples: A list of tuples to be modified.
        created: A boolean value indicating whether the list is being
        created or not.
        level: An integer indicating the level of the list.
        prompts: A dictionary containing prompts for different keys.
        keys: A dictionary containing different types of keys.

    Returns:
        The modified list of tuples.

    Raises:
        None."""
    key_prompt = prompts.get('key', 'key')
    value_prompt = prompts.get('value', 'value')
    additional_value_prompt = prompts.get('additional_value',
                                          'additional value')
    end_of_list_prompt = prompts.get('end_of_list', 'end of list')

    boolean_keys = keys.get('boolean', ())
    additional_value_keys = keys.get('additional_value', ())
    no_value_keys = keys.get('no_value', ())
    positioning_keys = keys.get('positioning', ())

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
                answer = tidy_answer(['insert', 'modify', 'delete', 'quit'],
                                     level=level)
            else:
                print('    ' * level
                      + ANSI_ANNOTATION + end_of_list_prompt + ANSI_RESET)
                answer = tidy_answer(['insert', 'quit'], level=level)

        if answer == 'insert':
            key = modify_data(key_prompt, level=level)
            if any(k == key for k in boolean_keys):
                value = modify_data(value_prompt, level=level)
                level += 1
                additional_value = modify_tuples([], True, level=level,
                                                 prompts=prompts, keys=keys)
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
                value = configure_position(answer)
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

            key = modify_data(key_prompt, level=level, data=key)
            if any(k == key for k in boolean_keys):
                value = modify_data(value_prompt, level=level, data=value)
                level += 1
                additional_value = modify_tuples(additional_value, created,
                                                 level=level, prompts=prompts,
                                                 keys=keys)
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
                value = configure_position(answer, value)
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

def modify_data(prompt, level=0, data=''):
    """Modify data.

    Args:
        prompt (str): The prompt to display to the user.
        level (int, optional): The level of indentation. Defaults to 0.
        data (str, optional): The data to modify. Defaults to ''.

    Returns:
        str: The modified data.

    Raises:
        No specific exceptions are raised."""
    if data:
        data = input('    ' * level + prompt + ' '
                     + ANSI_DEFAULT + data + ANSI_RESET + ': ').strip() or data
    else:
        data = input('    ' * level + prompt + ': ').strip()
    return data

def tidy_answer(answers, level=0):
    """Tidy up user input by highlighting the first letter of each word
    and prompting the user for an answer.

    Args:
        answers: A list of possible answers
        level: The indentation level for the prompt (default 0)

    Returns:
        The user's answer as a string, or an empty string if the answer
        does not match any of the possible answers."""
    initialism = ''

    previous_initialism = ''
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

def configure_position(answer, value=''):
    """Configures the position of the mouse cursor.

    Args:
        answer (str): The answer to the prompt. Can be 'insert' or
        'modify'.
        value (str): The value to modify. Default is an empty string.

    Returns:
        str: The new value of the position of the mouse cursor.

    Raises:
        None."""
    import time

    import pyautogui
    import win32api

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
    """Delete an option from a configuration file.

    Args:
        config (ConfigParser): The configuration object
        section (str): The section of the option to be deleted
        option (str): The option to be deleted
        config_file (str): The path to the configuration file

    Returns:
        None

    Raises:
        None"""
    if config.has_option(section, option):
        config.remove_option(section, option)
        write_config(config, config_file)

def write_config(config, config_file):
    """Writes a configuration to a file.

    Args:
        config: A configuration object.
        config_file: A file path to write the configuration to.

    Returns:
        None

    Raises:
        IOError: If the file cannot be opened or written to."""
    with open(config_file, 'w', encoding='utf-8') as f:
        config.write(f)

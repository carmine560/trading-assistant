import ast
import os
import sys

INDENT = '    '
ANSI_DEFAULT = '\033[32m'
ANSI_ANNOTATION = '\033[33m'
ANSI_HIGHLIGHT = '\033[4m'
ANSI_RESET = '\033[m'

if sys.platform == 'win32':
    os.system('color')

def list_section(config, section):
    """List all options in a section of a configuration file.

    Args:
        config: ConfigParser object representing the configuration file
        section: Name of the section to list options from

    Returns:
        True if the section exists and has options, False otherwise."""
    if config.has_section(section):
        for option in config[section]:
            print(option)
        return True
    else:
        print(section, 'section does not exist')
        return False

# TODO: insert
def modify_section(config, section, config_file, backup_function=None,
                   backup_parameters=None, keys={}):
    """Modifies a section of a configuration file.

    Args:
        config : configparser object representing the configuration file
        section : name of the section to modify
        config_file : path to the configuration file
        backup_function : function to backup the configuration file
        backup_parameters : parameters to pass to the backup function
        keys : dictionary of keys to modify in the section

    Returns:
        True if the section was modified successfully, False otherwise

    Raises:
        None"""
    if backup_function:
        backup_function(config_file, **backup_parameters)

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

def modify_option(config, section, option, config_file, backup_function=None,
                  backup_parameters=None, prompts={}, keys={}):
    """Modify an option in a configuration file.

    Args:
        config (ConfigParser): configuration object
        section (str): section name in the configuration file
        option (str): option name in the configuration file
        config_file (str): path to the configuration file
        backup_function (function): function to backup the configuration
        file
        backup_parameters (dict): parameters to pass to the backup
        function
        prompts (dict): dictionary of prompts to display to the user
        keys (dict): dictionary of keys to use for modifying the data

    Returns:
        True if the option was modified, False otherwise

    Raises:
        ValueError: If the option value is not a boolean value.
        NotImplementedError: If the animal is silent."""
    import re

    if backup_function:
        backup_function(config_file, **backup_parameters)

    if config.has_option(section, option):
        print(option, '=', ANSI_DEFAULT + config[section][option] + ANSI_RESET)
        try:
            boolean_value = config[section].getboolean(option)
            answer = tidy_answer(['toggle', 'default', 'quit'])
        except ValueError:
            answer = tidy_answer(['modify', 'default', 'quit'])

        if answer == 'modify':
            if re.sub('\s+', '', config[section][option])[:2] == '[(':
                modify_tuple_list(config, section, option, config_file,
                                  keys=keys)
            elif re.sub('\s+', '', config[section][option])[:1] == '(':
                config[section][option] = modify_tuple(config[section][option],
                                                       False, level=1)
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

def modify_tuple_list(config, section, option, config_file,
                      backup_function=None, backup_parameters=None, prompts={},
                      keys={}):
    """Modify a list of tuples in a configuration file.

    Args:
        config : ConfigParser object
        section : section of the configuration file
        option : option in the section
        config_file : path to the configuration file
        backup_function : function to backup the configuration file
        backup_parameters : parameters for the backup function
        prompts : dictionary of prompts for user input
        keys : dictionary of keys for user input

    Returns:
        True if the list of tuples was modified, False otherwise

    Raises:
        ValueError: If the option is not a list of tuples
        IOError: If the configuration file cannot be written to
    """
    if backup_function:
        backup_function(config_file, **backup_parameters)

    is_created = False
    if not config.has_section(section):
        config[section] = {}
    if not config.has_option(section, option):
        is_created = True
        config[section][option] = '[]'

    tuples = modify_tuples(ast.literal_eval(config[section][option]),
                           is_created, prompts=prompts, keys=keys)
    if tuples:
        config[section][option] = str(tuples)
        write_config(config, config_file)
        return True
    else:
        delete_option(config, section, option, config_file)
        return False

def modify_tuples(tuples, is_created, level=0, prompts={}, keys={}):
    """Modify tuples.

    Args:
        tuples: A list of tuples to be modified.
        is_created: A boolean indicating whether the tuples are being
        created or modified.
        level: An integer indicating the level of indentation.
        prompts: A dictionary containing prompts for different keys.
        keys: A dictionary containing keys for different types of
        values.

    Returns:
        The modified list of tuples."""
    key_prompt = prompts.get('key', 'key')
    value_prompt = prompts.get('value', 'value')
    additional_value_prompt = prompts.get('additional_value',
                                          'additional value')
    end_of_list_prompt = prompts.get('end_of_list', 'end of list')

    boolean_keys = keys.get('boolean', ())
    additional_value_keys = keys.get('additional_value', ())
    no_value_keys = keys.get('no_value', ())
    positioning_keys = keys.get('positioning', ())

    index = 0
    while index <= len(tuples):
        if is_created or index == len(tuples):
            print(INDENT * level
                  + ANSI_ANNOTATION + end_of_list_prompt + ANSI_RESET)
            answer = tidy_answer(['insert', 'quit'], level=level)
        else:
            print(INDENT * level
                  + ANSI_DEFAULT + str(tuples[index]) + ANSI_RESET)
            answer = tidy_answer(['insert', 'modify', 'delete', 'quit'],
                                 level=level)

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

            key = modify_data(key_prompt, level=level, data=key)
            if any(k == key for k in boolean_keys):
                value = modify_data(value_prompt, level=level, data=value)
                level += 1
                additional_value = modify_tuples(additional_value, is_created,
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

def modify_tuple(data, is_created, level=0, prompts={}):
    """Modify a tuple.

    Args:
        data (str): A string representation of the tuple to be modified.
        is_created (bool): A flag indicating whether the tuple is being
        created or modified.
        level (int): The level of indentation for printing prompts.
        prompts (dict): A dictionary containing prompts for user
        input. The keys are 'value' for the prompt for entering a new
        value, and 'end_of_list' for the prompt for the end of the list.

    Returns:
        str: A string representation of the modified tuple."""
    data = list(ast.literal_eval(data))
    value_prompt = prompts.get('value', 'value')
    end_of_list_prompt = prompts.get('end_of_list', 'end of tuple')

    index = 0
    while index <= len(data):
        if is_created or index == len(data):
            print(INDENT * level
                  + ANSI_ANNOTATION + end_of_list_prompt + ANSI_RESET)
            answer = tidy_answer(['insert', 'quit'], level=level)
        else:
            print(INDENT * level
                  + ANSI_DEFAULT + str(data[index]) + ANSI_RESET)
            answer = tidy_answer(['insert', 'modify', 'delete', 'quit'],
                                 level=level)

        if answer == 'insert':
            value = modify_data(value_prompt, level=level)
            if value:
                data.insert(index, value)
        elif answer == 'modify':
            data[index] = modify_data(value_prompt, level=level,
                                      data=data[index])
        elif answer == 'delete':
            del data[index]
            index -= 1
        elif answer == 'quit':
            index = len(data)

        index += 1

    return str(tuple(data))

def modify_data(prompt, level=0, data=''):
    """A function to modify data.

    Args:
        prompt : the prompt to display to the user
        level : the indentation level of the prompt (default 0)
        data : the data to modify (default '')

    Returns:
        The modified data

    Raises:
        ImportError: If prompt_toolkit is not installed"""
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.shortcuts import CompleteStyle

    if data:
        completer = WordCompleter([data])
        data = pt_prompt(INDENT * level + prompt + ': ', completer=completer,
                         complete_style=CompleteStyle.READLINE_LIKE).strip() \
                         or data
    else:
        data = input(INDENT * level + prompt + ': ').strip()
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

    answer = input(INDENT * level + prompt).strip().lower()
    if answer:
        if not answer[0] in initialism:
            answer = ''
        else:
            for index in range(len(initialism)):
                if initialism[index] == answer[0]:
                    answer = answers[index]
    return answer

def configure_position(answer, level=0, value=''):
    """Configures the position of an input.

    Args:
        answer (str): The answer to the input prompt.
        level (int): The level of indentation.
        value (str): The value of the input prompt.

    Returns:
        The configured position.

    Raises:
        ImportError: If the prompt_toolkit module is not installed.
        NotImplementedError: If silent animals are not supported."""
    import time

    from prompt_toolkit import ANSI
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.shortcuts import CompleteStyle
    import pyautogui
    import win32api

    if answer == 'modify' and value:
        completer = WordCompleter([value])
        value = pt_prompt(
            ANSI(INDENT * level
                 + 'input/' + ANSI_HIGHLIGHT + 'c' + ANSI_RESET + + 'lick: '),
            completer=completer,
            complete_style=CompleteStyle.READLINE_LIKE).strip() or value
    else:
        value = input(
            INDENT * level
            + 'input/' + ANSI_HIGHLIGHT + 'c' + ANSI_RESET + 'lick: ').strip()

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

def delete_option(config, section, option, config_file, backup_function=None,
                  backup_parameters=None):
    """Deletes an option from a configuration file.

    Args:
        config: ConfigParser object representing the configuration file
        section: Section of the configuration file where the option is
        located
        option: Option to be deleted
        config_file: Path to the configuration file
        backup_function: Function to backup the configuration file
        before deleting the option
        backup_parameters: Parameters to be passed to the backup
        function

    Returns:
        True if the option was deleted successfully, False otherwise

    Raises:
        None"""
    if backup_function:
        backup_function(config_file, **backup_parameters)

    if config.has_option(section, option):
        config.remove_option(section, option)
        write_config(config, config_file)
        return True
    else:
        print(option, 'option does not exist')
        return False

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

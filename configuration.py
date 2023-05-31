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

def modify_section(config, section, config_file, backup_function=None,
                   backup_parameters=None, is_inserting=False,
                   value_format='string', prompts={}, categorized_keys={},
                   tuple_info={}):
    """Modifies a section in a configuration file.

    Args:
        config (ConfigParser): The configuration object
        section (str): The section to modify
        config_file (str): The path to the configuration file
        backup_function (function, optional): A function to backup the
        configuration file. Defaults to None.
        backup_parameters (dict, optional): Parameters to pass to the
        backup function. Defaults to None.
        is_inserting (bool, optional): Whether to insert a new
        option. Defaults to False.
        value_format (str, optional): The format of the value to
        modify. Defaults to 'string'.
        prompts (dict, optional): Prompts to display to the
        user. Defaults to {}.
        categorized_keys (dict, optional): Categorized keys. Defaults to
        {}.
        tuple_info (dict, optional): Information about tuples. Defaults
        to {}.

    Returns:
        bool: True if the section was modified successfully, False
        otherwise.

    Raises:
        NotImplementedError: If the animal is silent."""
    if backup_function:
        backup_function(config_file, **backup_parameters)

    if config.has_section(section):
        for option in config[section]:
            result = modify_option(config, section, option, config_file,
                                   categorized_keys=categorized_keys,
                                   tuple_info=tuple_info)
            if result == 'quit' or result == False:
                return result

        if is_inserting:
            end_of_list_prompt = prompts.get('end_of_list', 'end of section')
            is_inserted = False
            while is_inserting:
                print(ANSI_ANNOTATION + end_of_list_prompt + ANSI_RESET)
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
                write_config(config, config_file)

        return True
    else:
        print(section, 'section does not exist')
        return False

def modify_option(config, section, option, config_file, backup_function=None,
                  backup_parameters=None, prompts={}, categorized_keys={},
                  tuple_info={}):
    """Modify an option in a configuration file.

    Args:
        config: A configparser object representing the configuration
        file.
        section: The section of the configuration file that contains the
        option.
        option: The option to modify.
        config_file: The path to the configuration file.
        backup_function: A function to backup the configuration file
        before modification. Default is None.
        backup_parameters: A dictionary of parameters to pass to the
        backup function. Default is None.
        prompts: A dictionary of prompts to display to the user. Default
        is an empty dictionary.
        categorized_keys: A dictionary of categorized keys. Default is
        an empty dictionary.
        tuple_info: A dictionary of information about tuples. Default is
        an empty dictionary.

    Returns:
        True if the option was modified, False if the option does not
        exist.

    Raises:
        ValueError: If the configuration file is not valid.
        NotImplementedError: If silent animals are not supported."""
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
                                  categorized_keys=categorized_keys)
            elif re.sub('\s+', '', config[section][option])[:1] == '(':
                config[section][option] = modify_tuple(config[section][option],
                                                       False, level=1,
                                                       tuple_info=tuple_info)
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
                      categorized_keys={}):
    """Modify a list of tuples in a configuration file.

    Args:
        config (ConfigParser): configuration object
        section (str): section name in the configuration file
        option (str): option name in the section
        config_file (str): path to the configuration file
        backup_function (function, optional): function to backup the
        configuration file
        backup_parameters (dict, optional): parameters to pass to the
        backup function
        prompts (dict, optional): dictionary of prompts to display to
        the user
        categorized_keys (dict, optional): dictionary of categorized
        keys

    Returns:
        bool: True if the list of tuples was modified, False otherwise

    Raises:
        ValueError: If the section or option does not exist in the
        configuration file
        NotImplementedError: If the animal is silent"""
    if backup_function:
        backup_function(config_file, **backup_parameters)

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
        write_config(config, config_file)
        return True
    else:
        delete_option(config, section, option, config_file)
        return False

def modify_tuples(tuples, is_created, level=0, prompts={},
                  categorized_keys={}):
    """Modify tuples of data.

    Args:
        tuples: A list of tuples to be modified.
        is_created: A boolean indicating whether the tuples are being
        created or modified.
        level: An integer indicating the level of indentation for
        printing.
        prompts: A dictionary containing prompts for user input.
        categorized_keys: A dictionary containing categorized keys.

    Returns:
        The modified list of tuples.

    Raises:
        No specific exceptions are raised by this function."""
    key_prompt = prompts.get('key', 'key')
    value_prompt = prompts.get('value', 'value')
    additional_value_prompt = prompts.get('additional_value',
                                          'additional value')
    end_of_list_prompt = prompts.get('end_of_list', 'end of list')

    all_keys = categorized_keys.get('all_keys', [])
    boolean_keys = categorized_keys.get('boolean_keys', ())
    additional_value_keys = categorized_keys.get('additional_value_keys', ())
    no_value_keys = categorized_keys.get('no_value_keys', ())
    positioning_keys = categorized_keys.get('positioning_keys', ())

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
            key = modify_data(key_prompt, level=level, all_data=all_keys)
            if any(k == key for k in boolean_keys):
                value = modify_data(value_prompt, level=level,
                                    all_data=['True', 'False'])
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
            if any(k == key for k in boolean_keys):
                value = modify_data(value_prompt, level=level,
                                    all_data=['True', 'False'])
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

def modify_tuple(data, is_created, level=0, prompts={}, tuple_info={}):
    """Modify a tuple.

    Args:
        data: a string representation of the tuple to be modified
        is_created: a boolean indicating whether the tuple is being
        created or modified
        level: an integer indicating the level of indentation for the
        output
        prompts: a dictionary containing prompts for user input
        tuple_info: a dictionary containing information about the tuple

    Returns:
        A string representation of the modified tuple."""
    data = list(ast.literal_eval(data))
    value_prompt = prompts.get('value', 'value')
    end_of_list_prompt = prompts.get('end_of_list', 'end of tuple')
    element_index = tuple_info.get('element_index')
    possible_values = tuple_info.get('possible_values')

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

def modify_data(prompt, level=0, data='', all_data=[]):
    """Modify data based on user input.

    Args:
        prompt (str): The prompt to display to the user.
        level (int): The indentation level of the prompt.
        data (str): The default value to use if the user does not
        provide input.
        all_data (list): A list of all possible values for the user to
        choose from.

    Returns:
        The modified data.

    Raises:
        ImportError: If prompt_toolkit is not installed."""
    has_prompt_toolkit = True
    try:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.shortcuts import CompleteStyle
    except ImportError:
        has_prompt_toolkit = False

    completer = None
    if has_prompt_toolkit:
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
                     + ANSI_DEFAULT + data + ANSI_RESET + ': ').strip() or data
    else:
        data = input(prompt_prefix + ': ').strip()
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

def configure_position(answer, level=0, value=''):
    """Configure the position of an object.

    Args:
        answer (str): The answer to the prompt.
        level (int, optional): The level of indentation. Defaults to 0.
        value (str, optional): The value of the prompt. Defaults to ''.

    Returns:
        str: The coordinates of the object or the value of the prompt.

    Raises:
        ImportError: If prompt_toolkit is not installed."""
    import time

    import pyautogui
    import win32api

    has_prompt_toolkit = True
    try:
        from prompt_toolkit import ANSI
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.shortcuts import CompleteStyle
    except ImportError:
        has_prompt_toolkit = False

    prompt_prefix = f'{INDENT * level}input/{ANSI_HIGHLIGHT}c{ANSI_RESET}lick'
    if answer == 'modify' and value:
        if has_prompt_toolkit:
            completer = WordCompleter([value])
            value = pt_prompt(
                ANSI(prompt_prefix + ': '), completer=completer,
                complete_style=CompleteStyle.READLINE_LIKE).strip() or value
        else:
            value = input(prompt_prefix + ' '
                          + ANSI_DEFAULT + value + ANSI_RESET + ': ').strip() \
                          or value
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

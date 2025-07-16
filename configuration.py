"""Manage configurations and perform auto-completion."""

from io import StringIO
import ast
import configparser
import os
import sys
import time

from prompt_toolkit import ANSI
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion

try:
    import gnupg

    GNUPG_IMPORT_ERROR = None
except ModuleNotFoundError as e:
    GNUPG_IMPORT_ERROR = e

try:
    import pyautogui
    import win32api

    GUI_IMPORT_ERROR = None
except ModuleNotFoundError as e:
    GUI_IMPORT_ERROR = e

import file_utilities

ANSI_BOLD = "\033[1m"
ANSI_CURRENT = "\033[32m"
ANSI_ERROR = "\033[31m"
ANSI_IDENTIFIER = "\033[36m"
ANSI_RESET = "\033[m"
ANSI_UNDERLINE = "\033[4m"
ANSI_WARNING = "\033[33m"
INDENT = "    "

if sys.platform == "win32":
    os.system("color")


class ConfigError(Exception):
    """Represent a custom exception for configuration-related issues."""

    pass


class CustomWordCompleter(Completer):
    """Provide custom word completion by extending the Completer class."""

    def __init__(self, words, ignore_case=False):
        """Initialize with words for auto-completion."""
        self.words = words
        self.ignore_case = ignore_case

    def get_completions(self, document, complete_event):
        """Yield completions for the current word before the cursor."""
        word_before_cursor = document.current_line_before_cursor.lstrip()
        for word in self.words:
            if self.ignore_case:
                if word.lower().startswith(word_before_cursor.lower()):
                    yield Completion(word, -len(word_before_cursor))
            else:
                if word.startswith(word_before_cursor):
                    yield Completion(word, -len(word_before_cursor))


def read_config(config, config_path, is_encrypted=False):
    """Read config from a file, decrypt if is_encrypted is True."""
    if is_encrypted:
        encrypted_config_path = f"{config_path}.gpg"
        if os.path.isfile(encrypted_config_path):
            if GNUPG_IMPORT_ERROR:
                raise RuntimeError(GNUPG_IMPORT_ERROR)

            with open(encrypted_config_path, "rb") as f:
                encrypted_config = f.read()

            gpg = gnupg.GPG()
            decrypted_config = gpg.decrypt(encrypted_config)
            config.read_string(decrypted_config.data.decode())
    else:
        config.read(config_path, encoding="utf-8")


def write_config(config, config_path, is_encrypted=False):
    """Write config to a file, encrypt if is_encrypted is True."""
    if is_encrypted:
        if GNUPG_IMPORT_ERROR:
            raise RuntimeError(GNUPG_IMPORT_ERROR)

        config_string = StringIO()
        config.write(config_string)
        gpg = gnupg.GPG()
        gpg.encoding = "utf-8"
        fingerprint = ""
        if config.has_option("General", "fingerprint"):
            fingerprint = config["General"]["fingerprint"]
        if not fingerprint:
            fingerprint = gpg.list_keys()[0]["fingerprint"]

        encrypted_config = gpg.encrypt(
            config_string.getvalue(), fingerprint, armor=False
        )
        with open(f"{config_path}.gpg", "wb") as f:
            f.write(encrypted_config.data)
    else:
        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)


def check_config_changes(
    default_config,
    config_path,
    excluded_sections=(),
    user_option_ignored_sections=(),
    backup_parameters=None,
    is_encrypted=False,
):
    """Compare default and user configurations."""

    def truncate_string(string):
        """Truncate a string to a maximum length."""
        max_length = 256
        if len(string) > max_length:
            string = string[:max_length] + "..."
        return string

    if backup_parameters:
        file_utilities.backup_file(config_path, **backup_parameters)

    section_index = 0
    section_indices = []
    sections = []
    for section in default_config.sections():
        if section not in excluded_sections and default_config.options(
            section
        ):
            sections.append(section)

    user_config = configparser.ConfigParser(interpolation=None)
    read_config(user_config, config_path, is_encrypted=is_encrypted)

    while section_index < len(sections):
        section = sections[section_index]
        answer = ""

        if not user_config.has_section(section):
            user_config.add_section(section)

        option_index = 0
        option_indices = []
        options = default_config.options(section)
        for option in user_config[section]:
            if (
                section not in user_option_ignored_sections
                and option not in default_config[section]
            ):
                options.append(option)

        while option_index < len(options):
            option = options[option_index]
            default_value = default_config[section].get(option)
            user_value = user_config[section].get(option)

            if user_value is not None and default_value != user_value:
                if not option_indices:
                    print(f"[{ANSI_BOLD}{section}{ANSI_RESET}]")

                if default_config.has_option(section, option):
                    tidied_default_value = (
                        truncate_string(default_value)
                        if default_value
                        else f"{ANSI_WARNING}(empty){ANSI_RESET}"
                    )
                else:
                    tidied_default_value = (
                        f"{ANSI_WARNING}(not exist){ANSI_RESET}"
                    )

                tidied_user_value = (
                    f"{ANSI_CURRENT}{truncate_string(user_value)}{ANSI_RESET}"
                    if user_value
                    else f"{ANSI_WARNING}(empty){ANSI_RESET}"
                )

                print(
                    f"{ANSI_IDENTIFIER}{option}{ANSI_RESET}: "
                    f"{tidied_default_value} → {tidied_user_value}"
                )

                answers = ["default", "back", "quit"]
                if not section_indices and not option_indices:
                    answers.remove("back")

                answer = tidy_answer(answers)

                if answer == "default":
                    user_config.remove_option(section, option)
                    write_config(
                        user_config, config_path, is_encrypted=is_encrypted
                    )
                elif answer == "back":
                    if option_indices:
                        option_index = option_indices.pop()
                        continue
                    break
                elif answer == "quit":
                    return

                option_indices.append(option_index)

            option_index += 1

        if answer == "back":
            section_index = section_indices.pop()
            continue
        if option_indices:
            section_indices.append(section_index)

        section_index += 1


def ensure_section_exists(config, section):
    """Ensure a section is defined, raise ConfigError if not."""
    if not config.has_section(section):
        raise ConfigError(f"The '{section}' section is undefined.")


def list_section(config, section):
    """Retrieve all options from a specified section in a configuration."""
    options = []
    if config.has_section(section):
        for option in config[section]:
            options.append(option)
        return options

    print(f"The {section} section does not exist.")
    return False


def modify_section(
    config,
    section,
    config_path,
    backup_parameters=None,
    option=None,
    can_back=True,
    can_insert_delete=False,
    prompts=None,
    items=None,
    all_values=None,
    limits=(),
    is_encrypted=False,
):
    """Modify a section of a configuration based on user input."""
    if backup_parameters:
        file_utilities.backup_file(config_path, **backup_parameters)

    if config.has_section(section):
        index = 0
        options = [option] if option else config.options(section)
        length = len(options) + 1 if can_insert_delete else len(options)
        if prompts is None:
            prompts = {}

        while index < length:
            if index < len(options):
                option = options[index]
                current_can_back = False if index == 0 else can_back
                result = modify_option(
                    config,
                    section,
                    option,
                    config_path,
                    can_back=current_can_back,
                    can_insert_delete=can_insert_delete,
                    prompts=prompts,
                    items=items,
                    all_values=all_values,
                    limits=limits,
                    is_encrypted=is_encrypted,
                )

                if result == "back":
                    index -= 1
                    continue
                elif result == "quit":
                    return result
            else:
                print(
                    f"{ANSI_WARNING}"
                    f"{prompts.get('end_of_list', 'end of section')}"
                    f"{ANSI_RESET}"
                )
                answer = tidy_answer(["insert", "back", "quit"])

                if answer == "insert":
                    option = modify_value(prompts.get("key", "option"))
                    if all_values:
                        config[section][option] = str(
                            modify_tuple(
                                (),
                                level=1,
                                prompts=prompts,
                                all_values=all_values,
                            )
                        )
                        if config[section][option] != "()":
                            write_config(
                                config, config_path, is_encrypted=is_encrypted
                            )
                            options.append(option)
                            length += 1
                    else:
                        config[section][option] = modify_value("value")
                        if config[section][option]:
                            write_config(
                                config, config_path, is_encrypted=is_encrypted
                            )
                            options.append(option)
                            length += 1
                elif answer == "back":
                    index -= 1
                    continue
                elif answer in {"", "quit"}:
                    break

            index += 1

        return True

    print(f"The {section} section does not exist.")
    return False


def modify_option(
    config,
    section,
    option,
    config_path,
    backup_parameters=None,
    can_back=False,
    can_insert_delete=False,
    initial_value=None,
    prompts=None,
    items=None,
    all_values=None,
    limits=(),
    is_encrypted=False,
):
    """Modify an option in a section of a configuration file."""
    if backup_parameters:
        file_utilities.backup_file(config_path, **backup_parameters)
    if initial_value:
        config[section].setdefault(option, initial_value)
    if prompts is None:
        prompts = {}

    if config.has_option(section, option):
        print(
            f"{ANSI_IDENTIFIER}{option}{ANSI_RESET} = "
            f"{ANSI_CURRENT}{config[section][option]}{ANSI_RESET}"
        )
        try:
            boolean_value = get_strict_boolean(config, section, option)
            answers = ["modify", "toggle", "default", "quit"]
        except ValueError:
            answers = ["modify", "default", "quit"]
        if can_back:
            answers.insert(answers.index("quit"), "back")
        if can_insert_delete:
            answers[answers.index("default")] = "delete"

        answer = tidy_answer(answers)

        if answer == "modify":
            evaluated_value = evaluate_value(config[section][option])
            if isinstance(evaluated_value, dict):
                config[section][option] = str(
                    modify_dictionary(
                        evaluated_value,
                        level=1,
                        prompts=prompts,
                        all_values=all_values,
                    )
                )
            elif isinstance(evaluated_value, tuple) and all(
                isinstance(i, str) for i in evaluated_value
            ):
                config[section][option] = str(
                    modify_tuple(
                        evaluated_value,
                        level=1,
                        prompts=prompts,
                        all_values=all_values,
                    )
                )
            elif isinstance(evaluated_value, list) and all(
                isinstance(item, tuple) for item in evaluated_value
            ):
                if evaluated_value == [()]:
                    evaluated_value = []

                tuple_list = modify_tuple_list(
                    evaluated_value, prompts=prompts, items=items
                )
                if tuple_list:
                    config[section][option] = str(tuple_list)
                else:
                    delete_option(
                        config,
                        section,
                        option,
                        config_path,
                        is_encrypted=is_encrypted,
                    )
                    return False
            else:
                config[section][option] = modify_value(
                    prompts.get("value", "value"),
                    value=config[section][option],
                    all_values=all_values,
                    limits=limits,
                )
        elif answer == "toggle":
            config[section][option] = str(not boolean_value)
        elif answer == "empty":  # TODO: Remove empty.
            config[section][option] = ""
        elif answer in {"default", "delete"}:
            delete_option(
                config, section, option, config_path, is_encrypted=is_encrypted
            )
            return False
        elif answer == "back":
            return answer
        elif answer in {"", "quit"}:
            if config[section][option] == initial_value:
                delete_option(
                    config,
                    section,
                    option,
                    config_path,
                    is_encrypted=is_encrypted,
                )
                return False
            return answer

        write_config(config, config_path, is_encrypted=is_encrypted)
        return True

    print(f"The {option} option does not exist.")
    return False


def delete_option(
    config,
    section,
    option,
    config_path,
    backup_parameters=None,
    is_encrypted=False,
):
    """Delete an option from a section in a configuration file."""
    if backup_parameters:
        file_utilities.backup_file(config_path, **backup_parameters)

    if config.has_option(section, option):
        config.remove_option(section, option)
        write_config(config, config_path, is_encrypted=is_encrypted)
        return True

    print(f"The {option} option does not exist.")
    return False


def modify_dictionary(dictionary, level=0, prompts=None, all_values=None):
    """Iterate over a dictionary and modify its values based on user input."""
    index = 0
    keys = list(dictionary.keys())
    value_prompt = prompts.get("value", "value")

    while index < len(keys):
        key = keys[index]
        value = dictionary[key]
        print(
            f"{INDENT * level}{ANSI_IDENTIFIER}{key}{ANSI_RESET}: "
            f"{ANSI_CURRENT}{value}{ANSI_RESET}"
        )
        answers = ["modify", "empty", "back", "quit"]
        if index == 0:
            answers.remove("back")

        answer = tidy_answer(answers, level=level)

        if answer == "modify":
            dictionary[key] = modify_value(
                value_prompt, level=level, value=value, all_values=all_values
            )
        elif answer == "empty":
            dictionary[key] = ""
        elif answer == "back":
            index -= 1
            continue
        elif answer == "quit":
            break

        index += 1

    return dictionary


def modify_tuple(tuple_entry, level=0, prompts=None, all_values=None):
    """Modify a tuple based on user prompts and provided values."""
    tuple_entry = list(tuple_entry)
    values_prompt = prompts.get("values", ())

    index = 0
    while index <= len(tuple_entry):
        if index == len(tuple_entry):
            print(
                f"{INDENT * level}"
                f"{ANSI_WARNING}{prompts.get('end_of_list', 'end of tuple')}"
                f"{ANSI_RESET}"
            )
            answers = ["insert", "back", "quit"]
        else:
            print(
                f"{INDENT * level}"
                f"{ANSI_CURRENT}{tuple_entry[index]}{ANSI_RESET}"
            )
            if values_prompt:
                answers = ["modify", "empty", "back", "quit"]
            else:
                answers = ["insert", "modify", "delete", "back", "quit"]
        if index == 0:
            answers.remove("back")

        answer = tidy_answer(answers, level=level)

        if answer in {"insert", "modify"}:
            value = "" if answer == "insert" else tuple_entry[index]
            value_prompt = (
                values_prompt[index]
                if values_prompt[index : index + 1]
                else prompts.get("value", "value")
            )
            if all_values and len(all_values) == 1:
                value = modify_value(
                    value_prompt,
                    level=level,
                    value=value,
                    all_values=all_values[0],
                )
            elif all_values and all_values[index : index + 1]:
                value = modify_value(
                    value_prompt,
                    level=level,
                    value=value,
                    all_values=all_values[index],
                )
            else:
                value = modify_value(value_prompt, level=level, value=value)
            if answer == "insert":
                tuple_entry.insert(index, value)
            else:
                tuple_entry[index] = value
        elif answer == "empty":
            tuple_entry[index] = ""
        elif answer == "delete":
            del tuple_entry[index]
            index -= 1
        elif answer == "back":
            index -= 1
            continue
        elif answer == "quit":
            break

        index += 1
        if values_prompt and index == len(values_prompt):
            break

    return tuple(tuple_entry)


def modify_tuple_list(tuple_list, level=0, prompts=None, items=None):
    """Modify a list of tuples based on user prompts and provided items."""
    if not isinstance(tuple_list, list):
        tuple_list = []
    if items is None:
        items = {}

    value_prompt = prompts.get("value", "value")
    additional_value_prompt = prompts.get(
        "additional_value", "additional value"
    )

    index = 0
    while index <= len(tuple_list):
        if index == len(tuple_list):
            print(
                f"{INDENT * level}"
                f"{ANSI_WARNING}{prompts.get('end_of_list', 'end of list')}"
                f"{ANSI_RESET}"
            )
            answers = ["insert", "back", "quit"]
        else:
            print(
                f"{INDENT * level}"
                f"{ANSI_CURRENT}{tuple_list[index]}{ANSI_RESET}"
            )
            answers = ["insert", "modify", "delete", "back", "quit"]
        if index == 0:
            answers.remove("back")

        answer = tidy_answer(answers, level=level)

        if answer in {"insert", "modify"}:
            if answer == "insert":
                key = value = additional_value = ""
            else:
                key, value, additional_value = (tuple_list[index] + ("", ""))[
                    :3
                ]

            key = modify_value(
                prompts.get("key", "key"),
                level=level,
                value=key,
                all_values=items.get("all_keys"),
            )
            if key in items.get("preset_value_keys", set()):
                preset_values = items.get("preset_values")
            elif key in items.get("boolean_value_keys", set()):
                preset_values = {"True", "False"}
            else:
                preset_values = None
            if key in items.get("no_value_keys", set()):
                tuple_entry = (key,)
            elif key in items.get("optional_value_keys", set()):
                value = modify_value(
                    value_prompt,
                    level=level,
                    value=value,
                    all_values=("None",),
                )
                tuple_entry = (
                    (key,) if value.lower() in {"", "none"} else (key, value)
                )
            elif key in items.get("additional_value_keys", set()):
                value = modify_value(value_prompt, level=level, value=value)
                additional_value = modify_value(
                    additional_value_prompt,
                    level=level,
                    value=additional_value,
                )
                tuple_entry = (key, value, additional_value)
            elif key in items.get("optional_additional_value_keys", set()):
                value = modify_value(value_prompt, level=level, value=value)
                additional_value = modify_value(
                    additional_value_prompt,
                    level=level,
                    value=additional_value,
                    all_values=("None",),
                )
                tuple_entry = (
                    (key, value)
                    if additional_value.lower() in {"", "none"}
                    else (key, value, additional_value)
                )
            elif key in items.get("positioning_keys", set()):
                value = configure_position(level=level, value=value)
                tuple_entry = (key, value)
            elif key in items.get("nested_keys", set()):
                value = modify_nested_value(value, level, prompts, items)
                tuple_entry = (key, value)
            elif key in items.get("optional_additional_nested_keys", set()):
                value = modify_value(value_prompt, level=level, value=value)
                additional_value = modify_nested_value(
                    additional_value,
                    level,
                    prompts,
                    items,
                    answers=["build", "call", "none"],
                )
                tuple_entry = (
                    (key, value)
                    if additional_value in {"", None}
                    else (key, value, additional_value)
                )
            elif key in items.get("control_flow_keys", set()):
                value = modify_value(
                    value_prompt,
                    level=level,
                    value=value,
                    all_values=preset_values,
                )
                additional_value = modify_nested_value(
                    additional_value, level, prompts, items
                )
                tuple_entry = (key, value, additional_value)
            else:
                value = modify_value(
                    value_prompt,
                    level=level,
                    value=value,
                    all_values=preset_values,
                )
                tuple_entry = (key, value)
            if answer == "insert":
                tuple_list.insert(index, tuple_entry)
            else:
                tuple_list[index] = tuple_entry
        elif answer == "delete":
            del tuple_list[index]
            index -= 1
        elif answer == "back":
            index -= 1
            continue
        elif answer == "quit":
            break

        index += 1

    return tuple_list


def get_strict_boolean(config, section, option):
    """Retrieve a strict boolean value from a configuration section."""
    value = config.get(section, option)
    if value.lower() not in {"true", "false"}:
        raise ValueError(f"Invalid boolean value for {option} in {section}.")
    return config.getboolean(section, option)


def evaluate_value(value):
    """Evaluate the given value using Python's abstract syntax trees."""
    evaluated_value = None
    try:
        evaluated_value = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        pass
    except (TypeError, MemoryError, RecursionError) as e:
        print(e)
        sys.exit(1)
    return evaluated_value


def tidy_answer(answers, level=0):
    """Tidy up the answer based on user input and initialism."""
    initialism = ""

    previous_initialism = ""
    for word_index, word in enumerate(answers):
        for char_index, _ in enumerate(word):
            if word[char_index].lower() not in initialism:
                mnemonics = word[char_index]
                initialism = initialism + mnemonics.lower()
                break
        if initialism == previous_initialism:
            print("Undetermined mnemonics.")
            sys.exit(1)
        else:
            previous_initialism = initialism
            highlighted_word = word.replace(
                mnemonics, f"{ANSI_UNDERLINE}{mnemonics}{ANSI_RESET}", 1
            )
            if word_index == 0:
                prompt = highlighted_word
            else:
                prompt = f"{prompt}/{highlighted_word}"

    answer = input(f"{INDENT * level}{prompt}: ").strip().lower()
    if answer:
        if answer[0] not in initialism:
            answer = ""
        else:
            for index, _ in enumerate(initialism):
                if initialism[index] == answer[0]:
                    answer = answers[index]
    return answer


def modify_value(prompt, level=0, value="", all_values=None, limits=()):
    """Modify a value based on user input and specified limits."""
    value = prompt_for_input(
        prompt, level=level, value=value, all_values=all_values
    )
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

    return value


def configure_position(level=0, value=""):
    """Configure the position based on user input or mouse click."""
    if GUI_IMPORT_ERROR:
        print(GUI_IMPORT_ERROR)
        return False

    value = prompt_for_input(
        f"coordinates/{ANSI_UNDERLINE}c{ANSI_RESET}lick",
        level=level,
        value=value,
    )
    if value and value[0].lower() == "c":
        previous_key_state = win32api.GetKeyState(0x01)
        coordinates = ""
        print(
            f"{INDENT * level}{ANSI_WARNING}waiting for click...{ANSI_RESET}"
        )
        while True:
            key_state = win32api.GetKeyState(0x01)
            if key_state != previous_key_state:
                if key_state not in [0, 1]:
                    coordinates = ", ".join(map(str, pyautogui.position()))
                    print(f"{INDENT * level}coordinates: {coordinates}")
                    break

            time.sleep(0.001)
        return coordinates

    parts = value.split(",")
    if len(parts) == 2:
        x = parts[0].strip()
        y = parts[1].strip()
        if x.isdigit() and y.isdigit():
            return f"{x}, {y}"

    return configure_position(
        level=level, value=f"{ANSI_RESET}{ANSI_ERROR}{value}"
    )


def prompt_for_input(prompt, level=0, value="", all_values=None):
    """Prompt the user for input and return the entered value."""
    if value:
        prompt_prefix = (
            f"{INDENT * level}{prompt} " f"{ANSI_CURRENT}{value}{ANSI_RESET}: "
        )
    else:
        prompt_prefix = f"{INDENT * level}{prompt}: "

    completer = None
    if all_values:
        completer = CustomWordCompleter(all_values, ignore_case=True)
    elif value:
        completer = CustomWordCompleter([value], ignore_case=True)

    if completer:
        value = (
            pt_prompt(ANSI(prompt_prefix), completer=completer).strip()
            or value
        )
    else:
        value = input(prompt_prefix).strip()
    return value


def modify_nested_value(
    value, level, prompts, items, answers=["build", "call"]
):
    """Handle a value that can be built as a list or called as a preset."""
    nested_answer = tidy_answer(answers, level=level)
    if nested_answer == "build":
        if isinstance(value, str):
            value = None

        level += 1
        value = modify_tuple_list(
            value, level=level, prompts=prompts, items=items
        )
        level -= 1
    elif nested_answer == "call":
        if isinstance(value, list):
            value = None

        value = modify_value(
            prompts.get("preset_additional_value", "preset additional value"),
            level=level,
            value=value,
            all_values=items.get("preset_additional_values"),
        )
    elif nested_answer == "none":
        value = None
    return value

def list_section(config, section):
    if config.has_section(section):
        for key in config[section]:
            print(key)

def modify_option(config, section, option):
    create = False
    if not config.has_section(section):
        config[section] = {}
    if not config.has_option(section, option):
        create = True
        config[section][option] = '[]'
        i = -1
    else:
        i = 0

    commands = eval(config[section][option])
    while i < len(commands):
        if create:
            answer = input('[i]nsert/[q]uit: ').lower()
        else:
            print(commands[i])
            answer = \
                input('[i]nsert/[m]odify/[a]ppend/[d]elete/[q]uit: ').lower()

        if len(answer):
            if answer[0] == 'i' or answer[0] == 'a':
                command = input('command: ')
                if command == 'click' or command == 'move_to':
                    arguments = input('input/[c]lick: ')
                    if len(arguments) and arguments[0].lower() == 'c':
                        arguments = configure_position()
                else:
                    arguments = input('arguments: ')
                if len(arguments) == 0 or arguments == 'None':
                    arguments = None
                if answer[0] == 'a':
                    # FIXME
                    i += 1

                commands.insert(i, (command, arguments))
            elif answer[0] == 'm':
                command = commands[i][0]
                arguments = commands[i][1]
                command = input('command [' + str(command) + '] ') or command
                if command == 'click' or command == 'move_to':
                    arguments = input('input/[c]lick [' + str(arguments)
                                      + '] ') or arguments
                    if len(arguments) and arguments[0].lower() == 'c':
                        arguments = configure_position()
                else:
                    arguments = input('arguments [' + str(arguments) + '] ') \
                        or arguments
                if len(arguments) == 0 or arguments == 'None':
                    arguments = None

                commands[i] = command, arguments
            elif answer[0] == 'd':
                del commands[i]
                i -= 1
            elif answer[0] == 'q':
                i = len(commands)

        i += 1

    if len(commands):
        config[section][option] = str(commands)
        with open(config.path, 'w', encoding='utf-8') as f:
            config.write(f)
        return True
    else:
        delete_option(config, section, option)

def delete_option(config, section, option):
    if config.has_option(section, option):
        config.remove_option(section, option)
        with open(config.path, 'w', encoding='utf-8') as f:
            config.write(f)

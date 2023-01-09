def list_section(config, section):
    if config.has_section(section):
        for key in config[section]:
            print(key)

# FIXME
def modify_tuple_list(config, section, option):
    create = False
    if not config.has_section(section):
        config[section] = {}
    if not config.has_option(section, option):
        create = True
        config[section][option] = '[]'
        i = -1
    else:
        i = 0

    tuple_list = eval(config[section][option])
    while i < len(tuple_list):
        if create:
            answer = input('[i]nsert/[q]uit: ').lower()
        else:
            print(tuple_list[i])
            answer = \
                input('[i]nsert/[m]odify/[a]ppend/[d]elete/[q]uit: ').lower()

        if len(answer):
            if answer[0] == 'i' or answer[0] == 'a':
                key = input('key: ')
                # FIXME
                if key == 'click' or key == 'move_to':
                    value = input('input/[c]lick: ')
                    if len(value) and value[0].lower() == 'c':
                        value = configure_position()
                else:
                    value = input('value: ')
                if len(value) == 0 or value == 'None':
                    value = None
                if answer[0] == 'a':
                    # FIXME
                    i += 1

                tuple_list.insert(i, (key, value))
            elif answer[0] == 'm':
                key = tuple_list[i][0]
                value = tuple_list[i][1]
                key = input('key [' + str(key) + '] ') or key
                # FIXME
                if key == 'click' or key == 'move_to':
                    value = input('input/[c]lick [' + str(value) + '] ') \
                        or value
                    if len(value) and value[0].lower() == 'c':
                        value = configure_position()
                else:
                    value = input('value [' + str(value) + '] ') \
                        or value
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

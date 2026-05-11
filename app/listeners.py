"""Mouse, keyboard, and speech listener startup helpers."""


def start_listeners(
    trade,
    config,
    gui_state,
    base_manager,
    dependencies,
    is_persistent=False,
):
    """Initiate listeners for mouse and keyboard events."""
    mouse = dependencies["mouse"]
    keyboard = dependencies["keyboard"]
    process_utilities = dependencies["process_utilities"]
    threading = dependencies["threading"]

    trade.mouse_listener = mouse.Listener(
        on_click=lambda x, y, button, pressed: trade.on_click(
            x, y, button, pressed, config, gui_state
        )
    )
    trade.mouse_listener.start()

    trade.keyboard_listener = keyboard.Listener(
        on_press=lambda key: trade.on_press(key, config, gui_state),
        on_release=lambda key: trade.on_release(key, gui_state),
    )
    trade.keyboard_listener.start()

    trade.speaking_process = dependencies["start_speaking_process_fn"](
        trade, config
    )

    trade.stop_listeners_event = threading.Event()
    trade.wait_listeners_thread = threading.Thread(
        target=process_utilities.wait_listeners,
        args=(
            trade.stop_listeners_event,
            trade.process,
            trade.mouse_listener,
            trade.keyboard_listener,
            base_manager,
            trade.speech_manager,
            trade.speaking_process,
        ),
        kwargs={
            "indicator_thread": trade.indicator_thread,
            "is_persistent": is_persistent,
        },
    )
    trade.wait_listeners_thread.start()


def start_speaking_process(trade, config, speech_synthesis):
    """Start a speaking process using the configured voice settings."""
    return speech_synthesis.start_speaking_process(
        trade.speech_manager,
        voice_name=config["General"]["voice_name"],
        speech_rate=int(config["General"]["speech_rate"]),
    )

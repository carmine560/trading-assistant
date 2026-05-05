"""Runtime orchestration extracted from the main entrypoint."""


def run(args, trade, config, gui_state, deps):
    """Run the application using the provided runtime dependencies."""
    deps["atexit"].register(persist_config_on_exit, trade, config, deps)

    if args.r:
        deps["save_customer_margin_ratios_fn"](trade, config)

    is_running = deps["process_utilities"].is_running(trade.process)
    base_manager = None
    if args.s or args.l or args.a:
        base_manager = _start_speech_manager(trade, deps)

    if args.a:
        _execute_single_action(
            args,
            trade,
            config,
            gui_state,
            base_manager,
            is_running,
            deps,
        )
    if args.l and is_running:
        deps["start_listeners_fn"](trade, config, gui_state, base_manager)
    if args.s and is_running:
        deps["threading"].Thread(
            target=deps["start_scheduler_fn"],
            args=(trade, config, gui_state, trade.process, base_manager),
        ).start()


def persist_config_on_exit(trade, config, deps):
    """Persist configuration on interpreter shutdown."""
    deps["configuration"].write_config(
        config, trade.config_path, is_encrypted=True
    )


def _start_speech_manager(trade, deps):
    """Create and start the speech manager used by runtime workflows."""
    base_manager_cls = deps["base_manager_cls"]
    speech_synthesis = deps["speech_synthesis"]
    base_manager_cls.register("SpeechManager", speech_synthesis.SpeechManager)
    base_manager = base_manager_cls()
    base_manager.start()
    trade.speech_manager = base_manager.SpeechManager()
    return base_manager


def _execute_single_action(
    args,
    trade,
    config,
    gui_state,
    base_manager,
    is_running,
    deps,
):
    """Execute a single configured action and manage transient listeners."""
    should_start_transient_listeners = not (is_running and args.l)
    if should_start_transient_listeners:
        deps["start_listeners_fn"](
            trade,
            config,
            gui_state,
            base_manager,
            is_persistent=True,
        )

    deps["execute_action_fn"](
        trade,
        config,
        gui_state,
        config[trade.actions_section][args.a[0]],
    )
    if should_start_transient_listeners:
        deps["process_utilities"].stop_listeners(
            trade.mouse_listener,
            trade.keyboard_listener,
            base_manager,
            trade.speech_manager,
            trade.speaking_process,
        )
        trade.stop_listeners_event.set()
        trade.wait_listeners_thread.join()

"""Configuration-building helpers extracted from the entrypoint."""

from datetime import date
import configparser
import os
import re

from core_utilities.errors import ConfigBuildError


def configure(
    trade,
    file_utilities,
    configuration,
    data_utilities,
    securities_code_regex,
    can_interpolate=True,
    can_override=True,
):
    """Set up the configuration for a trade."""
    if can_interpolate:
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
    else:
        config = configparser.ConfigParser(interpolation=None)

    config["General"] = {
        "fingerprint": "",
        "voice_name": "Microsoft Zira Desktop",
        "speech_rate": "2",
        "countdown_seconds_before_candle_close": "30, 10, 5",
    }
    config["Market Holidays"] = {
        "url": "https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html",
        "date_header": "日付",
        "date_format": "%Y/%m/%d",
    }
    config["Market Data"] = {
        "opening_time": "09:00:00",
        "midday_break_time": "11:30:00",
        "reopening_time": "12:30:00",
        "last_order_time": "15:25:00",
        "closing_time": "15:30:00",
        "timezone": "Asia/Tokyo",
        # Double backslashes are required because these values are stored as
        # Python string literals for 'evaluate_value()':
        # 'securities_code_regex' via 'interactive_windows' and user-defined
        # actions, and 'rankings' via user-defined actions.
        "securities_code_regex": securities_code_regex.replace("\\", "\\\\"),
        "rankings": os.path.join(
            os.path.expanduser("~"),
            "Downloads",
            "rankings.csv",
        ).replace("\\", "\\\\"),
    }
    config[trade.geometries_section] = {
        "cash_balance_region": "0, 0, 0, 0, 0",
        "price_limit_region": "0, 0, 0, 0, 0",
    }
    config[trade.actions_section] = {
        "show_hide_indicator": [("show_hide_indicator",)],
        "start_manual_recording": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "is_recording",
                        "False",
                        [
                            ("press_hotkeys", "alt, f9"),
                            ("sleep", "2"),
                            (
                                "is_recording",
                                "False",
                                [("speak_text", "Not recording.")],
                            ),
                        ],
                    )
                ],
            )
        ],
        "create_opening_chapter": [("write_chapter", "Opening", "Pre-market")],
        "create_midday_break_chapter": [("write_chapter", "Midday Break")],
        "create_reopening_chapter": [("write_chapter", "Reopening")],
        "stop_manual_recording": [
            ("is_recording", "True", [("press_hotkeys", "alt, f9")])
        ],
        "speak_cpu_utilization": [
            ("is_trading_day", "True", [("speak_cpu_utilization", "1")])
        ],
        "speak_seconds_until_open": [
            (
                "is_trading_day",
                "True",
                [("speak_seconds_until_time", "${Market Data:opening_time}")],
            )
        ],
        "speak_seconds_until_midday_break": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "speak_seconds_until_time",
                        "${Market Data:midday_break_time}",
                    )
                ],
            )
        ],
        "speak_seconds_until_reopen": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "speak_seconds_until_time",
                        "${Market Data:reopening_time}",
                    )
                ],
            )
        ],
        "speak_seconds_until_last_order": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "speak_seconds_until_time",
                        "${Market Data:last_order_time}",
                    )
                ],
            )
        ],
        "speak_seconds_until_end": [
            (
                "is_trading_day",
                "True",
                [
                    (
                        "speak_seconds_until_time",
                        f"${{{trade.process}:end_time}}",
                    )
                ],
            )
        ],
    }
    config[trade.schedules_section] = {}
    config[trade.variables_section] = {
        "current_date": date.min.strftime("%Y-%m-%d"),
        "initial_cash_balance": "0",
        "current_number_of_trades": "0",
    }

    if trade.vendor == "SBI Securities":
        config[trade.customer_margin_ratios_section] = {
            "customer_margin_ratio": "0.31",
            "update_time": "20:00:00",
            "timezone": "${Market Data:timezone}",
            "url": (
                "https://search.sbisec.co.jp/v2/popwin/attention/stock/"
                "margin_M29.html"
            ),
            "symbol_header": "コード",
            "regulation_header": "規制内容",
            "headers": ("銘柄", "コード", "建玉", "信用取引区分", "規制内容"),
            "customer_margin_ratio_string": "委託保証金率",
            "suspended": "新規建停止",
        }

    if trade.process == "HYPERSBI2":
        _configure_hypersbi2(
            trade,
            config,
            file_utilities,
            data_utilities,
        )

    if can_override:
        configuration.read_config(config, trade.config_path, is_encrypted=True)

    current_date = date.today()
    if (
        date.fromisoformat(config[trade.variables_section]["current_date"])
        != current_date
    ):
        config[trade.variables_section]["current_date"] = str(current_date)
        config[trade.variables_section]["initial_cash_balance"] = "0"
        config[trade.variables_section]["current_number_of_trades"] = "0"

    if trade.process == "HYPERSBI2":
        theme_config = configparser.ConfigParser(interpolation=None)
        theme_config.read(
            os.path.join(
                os.path.expandvars("%APPDATA%"),
                trade.vendor,
                trade.process,
                "theme.ini",
            )
        )
        if (
            theme_config.has_option("General", "theme")
            and theme_config["General"]["theme"] == "Light"
        ):
            config[trade.process]["is_dark_theme"] = "False"

    return config


def _configure_hypersbi2(trade, config, file_utilities, data_utilities):
    """Populate HYPERSBI2-specific configuration defaults."""
    if not trade.executable:
        location_dat = os.path.join(
            os.path.expandvars("%LOCALAPPDATA%"),
            trade.vendor,
            trade.process,
            "location.dat",
        )
        try:
            with open(location_dat, encoding="utf-8") as f:
                trade.executable = os.path.normpath(
                    os.path.join(f.read(), trade.process + ".exe")
                )
        except OSError:
            for program_files in ("%ProgramFiles%", "%ProgramFiles(x86)%"):
                executable = os.path.join(
                    os.path.expandvars(program_files),
                    trade.vendor,
                    trade.process,
                    trade.process + ".exe",
                )
                if os.path.isfile(executable):
                    trade.executable = executable
                    break
            if not trade.executable:
                raise ConfigBuildError(
                    f"The executable file for {trade.process}"
                    " does not exist."
                )

    file_description = file_utilities.get_file_description(trade.executable)
    title = (
        data_utilities.title_except_acronyms(file_description, ["SBI"])
        + " Assistant"
        if file_description
        else re.sub(r"[\W_]+", " ", trade.script_base).strip().title()
    )

    config[trade.window_titles_section] = {
        # Double backslashes are required because these values are stored as
        # Python string literals for 'evaluate_value()', used via
        # 'interactive_windows' and user-defined actions.
        "announcements": "お知らせ",
        "summary": (
            "個別銘柄" r"\\s.*\\((${Market Data:securities_code_regex})\\)"
        ),
        "watchlists": "登録銘柄",
        "holdings": "保有証券",
        "order status": "注文一覧",
        "chart": (
            "個別チャート"
            r"\\s.*\\((${Market Data:securities_code_regex})\\).*"
        ),
        "markets": "マーケット",
        "rankings": "ランキング",
        "stock lists": "銘柄一覧",
        "account": "口座情報",
        "news": "ニュース",
        "trading": "取引ポップアップ",
        "notifications": "通知設定",
        "full order book": (
            "全板" r"\\s.*\\((${Market Data:securities_code_regex})\\)"
        ),
    }
    config[trade.process] = {
        "start_time": "${Market Data:opening_time}",
        "end_time": "${Market Data:closing_time}",
        "executable": trade.executable,
        "title": title,
        "interactive_windows": (
            file_description,
            "${HYPERSBI2 Window Titles:announcements}",
            "${HYPERSBI2 Window Titles:summary}",
            "${HYPERSBI2 Window Titles:watchlists}",
            "${HYPERSBI2 Window Titles:holdings}",
            "${HYPERSBI2 Window Titles:order status}",
            "${HYPERSBI2 Window Titles:chart}",
            "${HYPERSBI2 Window Titles:markets}",
            "${HYPERSBI2 Window Titles:rankings}",
            "${HYPERSBI2 Window Titles:stock lists}",
            "${HYPERSBI2 Window Titles:account}",
            "${HYPERSBI2 Window Titles:news}",
            "${HYPERSBI2 Window Titles:trading}",
            "${HYPERSBI2 Window Titles:notifications}",
            "${HYPERSBI2 Window Titles:full order book}",
            r"${title}\s.*",
        ),
        "input_map": {
            "left": "",
            "middle": "show_hide_watchlists",
            "right": "",
            "x1": "",
            "x2": "",
            "f1": "",
            "f2": "",
            "f3": "",
            "f4": "",
            "f5": "show_hide_watchlists",
            "f6": "",
            "f7": "",
            "f8": "",
            "f9": "",
            "f10": "",
            "f11": "",
            "f12": "",
        },
        "utilization_ratio": "1.0",
        "daily_loss_limit_ratio": "-0.01",
        "maximum_daily_number_of_trades": "0",
        "image_magnification": "2",
        "binarization_threshold": "128",
        "is_dark_theme": "True",
        "screencast_directory": os.path.join(
            os.path.expanduser("~"), "Videos", trade.process.title()
        ),
        "screencast_regex": (
            trade.process.title()
            + r" \d{4}\.\d{2}\.\d{2} - \d{2}\.\d{2}\.\d{2}\.\d+\.mp4"
        ),
    }
    config[trade.widgets_section] = {
        "is_clock_label_enabled": "False",
        "clock_label_position": "nw",
        "clock_label_font_size": "12",
        "status_bar_frame_position": "sw",
        "status_bar_frame_font_size": "17",
        "message_font_size": "14",
    }
    config[trade.startup_script_section] = {
        "pre_start_options": "",
        "post_start_options": "-rl",
        "running_options": "-l",
    }
    config[trade.actions_section]["show_hide_watchlists"] = str(
        [("show_hide_window", "${HYPERSBI2 Window Titles:watchlists}")]
    )

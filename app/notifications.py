"""User notification helpers for optional runtime services."""


def set_speech_text(trade, text):
    """Set speech text when the trade has an active speech manager."""
    speech_manager = getattr(trade, "speech_manager", None)
    if speech_manager:
        speech_manager.set_speech_text(text)
        return True
    return False

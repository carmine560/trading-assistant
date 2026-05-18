"""Action exception types for trading assistant workflows."""

from core_utilities.errors import CoreUtilitiesError


class ActionLookupError(CoreUtilitiesError):
    """Raised when a requested action is not defined."""

    def __init__(self, message, *, action_name):
        """Store missing action context for callers and diagnostics."""
        super().__init__(message)
        self.action_name = action_name


class ActionConcurrencyError(CoreUtilitiesError):
    """Raised when an action trigger arrives while another action runs."""

    def __init__(self, message, *, action_name):
        """Store skipped action context for callers and diagnostics."""
        super().__init__(message)
        self.action_name = action_name


class ActionExecutionError(CoreUtilitiesError):
    """Raised when an action definition is invalid at execution time."""

    def __init__(
        self,
        message,
        *,
        action_path,
        instruction_index,
        command,
    ):
        """Store action context for callers and diagnostics."""
        super().__init__(message)
        self.action_path = tuple(action_path)
        self.instruction_index = instruction_index
        self.command = command

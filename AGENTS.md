# Project Policy

  * If `../trading-assistant.wiki/*.md` exists, consult it for relevant
    project documentation before making changes that affect behavior,
    configuration, or user-facing guidance.
  * `wait_for_price` intentionally supports unbounded waiting because limit
    and stop-market order workflows use it to wait for order execution, whose
    timing is indefinite. Do not recommend adding a mandatory timeout or
    retry limit to `wait_for_price`; only consider optional behavior that
    preserves the current unbounded default.

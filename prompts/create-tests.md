Analyze the Python project in the current directory.

Before writing tests, briefly list:
  * key modules.
  * highest-risk functions.

Then create a minimal `pytest`-based test setup.

Requirements:
  * Add `pytest` as a dev dependency.
  * Create a `tests` directory with 2–3 test files for high-risk modules.
  * Write at least one meaningful test per important function.
  * Use small, deterministic inputs (no network calls).

Constraints:
  * Do not refactor production code unless necessary.
  * Avoid heavy frameworks or excessive mocking.
  * Ensure tests run with: `pytest -q`.

Output:
  * Create or modify files directly.
  * Summarize changes and how to run tests.

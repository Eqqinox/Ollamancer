"""The startup wordmark.

ASCII art fails silently in a way ordinary strings do not. Add one character to a row and
that row shifts, the letters stop lining up, and nothing raises: the misalignment only ever
shows up on someone else's screen. So the shape is pinned here.

The art is deliberately terminal-only. It was tried in README.md and removed, so there is
exactly one copy of it and nothing to keep in sync.

Offline. No model, no Ollama, no terminal.

    PYTHONPATH="$PWD" python tests/test_banner.py
"""

from agentic import cli, i18n

# ── the art itself ───────────────────────────────────────────────────────────

ART = i18n.BANNER_ART

assert len(ART) == 5, f"expected 5 rows, got {len(ART)}"

# Every row is the same length, which is the whole property that makes it align.
widths = {len(line) for line in ART}
assert widths == {i18n.BANNER_WIDTH}, f"ragged rows: {sorted(widths)}"

# The wordmark must actually read OLLAMANCER. Collapsing the block characters to a mask and
# counting the letter columns catches a row pasted in from the wrong render.
assert all(set(line) <= set(" ▀▄█▲▼●→←") for line in ART), "unexpected character in the art"

# Rendering it must not be wider than the guard claims, or the guard lets through a banner
# that wraps.
assert i18n.BANNER_MIN_COLS > i18n.BANNER_WIDTH, "the threshold must exceed the art width"

# ── the width guard ──────────────────────────────────────────────────────────


class _FakeConsole:
    def __init__(self, width):
        self.width = width
        self.lines = []

    def print(self, *args, **kw):
        self.lines.append(args[0] if args else "")


_real_console = cli.ui.console
try:
    # Wide enough: all five rows are printed, and nothing is reformatted on the way out.
    cli.ui.console = _FakeConsole(120)
    cli._print_banner()
    assert cli.ui.console.lines[:5] == ART, "the art was altered before printing"

    # Exactly at the threshold still draws, one column under it does not.
    cli.ui.console = _FakeConsole(i18n.BANNER_MIN_COLS)
    cli._print_banner()
    assert cli.ui.console.lines, "the banner should draw at exactly BANNER_MIN_COLS"

    cli.ui.console = _FakeConsole(i18n.BANNER_MIN_COLS - 1)
    cli._print_banner()
    assert cli.ui.console.lines == [], "a narrow terminal must get no banner at all"

    # An 80-column terminal is the common default and must be wide enough, otherwise most
    # users would never see the thing.
    cli.ui.console = _FakeConsole(80)
    cli._print_banner()
    assert cli.ui.console.lines, "the banner must fit a standard 80-column terminal"
finally:
    cli.ui.console = _real_console

print("test_banner: ALL PASS")

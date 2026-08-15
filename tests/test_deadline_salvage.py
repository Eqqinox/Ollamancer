"""Running out of budget must produce an answer, not a status line.

Both ways a turn can end without finishing used to discard everything it had gathered. The
round limit returned the string "Stopped after N tool-call rounds"; a wall-clock deadline had no
handling at all. In the model-ranking campaign the second case hit **50 of 135 runs** — one of
them after 35 successful tool calls whose results were read, useful, and thrown away. What the
user got for eight minutes of waiting was a sentence explaining there would be no answer.

`_salvage` spends one final generation instead: no tools, answer from the evidence already in
the conversation, say plainly what is missing. The literature's phrasing for this is exact —
the choice is between a useful 80% answer and a useless 0% one.

Three properties, all pinned below, and each one was a real bug or nearly one:

  1. **The salvage call carries NO tools.** `_stream_or_buffer_chat(model, messages, None)`
     means *every* native and MCP tool, not none — the first version of `_salvage` passed None
     and handed the model the full toolset at the exact moment the budget was gone. It failed
     silently, too: the model just made another tool call, the salvage returned empty, and the
     status line came back anyway. Only an explicit `[]` disables them.
  2. **The salvaged answer is what the caller receives**, not the exhaustion message.
  3. **Failure is still honest.** If the salvage generation itself fails or comes back empty,
     the status line returns. A salvage that silently produced nothing would be worse than the
     message it replaced.

The honesty layer still runs on the salvaged text (`_grounding_check`, warn-not-nudge, since a
nudge is another generation and the budget is gone). Forcing an answer out of partial evidence
is exactly the condition that produces fabrication, so it is the last place to stop checking.

Offline: `ollama.chat` is monkeypatched with a model that calls tools while it has them and
answers when it does not — which is the behaviour the whole mechanism depends on.

    PYTHONPATH="$PWD" python tests/test_deadline_salvage.py
"""

import os
import pathlib
import tempfile

d = pathlib.Path(tempfile.mkdtemp())
os.chdir(d)

from agentic import config, loop, models, state          # noqa: E402

state.PROJECT_ROOT = d.resolve()
state._AUDIT_LOG = d / "audit.log"
models.get_num_ctx = lambda m: 65536
models.ollama_runner_rss_gb = lambda: None
config.STREAM_FINAL = "off"


class _F:
    def __init__(self, n, a): self.name = n; self.arguments = a


class _TC:
    def __init__(self, n, a): self.function = _F(n, a)


class _Msg:
    def __init__(self, content="", tool_calls=None, thinking=""):
        self.content = content; self.tool_calls = tool_calls; self.thinking = thinking


class _Resp:
    def __init__(self, m): self.message = m


SALVAGED = ("INCOMPLETE — I ran out of budget before finishing. Established: the current "
            "date. Still missing: the research itself.")


def _run(*, salvage_reply, max_rounds=2, budget=0):
    """Drive a turn to exhaustion. Returns (final_answer, tool_lists_seen)."""
    config.MAX_TOOL_ROUNDS = max_rounds
    config.TURN_BUDGET_SECONDS = budget
    seen = []

    def fake_chat(**kw):
        tool_list = kw.get("tools")
        seen.append(tool_list)
        # A faithful model: it keeps calling tools while it has them, and only answers when
        # they are taken away. If the salvage call still carries tools, this never answers —
        # which is precisely how the None-vs-[] bug stayed invisible.
        if tool_list:
            return _Resp(_Msg(tool_calls=[_TC("get_datetime", {})]))
        return _Resp(_Msg(content=salvage_reply))

    loop.ollama.chat = fake_chat
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "research it"}]
    return loop.run_agent(msgs, "fake-model"), seen


# ── 1. The round limit salvages instead of discarding ───────────────────────
final, seen = _run(salvage_reply=SALVAGED)
assert final == SALVAGED, f"the salvaged answer must be returned, got {final[:80]!r}"
assert seen[0], "the ordinary rounds must have tools"
assert seen[-1] == [], (
    "the salvage call must pass an EMPTY tool list. None means 'all tools' in "
    "_stream_or_buffer_chat, which hands the model the full toolset with no budget left")

log = (d / "audit.log").read_text()
assert "SALVAGE_ATTEMPT" in log and "SALVAGE_OK" in log, "the salvage must be audited"

# ── 2. A wall-clock budget triggers the same path ───────────────────────────
# TURN_BUDGET_SECONDS is checked against time.monotonic() at the top of each round, so a
# budget of 1s with a generous round limit exercises the timer rather than the counter.
import time                                                # noqa: E402
_real = time.monotonic
_clock = {"t": _real()}
time.monotonic = lambda: _clock["t"]


def _tick_chat_factory(inner):
    def wrapper(**kw):
        _clock["t"] += 5.0        # every model call burns five seconds
        return inner(**kw)
    return wrapper


config.MAX_TOOL_ROUNDS = 50
config.TURN_BUDGET_SECONDS = 1
seen2 = []


def fake_chat2(**kw):
    seen2.append(kw.get("tools"))
    if kw.get("tools"):
        return _Resp(_Msg(tool_calls=[_TC("get_datetime", {})]))
    return _Resp(_Msg(content=SALVAGED))


loop.ollama.chat = _tick_chat_factory(fake_chat2)
msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "research it"}]
final2 = loop.run_agent(msgs, "fake-model")
time.monotonic = _real

assert final2 == SALVAGED, f"a time budget must salvage too, got {final2[:80]!r}"
assert seen2[-1] == [], "the time-budget salvage must also disable tools"
assert len(seen2) < 50, "the time budget must trip well before the round limit"

# ── 3. A failed salvage still reports honestly ──────────────────────────────
# Silence here would be worse than the status line: the user would see a turn end with
# nothing at all and no explanation.
final3, _ = _run(salvage_reply="")          # model returns nothing when asked to salvage
assert "INCOMPLETE" not in final3, "an empty salvage must not be passed off as an answer"
assert final3.strip(), "a failed salvage must still say something"
log = (d / "audit.log").read_text()
assert "SALVAGE_FAILED" in log, "a failed salvage must be audited as such"

# ── 4. Off by default ───────────────────────────────────────────────────────
# A local model on a slow machine is not misbehaving, and cutting it off at a fixed wall
# clock by default would be a regression for exactly the users this project is for.
import importlib                                            # noqa: E402
fresh = importlib.import_module("agentic.config")
assert fresh.TURN_BUDGET_SECONDS in (0, config.TURN_BUDGET_SECONDS), "sanity"
src = (pathlib.Path(loop.__file__).parent / "config.py").read_text()
assert "TURN_BUDGET_SECONDS = 0" in src, \
    "the time budget must ship off by default; the round limit already bounds a runaway loop"

print("test_deadline_salvage: all assertions passed")

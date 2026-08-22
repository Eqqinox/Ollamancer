"""A tool call the code made counts as evidence, exactly like one the model made.

Two calls are injected into a turn before `run_agent` ever opens: `web._maybe_force_search`
runs `search_web_deep` on a message starting with "search", and `skills._maybe_autoload_web_
format` loads the web-answer skill. Both exist because a small model will not reliably choose
them itself, which is the same argument as the news-category routing.

The loop's per-turn bookkeeping never saw either. `turn_tool_results`, `had_research` and
`searched_since_cite` start empty and fill only inside the tool-execution block, so a turn whose
entire evidence base was handed to it looked, to every honesty check, like a turn that had
gathered nothing.

The unsearched-answer nudge is where that bites. Its premise is "the skill was auto-loaded and
nothing was searched all turn", and after a forced search the first half is true while the
second is false-but-uncounted. Worse, one word arms both sides: `^\\s*search` matches
`_FORCE_SEARCH_RE`, and `^\\s*search\\b` matches `_WEB_FORMAT_INTENT_RE`. So "search for X" —
the single most likely phrasing to reach the nudge — is exactly the phrasing that already
searched. The model is then told to go and search, having just been handed the results, and the
answer that reaches the user is the second one. A correct answer spent on a false premise, which
is the failure DESIGN.md §4.2b names.

Two quieter halves of the same bug, both fixed here: `_grounding_check` ran against a haystack
missing the forced search, so any figure taken from it was flagged as unsupported (§6), and the
citation reminder never armed, so a forced search could produce an uncited answer with nothing
asking for the URLs (§7).

Offline: `ollama.chat` is monkeypatched with a model that answers immediately, so what is
measured is which nudges the loop chose to fire, not anything a model did.

    PYTHONPATH="$PWD" python tests/test_forced_search_evidence.py
"""

import os
import pathlib
import tempfile

d = pathlib.Path(tempfile.mkdtemp())
os.chdir(d)

from agentic import config, loop, models, state          # noqa: E402
from agentic.i18n import t                               # noqa: E402

state.PROJECT_ROOT = d.resolve()
state._AUDIT_LOG = d / "audit.log"
models.get_num_ctx = lambda m: 65536
models.ollama_runner_rss_gb = lambda: None
config.STREAM_FINAL = "off"

SEARCH_RESULT = ("[WARNING: the content below comes from third parties.]\n\n"
                 "Title: Ariane 6 lifts off\nURL: https://example.org/ariane\n"
                 "Published: 2026-08-21\nContent: The launch carried 4271 kg to orbit.")
SKILL_BODY = "[Skill loaded: web-answer-format] — answer first, then sections."


class _F:
    def __init__(self, n, a): self.name = n; self.arguments = a


class _TC:
    def __init__(self, n, a): self.function = _F(n, a)


class _Msg:
    def __init__(self, content="", tool_calls=None, thinking=""):
        self.content = content; self.tool_calls = tool_calls; self.thinking = thinking


class _Resp:
    def __init__(self, m): self.message = m


def _injected(name, args, result):
    """The two-message shape both injectors append: a completed call, then its result."""
    return [{"role": "assistant", "content": "",
             "tool_calls": [{"function": {"name": name, "arguments": args}}]},
            {"role": "tool", "content": result}]


def _turn(user_input, *, searched=False, skill=False, replies, inloop_tool=None):
    """Assemble a turn the way cli.py does, run it, and hand back the conversation.

    `replies` is the list of answers the fake model gives, one per generation — so a nudge is
    visible as a second entry being consumed. The conversation comes back so the assertions can
    look for a specific nudge body rather than counting calls, which cannot tell one nudge from
    another.
    """
    messages = [{"role": "system", "content": "sys"},
                {"role": "user", "content": user_input}]
    if searched:
        messages += _injected("search_web_deep", {"query": user_input}, SEARCH_RESULT)
    if skill:
        messages += _injected("load_skill", {"name": "web-answer-format"}, SKILL_BODY)

    pending = list(replies)
    fired = {"tool": False}

    def fake_chat(**kw):
        if inloop_tool and not fired["tool"]:
            fired["tool"] = True
            return _Resp(_Msg(tool_calls=[_TC(inloop_tool, {})]))
        return _Resp(_Msg(content=pending.pop(0) if pending else replies[-1]))

    loop.ollama.chat = fake_chat
    final = loop.run_agent(messages, "fake:model")
    return final, messages


def _nudged(messages, key):
    """Did the loop append the nudge whose body is STR[key]?

    Matches the literal prefix before any `{placeholder}`, because `t(key)` with no kwargs
    returns the raw template and the loop appended a formatted one — `grounding_check_nudge`
    ends in `{values}`, so a whole-string match silently never fires. That failure runs in the
    worst direction: every `not _nudged(...)` assertion passes for free and the test reports
    success while checking nothing. It caught itself here first time out, hence the length
    guard, which fails loudly if a future string is reworded down to something unmatchable.
    """
    prefix = t(key).split("{")[0].strip()
    assert len(prefix) > 25, f"{key}: literal prefix {prefix!r} is too short to match on"
    return any(prefix in str(m.get("content") or "") for m in messages)


# ── 1. The forced search is recognised as this turn's injected evidence ─────
msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "search ariane 6"}]
msgs += _injected("search_web_deep", {"query": "ariane 6"}, SEARCH_RESULT)
assert loop._injected_turn_calls(msgs) == [("search_web_deep", SEARCH_RESULT)], \
    "the forced search must be reported as (name, result)"

# ── 2. It stops at the user message, so a previous turn is never harvested ──
# The scan walks backwards. A finished turn ends with an assistant message carrying no
# tool_calls, and the next turn appends the user message on top, so the boundary is the user
# message and nothing older can leak in — evidence from two turns ago is not this turn's.
stale = [{"role": "system", "content": "s"}, {"role": "user", "content": "older turn"}]
stale += _injected("search_web_deep", {"query": "old"}, "OLD RESULT — must not be counted")
stale += [{"role": "assistant", "content": "an answer"},
          {"role": "user", "content": "a fresh question with no injection"}]
assert loop._injected_turn_calls(stale) == [], \
    "a previous turn's injected results must not be attributed to this one"

# ── 3. Nothing injected, and both injectors together ───────────────────────
assert loop._injected_turn_calls(
    [{"role": "system", "content": "s"}, {"role": "user", "content": "hello"}]) == [], \
    "a plain turn has no injected evidence"

both = [{"role": "system", "content": "s"}, {"role": "user", "content": "search ariane 6"}]
both += _injected("search_web_deep", {"query": "ariane 6"}, SEARCH_RESULT)
both += _injected("load_skill", {"name": "web-answer-format"}, SKILL_BODY)
assert loop._injected_turn_calls(both) == [("search_web_deep", SEARCH_RESULT),
                                           ("load_skill", SKILL_BODY)], \
    "both injectors must be picked up, in the order they were appended"

# ── 4. The reported case: no unsearched nudge after a forced search ────────
# Both injectors ran, because "search for ..." arms both regexes. The answer carries no hard
# tokens, so the grounding check has nothing to say and cannot confound the result.
config.MAX_CITATION_NUDGES = 0
final, convo = _turn("search for the latest ariane launch", searched=True, skill=True,
                     replies=["Here is a summary of what the sources say."])
assert not _nudged(convo, "unsearched_nudge"), \
    "a turn that was handed a forced search must not be told it never searched"
assert final == "Here is a summary of what the sources say.", \
    "the first answer must survive — a nudge here replaces it with a second one"

# ── 5. The guard is not simply switched off ────────────────────────────────
# Skill auto-loaded, nothing searched: this is the shape the nudge exists for, and it must
# still fire. `load_skill` is deliberately absent from `_RESEARCH_TOOLS` — a skill body is
# instructions, not evidence — so seeding it cannot suppress this.
final, convo = _turn("what is the best python web framework", searched=False, skill=True,
                     replies=["Django, probably.", "Corrected after searching."])
assert _nudged(convo, "unsearched_nudge"), \
    "answering a web question from memory with no search must still be nudged"

# ── 6. The forced result is in the grounding haystack ──────────────────────
# The shape that distinguishes fixed from broken: the model also calls a tool in-loop, so
# `turn_tool_results` is non-empty either way and the check runs either way. The figure 4271
# appears only in the forced search, so before the fix it was flagged as appearing in no tool
# result — a fabrication warning about a number the code itself had fetched.
config.MAX_GROUNDING_CHECK_NUDGES = 1
final, convo = _turn("search for the latest ariane launch", searched=True, skill=True,
                     inloop_tool="get_datetime",
                     replies=["The launch carried 4271 kg.", "second answer"])
assert not _nudged(convo, "grounding_check_nudge"), \
    "a figure taken from the forced search is supported, and must not be flagged"
assert final == "The launch carried 4271 kg.", "the grounded answer must survive untouched"

# A figure that really is unsupported still gets caught — the haystack grew, it did not stop
# being checked.
final, convo = _turn("search for the latest ariane launch", searched=True, skill=True,
                     inloop_tool="get_datetime",
                     replies=["The launch carried 9999 kg.", "second answer"])
assert _nudged(convo, "grounding_check_nudge"), \
    "seeding the haystack must not blunt the check on a value that is genuinely unsupported"

# ── 7. The citation reminder now arms off a forced search ──────────────────
# `search_web_deep` is in `_CITATION_ARMING_TOOLS` and its result starts with "[WARNING:", so
# a forced search should arm it. It never did, so a forced search could produce an uncited
# answer with nothing asking for the URLs.
config.MAX_CITATION_NUDGES = 1
config.MAX_GROUNDING_CHECK_NUDGES = 0
final, convo = _turn("search for the latest ariane launch", searched=True, skill=True,
                     replies=["No URL in this answer.", "https://example.org/ariane says so."])
assert _nudged(convo, "citation_nudge"), \
    "an uncited answer built on a forced search must still be asked for its sources"

# ── 8. The loop seeds from the helper, rather than re-deriving it ──────────
body = pathlib.Path(loop.__file__).read_text()
assert "_injected_turn_calls(messages)" in body, "run_agent must seed from the helper"
assert "load_skill" not in loop._RESEARCH_TOOLS, \
    "a skill body is instructions, not evidence — it must not set had_research"
assert "search_web_deep" in loop._RESEARCH_TOOLS and \
       "search_web_deep" in loop._CITATION_ARMING_TOOLS, \
    "the forced search's tool must be both evidence and citation-arming"

print("test_forced_search_evidence: all assertions passed")

"""Agentic_1A — the ReAct loop and its honesty layers.

`run_agent` is the heart: the model thinks, calls tools, reads the results, and repeats until
it can answer without a tool. Everything else in this module exists because that loop meets
small local models, which fail in specific, repeatable ways.

**Plumbing retries.** Four distinct upstream failure signatures, each needing its own branch
because a generic "retry on error" would mask what is happening: a bad auto-generated parser
(ollama#16988), the model drifting from its own tool-call format (#14834/#16383/#16810), the
argument JSON truncated mid-generation, and a pseudo tool call emitted as plain text. Three of
these were first mistaken for model incompetence — the task was never attempted at all. When
retries are exhausted, a one-time model failover takes over rather than losing the turn.

**Empty answers.** A "thinking" model can produce a full reasoning trace and stop, never
converting it into content. The loop re-prompts before giving up, and never shows an empty
panel without explanation.

**Honesty nudges**, all deterministic and all capped, because each can false-positive:

  * `_grounding_check` — extracts the hard tokens (numbers, dates, URLs, quoted names) from
    the final answer and substring-searches them in this turn's raw tool results. Anything
    present in the answer but in no result gets flagged. No LLM, no semantics.
  * `_claim_without_action` — the answer claims "fixed"/"verified" but no edit and no
    verification happened this turn. This one exists because a model declared a bug fixed on
    a file that was bit-for-bit identical to the original.
  * thin-search and deep-search circuit breakers, the citation reminder, and the
    stuck-verification nudge that pushes toward searching when the same error repeats.

They **nudge, never gate**: each adds a message and re-runs the loop. None rewrites or
suppresses what the model produced — a censoring layer would hide the failure instead of
surfacing it.

**Compaction** runs in two stages on the real `prompt_eval_count`, not an estimate: lossless
truncation of old tool results first (free), then a structured summary of older turns, cutting
only at turn boundaries so a tool message is never orphaned from its assistant(tool_calls).
"""

import json
import re
import threading
import time

import ollama
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape as rich_escape
from rich.panel import Panel

from agentic import checkpoints, config, mcp_client, models, safety, state, tools, ui
from agentic.i18n import t
from agentic.ui import _EscapeWatcher, _UserAbort, _consume_stream
from agentic.tools import notes, web

_COMPACT_MARKER = "[⎗ Summary of earlier conversation (auto-compacted to save context)]\n\n"


# Patterns observed in practice (v2.9.14): a model that writes a pseudo tool
# call as plain text instead of using Ollama's real tool-calling mechanism
# — never executed, never caught by the "empty response" fallback
# since msg.content is not empty. Confirmed on `brianmatzelle/qwen3-coder-heretic:30b`
# (`<function=search_in_files> <parameter=...> ... </tool_call>`) et `lfm2:24b-a2b`
# (`<function=execute_tool> <parameter=command> ...`) — deux familles de modèles
# different families, same format failure.
_FAKE_TOOLCALL_RE = re.compile(r"<function=|<tool_call>|<\|tool_call\|>|function_calls>", re.IGNORECASE)


def _looks_like_fake_tool_call(text: str) -> bool:
    return bool(_FAKE_TOOLCALL_RE.search(text or ""))


# Pattern observed in practice (v2.9.16, test T8 "tool disambiguation"): the model
# calls no tool this turn, but describes in its text what a call
# would return ("returns something like this", "might be { ... }") with
# concrete invented values (population figures, dates...), presented as a
# plausible example rather than clearly flagged as fabricated. Only fires
# if the text looks like a description of a hypothetical tool result
# AND contains a data-like structure ({ } or a code block) —
# avoiding false positives on an ordinary conceptual explanation.
_HYPOTHETICAL_TOOL_OUTPUT_RE = re.compile(
    r"\b(returns? something like|might (?:be|return|look like)|would (?:return|look like)|"
    r"something like this|calling `?[\w][\w-]*`? (?:for|with)?.{0,60}?\breturns?\b)",
    re.IGNORECASE,
)


def _looks_like_hypothetical_tool_output(text: str) -> bool:
    text = text or ""
    if not _HYPOTHETICAL_TOOL_OUTPUT_RE.search(text):
        return False
    return "{" in text or "```" in text


_EDIT_TOOLS   = {"write_file", "append_file", "edit_file"}


# run_command counts as verification just like lint_file/run_tests: observed
# in practice (v2.9.19, a 4-model comparison on a real bug) that ruff/lint only
# detects syntax/style, never logic bugs (a missing dict key, an unreachable
# branch...) — all 4 models declared themselves "verified" after a clean
# lint, without ever actually running the script, and each let through
# at least one guaranteed crash. If the model really runs the script, that is a
# stronger verification than a lint — the mechanism must recognise it as such,
# otherwise we keep re-prompting it even when it does the right thing.
_VERIFY_TOOLS = {"lint_file", "run_tests", "run_command"}


_EDIT_SUCCESS_PREFIX = {"write_file": "File written:", "append_file": "Appended:", "edit_file": "Modified:"}


_THIN_SEARCH_MARKERS = ("No results.", "essentially empty")


_CITATION_ARMING_TOOLS = {"search_web", "search_web_deep", "fetch_url", "fetch_url_rendered"}


_FAILURE_SIGNATURE_RE = re.compile(r'(\w+(?:Error|Exception))(?::\s*([^\n]*))?')


def _failure_signature(result_text: str) -> str | None:
    """Extract a normalized failure signature (exception type + message) from the
    tail of a verification tool's result, using the LAST Error/Exception mention
    in the text (the actual raised error, even when a traceback shows an earlier
    "During handling of the above exception" chain). Returns None for results
    that don't look like a Python crash — a clean run, a lint pass, or a non-
    Python failure this heuristic doesn't recognize.
    """
    matches = _FAILURE_SIGNATURE_RE.findall(result_text or "")
    if not matches:
        return None
    exc_type, exc_msg = matches[-1]
    return f"{exc_type}: {exc_msg}".strip()


def _stuck_search_nudge_suffix() -> str:
    return ("\n💡 This is the exact same failure as your last verification attempt — your edit "
            "didn't fix it. Rather than guessing again, use search_web to look up this specific "
            "error message or symptom. You have real web search available and should use it when "
            "you're stuck on a bug, not only when you're missing a fact.")


# ── Vérification déterministe post-réponse : jetons durs non étayés (_grounding_check) ──
# Idea: every documented confabulation incident (invented population
# figures, invented table fields, an invented date, invented JSON)
# shares a mechanically checkable property — the answer contains concrete tokens
# (numbers, dates, URLs, quoted proper nouns) that appear in NO tool result
# from this turn. No LLM, no semantics: plain extraction + substring match.
_URL_TOKEN_RE   = re.compile(r"https?://[^\s\)\]\}<>\"']+")


_ISO_DATE_RE    = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


_NUMBER_RE      = re.compile(r"\d[\d.,   /:]*\d")  # numeric token with 2+ digits in total


_QUOTED_RE      = re.compile(r"[\"“«]\s*([^\"”»\n]{3,60}?)\s*[\"”»]")


def _extract_hard_tokens(text: str) -> dict[str, list[str]]:
    """Extract 'hard' tokens from an answer: URLs, ISO dates, numbers (≥2 digits) and quoted
    proper-noun-ish strings. Returns a dict by kind so the nudge can label them. Deterministic —
    no model, no semantics; the whole point is to check them literally against tool output."""
    text = text or ""
    urls = [u.rstrip(".,);]") for u in _URL_TOKEN_RE.findall(text)]
    dates = _ISO_DATE_RE.findall(text)
    # numbers: keep only those with ≥2 digits, drop the ones already inside a URL/ISO date
    stripped = _URL_TOKEN_RE.sub(" ", _ISO_DATE_RE.sub(" ", text))
    numbers = [n for n in _NUMBER_RE.findall(stripped) if len(re.sub(r"\D", "", n)) >= 2]
    quoted = [q.strip() for q in _QUOTED_RE.findall(text)
              if any(c.isupper() for c in q) and any(c.isalpha() for c in q)]
    return {"URL": urls, "date": dates, "number": numbers, "quote": quoted}


def _grounding_check(answer: str, tool_results: list[str]) -> list[str]:
    """Return the list of hard tokens from `answer` that appear in NONE of this turn's raw
    tool results. Conservative by design (fewer false alarms): numbers are matched on their
    digit sequence with separators removed (so "8,340,000" in a result covers "8340000" in
    the answer), URLs/dates/quotes by case-insensitive substring. Empty list = nothing to flag."""
    tokens = _extract_hard_tokens(answer)
    if not any(tokens.values()):
        return []
    haystack = "\n".join(tool_results)
    haystack_low = haystack.lower()
    haystack_digits = re.sub(r"\D", "", haystack)
    unsupported: list[str] = []
    seen: set[str] = set()
    for u in tokens["URL"]:
        if u.lower() not in haystack_low and u not in seen:
            unsupported.append(u); seen.add(u)
    for d in tokens["date"]:
        if d not in haystack and re.sub(r"\D", "", d) not in haystack_digits and d not in seen:
            unsupported.append(d); seen.add(d)
    for n in tokens["number"]:
        digits = re.sub(r"\D", "", n)
        if digits and digits not in haystack_digits and n not in seen:
            unsupported.append(n); seen.add(n)
    for q in tokens["quote"]:
        if q.lower() not in haystack_low and q not in seen:
            unsupported.append(q); seen.add(q)
    return unsupported


# ── Nudge affirmation-vs-action : "corrigé/vérifié" sans édition/vérification réelle ──
_FIX_CLAIM_RE = re.compile(
    r"\b(fixed|fix(?:es|ed)? the bug|now works?|works? now|resolved|repaired|patched|"
    r"corrigé[es]?|réparé[es]?|résolu[es]?|ça marche maintenant|fonctionne maintenant)\b",
    re.IGNORECASE)


_VERIFIED_CLAIM_RE = re.compile(
    r"\b(verified|i (?:have )?tested|tested (?:it|and)|confirmed (?:that|it|working|by)|"
    r"vérifié[es]?|j'ai testé|testé et|confirmé[es]?)\b",
    re.IGNORECASE)


def _claim_without_action(answer: str, had_edit: bool, had_verification: bool) -> str | None:
    """If the final answer claims a fix but no successful write/edit happened this turn, or
    claims verification but no verification tool ran this turn, return which kind of claim is
    unbacked (for the nudge). Deterministic, uses per-turn tracking the loop already keeps.
    Nudge, never a gate — a false positive just prompts the model to restate honestly."""
    ans = answer or ""
    fix_unbacked = bool(_FIX_CLAIM_RE.search(ans)) and not had_edit
    verif_unbacked = bool(_VERIFIED_CLAIM_RE.search(ans)) and not had_verification
    if fix_unbacked and verif_unbacked:
        return "both"
    if fix_unbacked:
        return "fix"
    if verif_unbacked:
        return "verification"
    return None


_REPETITION_MIN_LINE = 25   # ignore bullets, rules and one-word lines
_REPETITION_HITS     = 3    # the same substantial line this many times = degenerating


def _looks_repetitive(text: str) -> bool:
    """True when an answer has collapsed into repeating itself.

    Small local models under nudge pressure fall into a loop — restating the same header or
    the same "You're absolutely right, let me redo this" line over and over. Nudging a model
    in that state makes it worse: each nudge triggers another full rewrite, and with an
    unbounded generation length a single runaway can take hours.

    Deliberately crude and deterministic: count substantial lines (long enough not to be a
    bullet or a horizontal rule) that appear at least _REPETITION_HITS times. No model call,
    no semantics — the same philosophy as the other checks in this module.
    """
    if not text:
        return False
    counts: dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if len(line) < _REPETITION_MIN_LINE or set(line) <= set("-=_*# "):
            continue
        counts[line] = counts.get(line, 0) + 1
        if counts[line] >= _REPETITION_HITS:
            return True
    return False


# ── Mode headless / batch (B9) ───────────────────────────────────────────────────
_FAILURE_PREFIXES = ("⚠️", "⛔")


def _looks_like_failure(final: str) -> bool:
    """Heuristic for headless exit codes: the agent's fallback/blocked messages all start
    with ⚠️/⛔ (max-rounds, empty-response, plumbing fallbacks, blocked). Everything else is
    treated as a successful completion."""
    return (final or "").strip().startswith(_FAILURE_PREFIXES)


def _estimate_tokens(messages: list) -> int:
    """Token approximation ≈ characters/4 (the standard heuristic). Used as a fallback when
    no real count is available, and to decide whether the cleanup was enough."""
    return sum(len(str(m.get("content", ""))) for m in messages) // 4


def _turn_boundaries(messages: list) -> list[int]:
    """Indices of the 'user' messages that start a real user turn — excludes our own summary
    blocks (the _COMPACT_MARKER prefix) so a fresh compaction folds the old summary and the
    new turns together (a hierarchical rolling summary, the recommended pattern)."""
    return [i for i, m in enumerate(messages)
            if m.get("role") == "user" and not str(m.get("content", "")).startswith(_COMPACT_MARKER)]


def _cleanup_old_tool_results(messages: list, keep_from: int) -> int:
    """Deterministic lossless cleanup (step 1): truncates old tool results (before keep_from)
    longer than COMPACT_TOOL_TRUNC. Returns the number of characters saved."""
    saved = 0
    for m in messages[:keep_from]:
        if m.get("role") == "tool":
            c = str(m.get("content", ""))
            if len(c) > config.COMPACT_TOOL_TRUNC:
                m["content"] = c[:config.COMPACT_TOOL_TRUNC] + f"\n…[{len(c) - config.COMPACT_TOOL_TRUNC} chars truncated during compaction]"
                saved += len(c) - config.COMPACT_TOOL_TRUNC
    return saved


def _render_transcript(span: list) -> str:
    """Flatten a span of messages into text for the summary prompt (each message capped to
    bound the size of the summary prompt)."""
    lines = []
    for m in span:
        role = str(m.get("role", "?")).upper()
        content = str(m.get("content", "")).strip()
        if m.get("tool_calls"):
            names = ", ".join((tc.get("function", {}) or {}).get("name", "?") for tc in m["tool_calls"])
            content = (content + f" [called tools: {names}]").strip()
        if content:
            lines.append(f"{role}: {content[:1500]}")
    return "\n\n".join(lines)


def _summarize_span(span: list, model: str) -> str:
    """Structured (not freeform) summary of a conversation span, using the current model."""
    if not span:
        return ""
    transcript = _render_transcript(span)
    if config.LANG == "fr":
        instr = ("Résume l'extrait de conversation ci-dessous dans CE format structuré exact, en "
                 "préservant les chemins de fichiers, noms de fonctions, valeurs exactes et décisions. "
                 "N'invente rien qui ne soit dans l'extrait.\n\n"
                 "## Objectif de la session\n## Fichiers modifiés\n## Décisions clés\n"
                 "## Problèmes ouverts\n## Prochaines étapes\n\nExtrait :\n\n" + transcript)
    else:
        instr = ("Summarize the conversation excerpt below into THIS exact structured format, "
                 "preserving file paths, function names, exact values, and decisions. Do not invent "
                 "anything not in the excerpt.\n\n"
                 "## Session Intent\n## Files Modified\n## Key Decisions\n"
                 "## Open Problems\n## Next Steps\n\nExcerpt:\n\n" + transcript)
    try:
        resp = _chat_with_live_ram(
            "compacting_status",
            lambda: ollama.chat(model=model, messages=[{"role": "user", "content": instr}],
                                 stream=False, options=models._gen_options(model)),
        )
        return (resp.message.content or "").strip()
    except Exception:
        return ""


def _compact_now(messages: list, model: str, forced: bool = False) -> str:
    """Compact the conversation IN PLACE (mutating via messages[:]). Returns a status message.
    Structure-safe: cuts only at user-turn boundaries. Keeps the system prompt + the last
    COMPACT_KEEP_TURNS turns verbatim."""
    bounds = _turn_boundaries(messages)
    if len(bounds) <= config.COMPACT_KEEP_TURNS:
        return t("compact_too_few")
    keep_from = bounds[-config.COMPACT_KEEP_TURNS]
    before_est = _estimate_tokens(messages)
    # Step 1: deterministic lossless cleanup.
    saved = _cleanup_old_tool_results(messages, keep_from)
    trigger_tokens = int(config.COMPACT_THRESHOLD_PCT / 100 * models.get_num_ctx(model))
    if not forced and _estimate_tokens(messages) < trigger_tokens:
        safety._audit("COMPACT_CLEANUP", {"chars_saved": saved})
        return t("compact_cleanup_only", saved=saved)
    # Step 2: structured summary of the oldest turns (system + recent tail preserved).
    summary = _summarize_span(messages[1:keep_from], model)
    if not summary:
        return t("compact_failed")
    block = {"role": "user", "content": _COMPACT_MARKER + summary}
    messages[:] = [messages[0], block] + messages[keep_from:]
    after_est = _estimate_tokens(messages)
    safety._audit("COMPACT", {"before_est_tokens": before_est, "after_est_tokens": after_est,
                       "kept_turns": config.COMPACT_KEEP_TURNS, "forced": forced})
    return t("compact_done", before=before_est, after=after_est)


def _maybe_compact(messages: list, model: str) -> bool:
    """Automatic compaction if enabled and the real prompt exceeds the threshold. Prefers
    Ollama's true prompt_eval_count, falling back to a character-based estimate."""
    if config.AUTO_COMPACT != "on":
        return False
    trigger_tokens = int(config.COMPACT_THRESHOLD_PCT / 100 * models.get_num_ctx(model))
    current = state._LAST_PROMPT_TOKENS or _estimate_tokens(messages)
    if current < trigger_tokens:
        return False
    ui.console.print(f"[dim]{t('compact_auto_note', pct=config.COMPACT_THRESHOLD_PCT)}[/dim]")
    status = _compact_now(messages, model, forced=False)
    ui.console.print(f"[dim]{status}[/dim]")
    return True


# ── The model call: spinner, streaming, and the buffered fallback ────────────
def _start_ram_spinner():
    """Start a console spinner with a live-RAM readout (same look as _chat_with_live_ram) and
    return a stop() callable. Used by the streaming path so the RAM/thinking indicator is shown
    while the model is warming up / reasoning, before the first answer token streams in."""
    status_cm = ui.console.status(f"[bold blue]{t('thinking_status')}[/bold blue]", spinner="dots")
    status = status_cm.__enter__()
    stop_evt = threading.Event()

    def _poll():
        while not stop_evt.is_set():
            rss = models.ollama_runner_rss_gb()
            label = t("thinking_status")
            if rss is not None:
                label += f"  [dim]· {rss:.1f} GB RAM[/dim]"
            try:
                status.update(f"[bold blue]{label}[/bold blue]")
            except Exception:
                pass
            stop_evt.wait(0.7)

    poller = threading.Thread(target=_poll, daemon=True)
    poller.start()
    _done = {"v": False}

    def stop():
        if _done["v"]:
            return
        _done["v"] = True
        stop_evt.set()
        poller.join(timeout=1)
        try:
            status_cm.__exit__(None, None, None)
        except Exception:
            pass

    return stop


def _chat_with_live_ram(status_key: str, chat_fn):
    """Run a blocking ollama.chat() call while showing live RAM usage next to the spinner."""
    with ui.console.status(f"[bold blue]{t(status_key)}[/bold blue]", spinner="dots") as status:
        stop = threading.Event()

        def _poll():
            while not stop.is_set():
                rss = models.ollama_runner_rss_gb()
                label = t(status_key)
                if rss is not None:
                    label += f"  [dim]· {rss:.1f} GB RAM[/dim]"
                status.update(f"[bold blue]{label}[/bold blue]")
                stop.wait(0.7)

        poller = threading.Thread(target=_poll, daemon=True)
        poller.start()
        try:
            return chat_fn()
        finally:
            stop.set()
            poller.join(timeout=1)


def _stream_or_buffer_chat(model, messages, tool_schemas=None):
    """The model call used by run_agent. With STREAM_FINAL on, streams and renders assistant
    text live (transient — erased on completion, so tool rounds proceed cleanly and the final
    answer is re-rendered persistently by main()). With it off, uses the classic buffered
    call with the live-RAM spinner. Any streaming failure degrades to the buffered path.
    tool_schemas defaults to all native + MCP tools; the architect phase (B4) passes a
    read-only subset."""
    tool_list = tools.TOOLS + mcp_client.MCP_TOOL_SCHEMAS if tool_schemas is None else tool_schemas

    def _buffered():
        return _chat_with_live_ram(
            "thinking_status",
            lambda: ollama.chat(model=model, messages=messages, tools=tool_list,
                                 stream=False, options=models._gen_options(model)),
        )

    if config.STREAM_FINAL != "on":
        return _buffered()

    from rich.live import Live
    try:
        stream = ollama.chat(model=model, messages=messages, tools=tool_list,
                              stream=True, options=models._gen_options(model))
    except TypeError:
        return _buffered()   # SDK without stream support — fallback

    # Phase 1: spinner + live RAM while waiting/thinking (until the first text token).
    # Phase 2: as soon as text arrives, stop the spinner and stream live.
    # On a tool round (no content, just tool_calls) the spinner stays up the
    # whole time — so the RAM readout and the "thinking" indicator remain visible during tool
    # rounds, as they were before streaming was added (a regression, since fixed).
    stop_spinner = _start_ram_spinner()
    holder: dict = {"live": None}

    def _on_text(txt: str) -> None:
        if holder["live"] is None:
            stop_spinner()   # switch spinner -> live render on the first text token
            holder["live"] = Live(console=ui.console, refresh_per_second=12, transient=True)
            holder["live"].start()
        holder["live"].update(Markdown(txt))

    # Escape (or Ctrl+C) during streaming -> stops the model and returns to the prompt.
    watcher = _EscapeWatcher()
    watcher.__enter__()
    try:
        return _consume_stream(stream, on_text=_on_text, abort_check=watcher.pressed)
    finally:
        watcher.__exit__(None, None, None)
        stop_spinner()
        if holder["live"] is not None:
            holder["live"].stop()


def run_agent(messages: list, model: str, tool_schemas=None, allowed_tools=None) -> str:
    """ReAct loop. tool_schemas overrides which tools are advertised to the model (default:
    all native + MCP); allowed_tools, if given, is a set of tool names permitted to actually
    execute — a call to anything outside it is refused without running (used by the architect
    phase (B4) to enforce a read-only planning pass even if the model tries a write)."""
    state._CURRENT_MODEL = model               # B6 : appels latéraux (vision) savent quel modèle décharger
    state._checkpoint_turn += 1
    state._checkpoint_made_this_turn = False   # B1: at most one checkpoint per turn, before the first write
    rounds = 0
    edited_since_verify = False
    nudges_used = 0
    consecutive_thin_searches = 0
    deep_search_count = 0
    deep_search_stop_nudged = False
    search_stop_nudged = False
    empty_retries = 0
    fake_toolcall_retries = 0
    searched_since_cite = False
    citation_nudges_used = 0
    grounding_nudges_used = 0
    template_parser_retries = 0
    xml_parse_retries = 0
    json_truncation_retries = 0
    last_failure_signature = None
    stuck_search_nudges_used = 0
    plumbing_failover_used = False   # A7: a single switch to a backup model per turn
    readonly_refusals = 0            # B4: write tools refused during the read-only architect phase
    readonly_nudged = False
    # Per-turn tracking for the deterministic honesty layers (items A5/A6):
    turn_tool_results: list[str] = []   # raw tool results from THIS turn -> _grounding_check
    had_successful_edit = False         # a write/edit succeeded this turn (persists, unlike edited_since_verify)
    had_verification = False            # a verification tool ran this turn
    grounding_check_nudges_used = 0
    claim_action_nudges_used = 0

    while True:
        rounds += 1
        if rounds > config.MAX_TOOL_ROUNDS:
            ui.console.print(f"[red]{t('max_rounds_hit', n=config.MAX_TOOL_ROUNDS)}[/red]")
            return t("max_rounds_hit", n=config.MAX_TOOL_ROUNDS)

        try:
            resp = _stream_or_buffer_chat(model, messages, tool_schemas)
            pec = getattr(resp, "prompt_eval_count", 0) or 0
            if pec:
                state._LAST_PROMPT_TOKENS = pec   # the prompt's true token count (for compaction)
        except ollama.ResponseError as e:
            # e.error is a dict ({"code":..., "message":...}) when the Ollama
            # response body is JSON with a nested "error" key (the case for this
            # bug précis) — voir ollama/_types.py ResponseError.__init__. On extrait
            # the message for clean display rather than the dict's raw repr.
            err_payload = e.error
            err_text = err_payload.get("message", str(err_payload)) if isinstance(err_payload, dict) else str(err_payload or e)
            if "Unable to generate parser for this template" in err_text:
                # Bug Ollama confirmé (ollama/ollama#16988) : la génération automatique
                # generating the tool-calling parser for the chat template embedded in an
                # hf.co GGUF (no native mapping on the Ollama library side) can fail
                # mid-session, not only on the first call — reproduced twice
                # in a row with Ornith-1.0-9B at the same point (~20 tool rounds), not a
                # problem tied to the conversation's content. Simply retrying the
                # identical request is the only possible client-side intervention (the
                # bug is in Ollama's internal parser generation, out of
                # reach from this code) — see DESIGN.md.
                if template_parser_retries < config.MAX_TEMPLATE_PARSER_RETRIES:
                    template_parser_retries += 1
                    ui.console.print(f"[dim]{t('template_parser_retry_note', n=template_parser_retries, max=config.MAX_TEMPLATE_PARSER_RETRIES)}[/dim]")
                    safety._audit("TEMPLATE_PARSER_RETRY", {"round": rounds, "retry": template_parser_retries, "error_preview": err_text[:200]})
                    time.sleep(1)
                    rounds -= 1  # this attempt never reached the model — don't count it against MAX_TOOL_ROUNDS
                    continue
                target = None if plumbing_failover_used else models._plumbing_failover_target(model)
                if target:
                    plumbing_failover_used = True
                    ui.console.print(f"[yellow]{t('model_failover_note', frm=model, to=target)}[/yellow]")
                    safety._audit("MODEL_FAILOVER", {"round": rounds, "from": model, "to": target, "trigger": "template_parser"})
                    model = target
                    template_parser_retries = 0
                    rounds -= 1
                    continue
                ui.console.print(f"[red]{t('template_parser_fallback', error=err_text[:200])}[/red]")
                safety._audit("TEMPLATE_PARSER_GIVEUP", {"round": rounds, "error_preview": err_text[:200]})
                return t("template_parser_fallback", error=err_text[:200])
            if "xml syntax error" in err_text.lower():
                # Bug modèle confirmé (ollama/ollama#14834, #16383, #16810) : contrairement
                # to case #16988 above, the parser itself exists and works — it is the
                # *model* (Qwen3.5/3.6 family, also seen on qwen3.5:4b) that occasionally
                # drifts from its own documented tool-call format (e.g. emitting
                # "element <parameter> closed by </function>" ou un wrapper <function_invocation>
                # obsolete), which Ollama does not tolerate and reports as a 500 error instead
                # of ignoring/repairing the drift. No upstream fix available to date (issues
                # open) — reproduced in real conditions on qwen3.5:4b on 2026-08-04
                # (see DESIGN.md): before this fix,
                # the exception propagated raw to main() and ended the session outright,
                # sometimes right after a broken file edit that was never corrected. Same
                # treatment as bug #16988: simply retry the identical request, the only
                # possible client-side intervention (nothing to fix in the content we send).
                if xml_parse_retries < config.MAX_XML_PARSE_RETRIES:
                    xml_parse_retries += 1
                    ui.console.print(f"[dim]{t('xml_parse_retry_note', n=xml_parse_retries, max=config.MAX_XML_PARSE_RETRIES)}[/dim]")
                    safety._audit("XML_PARSE_RETRY", {"round": rounds, "retry": xml_parse_retries, "error_preview": err_text[:200]})
                    time.sleep(1)
                    rounds -= 1  # this attempt never reached the model — don't count it against MAX_TOOL_ROUNDS
                    continue
                target = None if plumbing_failover_used else models._plumbing_failover_target(model)
                if target:
                    plumbing_failover_used = True
                    ui.console.print(f"[yellow]{t('model_failover_note', frm=model, to=target)}[/yellow]")
                    safety._audit("MODEL_FAILOVER", {"round": rounds, "from": model, "to": target, "trigger": "xml_parse"})
                    model = target
                    xml_parse_retries = 0
                    rounds -= 1
                    continue
                ui.console.print(f"[red]{t('xml_parse_fallback', error=err_text[:200])}[/red]")
                safety._audit("XML_PARSE_GIVEUP", {"round": rounds, "error_preview": err_text[:200]})
                return t("xml_parse_fallback", error=err_text[:200])
            if "unexpected end of json input" in err_text.lower():
                # A third Ollama failure signature, distinct from the two above — see the
                # MAX_JSON_TRUNCATION_RETRIES comment. Reproduced in real conditions on
                # Ornith on 2026-08-04 right after a write_file on a bulky file (~14 KB):
                # the previous turn had already left the file in a broken state (a syntax
                # warning never fixed) and this error ended the session before any chance to
                # réparer — voir agentic_contexte.md, section "7 septdecies".
                if json_truncation_retries < config.MAX_JSON_TRUNCATION_RETRIES:
                    json_truncation_retries += 1
                    ui.console.print(f"[dim]{t('json_truncation_retry_note', n=json_truncation_retries, max=config.MAX_JSON_TRUNCATION_RETRIES)}[/dim]")
                    safety._audit("JSON_TRUNCATION_RETRY", {"round": rounds, "retry": json_truncation_retries, "error_preview": err_text[:200]})
                    time.sleep(1)
                    rounds -= 1  # this attempt never reached the model — don't count it against MAX_TOOL_ROUNDS
                    continue
                target = None if plumbing_failover_used else models._plumbing_failover_target(model)
                if target:
                    plumbing_failover_used = True
                    ui.console.print(f"[yellow]{t('model_failover_note', frm=model, to=target)}[/yellow]")
                    safety._audit("MODEL_FAILOVER", {"round": rounds, "from": model, "to": target, "trigger": "json_truncation"})
                    model = target
                    json_truncation_retries = 0
                    rounds -= 1
                    continue
                ui.console.print(f"[red]{t('json_truncation_fallback', error=err_text[:200])}[/red]")
                safety._audit("JSON_TRUNCATION_GIVEUP", {"round": rounds, "error_preview": err_text[:200]})
                return t("json_truncation_fallback", error=err_text[:200])
            raise

        msg = resp.message

        if msg.content and msg.tool_calls:
            ui.console.print(f"\n[dim italic]{rich_escape(msg.content)}[/dim italic]")

        if not msg.tool_calls:
            if _looks_like_fake_tool_call(msg.content) and fake_toolcall_retries < config.MAX_FAKE_TOOLCALL_RETRIES:
                fake_toolcall_retries += 1
                ui.console.print(f"[dim]{t('fake_toolcall_retry_note', n=fake_toolcall_retries, max=config.MAX_FAKE_TOOLCALL_RETRIES)}[/dim]")
                safety._audit("FAKE_TOOLCALL_RETRY", {"round": rounds, "retry": fake_toolcall_retries, "content_preview": (msg.content or "")[:200]})
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({"role": "user", "content": t("fake_toolcall_nudge")})
                continue
            if _looks_like_fake_tool_call(msg.content) and fake_toolcall_retries >= config.MAX_FAKE_TOOLCALL_RETRIES:
                ui.console.print(f"[red]{t('fake_toolcall_fallback')}[/red]")
                safety._audit("FAKE_TOOLCALL_GIVEUP", {"round": rounds, "content_preview": (msg.content or "")[:200]})
                return t("fake_toolcall_fallback")
            if edited_since_verify and nudges_used < config.MAX_VERIFY_NUDGES:
                nudges_used += 1
                ui.console.print(f"[dim]{t('auto_verify_note', n=nudges_used, max=config.MAX_VERIFY_NUDGES)}[/dim]")
                safety._audit("AUTO_VERIFY_NUDGE", {"round": rounds, "nudge": nudges_used})
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({"role": "user", "content": t("verify_nudge")})
                continue
            if not (msg.content or "").strip():
                # Empty final answer (no tool_calls either). Common with
                # modèles "thinking" : ils réfléchissent (msg.thinking) puis s'arrêtent
                # without ever producing final text or a tool call. We log
                # the start of the reasoning (useful for diagnosis) and re-prompt the
                # model a few times before giving up — never show an empty panel
                # without explanation, but don't give up after a single miss either.
                thinking_preview = str(getattr(msg, "thinking", "") or "")[:200]
                if empty_retries < config.MAX_EMPTY_RETRIES:
                    empty_retries += 1
                    ui.console.print(f"[dim]{t('empty_retry_note', n=empty_retries, max=config.MAX_EMPTY_RETRIES)}[/dim]")
                    safety._audit("EMPTY_RESPONSE_RETRY", {"round": rounds, "retry": empty_retries, "thinking_preview": thinking_preview})
                    messages.append({"role": "user", "content": t("empty_retry_nudge")})
                    continue
                ui.console.print(f"[red]{t('empty_response_fallback')}[/red]")
                safety._audit("EMPTY_RESPONSE", {"round": rounds, "thinking_preview": thinking_preview})
                return t("empty_response_fallback")
            if (searched_since_cite and "http" not in msg.content
                    and citation_nudges_used < config.MAX_CITATION_NUDGES):
                citation_nudges_used += 1
                ui.console.print(f"[dim]{t('auto_citation_note', n=citation_nudges_used, max=config.MAX_CITATION_NUDGES)}[/dim]")
                safety._audit("AUTO_CITATION_NUDGE", {"round": rounds, "nudge": citation_nudges_used})
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({"role": "user", "content": t("citation_nudge")})
                continue
            if (_looks_like_hypothetical_tool_output(msg.content)
                    and grounding_nudges_used < config.MAX_GROUNDING_NUDGES):
                grounding_nudges_used += 1
                ui.console.print(f"[dim]{t('auto_grounding_note', n=grounding_nudges_used, max=config.MAX_GROUNDING_NUDGES)}[/dim]")
                safety._audit("AUTO_GROUNDING_NUDGE", {"round": rounds, "nudge": grounding_nudges_used})
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({"role": "user", "content": t("grounding_nudge")})
                continue
            # Nudge affirmation-vs-action (A6, déterministe) : "corrigé"/"vérifié" sans
            # Circuit breaker: if the answer has collapsed into repeating itself, stop
            # nudging. Every nudge triggers another full rewrite, and a model already looping
            # loops harder — this is the same class of guard as the thin-search and
            # deep-search breakers, applied to writing instead of searching.
            if _looks_repetitive(msg.content):
                safety._audit("REPETITION_STOP", {"round": rounds, "chars": len(msg.content or "")})
                ui.console.print(f"[dim]{t('repetition_stop_note')}[/dim]")
                return msg.content or ""

            # a real edit/verification this turn. Placed before _grounding_check.
            claim_kind = _claim_without_action(msg.content, had_successful_edit, had_verification)
            # Never in a read-only phase. The architect (B4) is *forbidden* to write, so
            # had_successful_edit can never become True there: the nudge would demand an action
            # the model is structurally unable to take, and it fires on any plan that merely
            # uses the word "fix". Seen live — it fired three times before a plan even existed,
            # burning rounds on an impossible instruction.
            if allowed_tools is not None:
                claim_kind = None
            if claim_kind is not None and claim_action_nudges_used < config.MAX_CLAIM_ACTION_NUDGES:
                claim_action_nudges_used += 1
                ui.console.print(f"[dim]{t('auto_claim_action_note', n=claim_action_nudges_used, max=config.MAX_CLAIM_ACTION_NUDGES)}[/dim]")
                safety._audit("AUTO_CLAIM_ACTION_NUDGE", {"round": rounds, "kind": claim_kind, "nudge": claim_action_nudges_used})
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({"role": "user", "content": t(f"claim_action_nudge_{claim_kind}")})
                continue
            # _grounding_check (A5, deterministic): hard tokens in the answer absent from
            # every tool result this turn. Only if tools actually ran.
            if turn_tool_results and grounding_check_nudges_used < config.MAX_GROUNDING_CHECK_NUDGES:
                unsupported = _grounding_check(msg.content, turn_tool_results)
                if unsupported:
                    grounding_check_nudges_used += 1
                    shown = ", ".join(unsupported[:8])
                    ui.console.print(f"[dim]{t('auto_grounding_check_note', n=grounding_check_nudges_used, max=config.MAX_GROUNDING_CHECK_NUDGES)}[/dim]")
                    safety._audit("AUTO_GROUNDING_CHECK_NUDGE", {"round": rounds, "unsupported": unsupported[:12], "nudge": grounding_check_nudges_used})
                    messages.append({"role": "assistant", "content": msg.content or ""})
                    messages.append({"role": "user", "content": t("grounding_check_nudge", values=shown)})
                    continue
            # Keep this turn's raw tool results reachable: cmd_architect uses them to tell
            # whether the URLs in a plan were actually seen, or invented.
            state._last_turn_tool_results = list(turn_tool_results)
            return msg.content or ""

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            name = tc.function.name
            args = tc.function.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}

            ui.console.print(Panel(
                f"[bold white]{rich_escape(name)}[/bold white]([cyan]{rich_escape(json.dumps(args, ensure_ascii=False))}[/cyan])",
                title=f"[yellow]{t('tool_panel_title')}[/yellow]", border_style="yellow", expand=False,
            ))

            # B4: architect phase = read-only. Even if the model attempts a write,
            # we refuse without executing (the tool schema does not expose it, this is the
            # ceinture-et-bretelles côté exécution).
            if allowed_tools is not None and name not in allowed_tools and name not in mcp_client.MCP_TOOL_MAP:
                readonly_refusals += 1
                result = f"⛔ Read-only planning phase — '{name}' is not allowed here. Produce the plan; the editor model will make the changes."
                safety._audit(name, args, blocked=True, reason="architect read-only")
                messages.append({"role": "tool", "content": result})
                ui.console.print(Panel(f"[red]{rich_escape(result)}[/red]",
                                    title=f"[cyan]{t('result_panel_title')}[/cyan]", border_style="dim green", expand=False))
                continue

            # B1: git checkpoint of the state BEFORE this turn's first write (once
            # per turn only). Captures the pre-write state so /undo can go back.
            if name in _EDIT_TOOLS:
                checkpoints._make_turn_checkpoint(f"turn {state._checkpoint_turn}: before {name}")

            # MCP tools are treated as risky by default in safe mode — an MCP
            # server can do anything a local tool can do, so it must not
            # bypass the existing approval gate.
            is_risky = name in safety._RISKY_TOOLS or name in mcp_client.MCP_TOOL_MAP
            if state.SAFE_MODE and is_risky and not safety._confirm_risky_call(name, args):
                ui.console.print(f"[dim]{t('safe_mode_denied_console')}[/dim]")
                result = "⛔ Denied by user (safe mode)."
            elif name in mcp_client.MCP_TOOL_MAP:
                conn, real_name = mcp_client.MCP_TOOL_MAP[name]
                try:
                    mcp_result, progress_events = conn.call_tool(real_name, args)
                    result = mcp_client._mcp_result_to_text(mcp_result, progress_events)
                except Exception as e:
                    result = f"⚠️ MCP tool call failed: {type(e).__name__}: {e}. Check the arguments and try again."
            else:
                fn = tools.TOOL_MAP.get(name)
                if fn is None:
                    result = f"Unknown tool: {name}"
                else:
                    try:
                        result = fn(**args)
                    except Exception as e:
                        result = f"⚠️ Tool call failed: {type(e).__name__}: {e}. Check the arguments and try again."

            # Journaliser l'action
            blocked = str(result).startswith("⛔")
            safety._audit(name, args, blocked=blocked, reason=str(result)[:100] if blocked else "")

            # This turn's raw results (for the post-answer _grounding_check) — MCP included;
            # blocked/⛔ results carry no facts, so we keep them as-is
            # (they simply won't contain any hard token to support).
            turn_tool_results.append(str(result))

            # Self-correction tracking: a successful edit arms the verification,
            # un lint/test l'éteint.
            if name in _EDIT_TOOLS and str(result).startswith(_EDIT_SUCCESS_PREFIX.get(name, "\0")):
                edited_since_verify = True
                had_successful_edit = True
            elif name in _VERIFY_TOOLS:
                edited_since_verify = False
                nudges_used = 0
                had_verification = True
                sig = _failure_signature(str(result))
                if sig is not None and sig == last_failure_signature and stuck_search_nudges_used < config.MAX_STUCK_SEARCH_NUDGES:
                    stuck_search_nudges_used += 1
                    result = str(result) + _stuck_search_nudge_suffix()
                    ui.console.print(f"[dim]{t('stuck_search_nudge_note', n=stuck_search_nudges_used, max=config.MAX_STUCK_SEARCH_NUDGES)}[/dim]")
                    safety._audit("STUCK_SEARCH_NUDGE", {"round": rounds, "signature": sig, "nudge": stuck_search_nudges_used})
                last_failure_signature = sig

            # Circuit breaker for fruitless searches: stops a model from chaining
            # 10+ search_web calls with no usable result until the context is exhausted.
            if name == "search_web":
                if any(marker in str(result) for marker in _THIN_SEARCH_MARKERS):
                    consecutive_thin_searches += 1
                else:
                    consecutive_thin_searches = 0

            # Circuit breaker for deep searches that never converge: unlike
            # the breaker above, this fires even when every result is real —
            # search_web_deep is expensive (a full page fetch), and a long chain
            # of ever-narrower queries on a self-refining sub-topic can
            # burn the whole time budget without ever producing a final answer.
            if name == "search_web_deep":
                deep_search_count += 1

            # Arms the citation reminder: a search/read that actually
            # returned content (the [WARNING: prefix is common to all 4 tools on
            # success) means there are URLs to cite in the final answer.
            if name in _CITATION_ARMING_TOOLS and str(result).startswith("[WARNING:"):
                searched_since_cite = True

            # Affichage résultat
            preview = str(result)
            color   = "red" if blocked else "green"
            if len(preview) > 300:
                preview = preview[:300] + "…"
            ui.console.print(Panel(
                f"[{color}]{rich_escape(preview)}[/{color}]",
                title=f"[cyan]{t('result_panel_title')}[/cyan]", border_style="dim green", expand=False,
            ))

            messages.append({"role": "tool", "content": str(result)})

        if consecutive_thin_searches >= config.MAX_THIN_SEARCHES and not search_stop_nudged:
            search_stop_nudged = True
            consecutive_thin_searches = 0
            ui.console.print(f"[dim]{t('search_stop_note')}[/dim]")
            safety._audit("SEARCH_STOP_NUDGE", {"round": rounds})
            messages.append({"role": "user", "content": t("search_stop_nudge")})

        if deep_search_count >= config.MAX_DEEP_SEARCHES and not deep_search_stop_nudged:
            deep_search_stop_nudged = True
            ui.console.print(f"[dim]{t('deep_search_stop_note')}[/dim]")
            safety._audit("DEEP_SEARCH_STOP_NUDGE", {"round": rounds, "count": deep_search_count})
            messages.append({"role": "user", "content": t("deep_search_stop_nudge")})

        # B4: architect phase — if the model insists on calling write/execute tools
        # (all refused in read-only mode), it can burn its entire round budget
        # without ever producing a plan (observed in live testing with a small architect model,
        # qwen3.5:4b). After a few refusals, push it once to write the plan as prose.
        if (allowed_tools is not None and readonly_refusals >= config.MAX_READONLY_REFUSALS
                and not readonly_nudged):
            readonly_nudged = True
            ui.console.print(f"[dim]{t('readonly_plan_note')}[/dim]")
            safety._audit("READONLY_PLAN_NUDGE", {"round": rounds, "refusals": readonly_refusals})
            messages.append({"role": "user", "content": t("readonly_plan_nudge")})

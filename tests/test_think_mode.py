"""Thinking Mode: what gets sent, and — more importantly — what does not.

`THINK_MODE` is the only setting whose wrong value is not a bad answer but a dead turn: a
top-level `think` argument sent to a model without the capability is an Ollama 400, and that
exact mistake is the most reported bug in every other client that shipped this feature
(openclaw #80332, Continue #11265, crush #2713, claude-code-router #972/#1046, qwen-code
#1377). In all of them the trigger is the same — a thinking setting that outlives a model
switch. `/model` makes that reachable here too, so the gate is checked per call rather than
per setting, and this file pins it.

The second half pins the part no gate can cover. Ollama reports thinking as one yes/no
capability and never says whether a model reads a bool or a level, so a model can advertise
thinking and still refuse the argument. `state._think_rejected` is how that is learned once at
runtime instead of guessed from a hardcoded list — which is also what makes the feature work
for a model pulled tomorrow.

Offline: `ollama.show` is a stub and no model is ever contacted.

    PYTHONPATH="$PWD" python tests/test_think_mode.py
"""

from agentic import config, models, state, ui

_real_show = models.ollama.show
_real_mode = config.THINK_MODE

CAPS = {
    "thinker:8b":   ["completion", "tools", "thinking"],
    "plain:8b":     ["completion", "tools"],
    "embed:latest": ["embedding"],
}
shown: list = []


def _fake_show(name):
    shown.append(name)
    if name not in CAPS:
        raise RuntimeError(f"no such model: {name}")

    class _Info:
        capabilities = CAPS[name]
    return _Info()


try:
    models.ollama.show = _fake_show

    # ── 1. "default" sends nothing, whatever the model can do ────────────────
    # The pre-feature behaviour, and the only value that is safe on every model including
    # the two here that would 400. It must not even consult the capability.
    config.THINK_MODE = "default"
    state._thinking_cache.clear(); state._think_rejected.clear(); shown.clear()
    assert models.think_kwargs("thinker:8b") == {}, "default must send no think argument"
    assert shown == [], "default must not even need a capability lookup"

    # ── 2. A capable model gets exactly what was asked ───────────────────────
    for mode, expected in (("off", False), ("low", "low"), ("medium", "medium"), ("high", "high")):
        config.THINK_MODE = mode
        state._thinking_cache.clear(); state._think_rejected.clear()
        got = models.think_kwargs("thinker:8b")
        assert got == {"think": expected}, f"{mode} should send think={expected!r}, sent {got}"

    # ── 3. The gate: a model without the capability is never sent `think` ────
    # This is the 400 that broke five other clients.
    for mode in ("off", "low", "medium", "high"):
        config.THINK_MODE = mode
        state._thinking_cache.clear(); state._think_rejected.clear()
        assert models.think_kwargs("plain:8b") == {}, (
            f"{mode} leaked a think argument to a model without the capability — this is the "
            "400 that kills the turn")
        assert models.think_kwargs("embed:latest") == {}, "embedding model must never get think"

    # ── 4. A model whose show() fails is treated as incapable, not as unknown ─
    config.THINK_MODE = "high"
    state._thinking_cache.clear(); state._think_rejected.clear()
    assert models.think_kwargs("never-pulled:70b") == {}, (
        "an unresolvable model must not be sent think on the strength of a guess")

    # ── 5. The capability is cached: one show() per model, not one per turn ──
    config.THINK_MODE = "off"
    state._thinking_cache.clear(); state._think_rejected.clear(); shown.clear()
    for _ in range(5):
        models.think_kwargs("thinker:8b")
    assert shown == ["thinker:8b"], f"expected exactly one show() call, got {shown}"

    # ── 6. A refusal learned at runtime outranks the advertised capability ───
    # The MLX case: capabilities says thinking, the template is a bare passthrough. Only the
    # 400 itself can settle it, and once settled it must stick for the session.
    config.THINK_MODE = "high"
    state._thinking_cache.clear(); state._think_rejected.clear()
    assert models.think_kwargs("thinker:8b") == {"think": "high"}
    state._think_rejected.add("thinker:8b")          # what loop.py does on the 400
    assert models.think_kwargs("thinker:8b") == {}, (
        "a model that refused the argument must not be asked again this session")

    # ── 7. reset() clears both, so a test or a new session starts clean ──────
    state.reset()
    assert not state._thinking_cache and not state._think_rejected, (
        "state.reset() must clear the thinking caches; a stale rejection would silently "
        "disable the feature for the rest of the process")

    # ── 8. The menu offers exactly the five values the code implements ───────
    # "max" is deliberately absent: Ollama rejects it top-level and takes it only nested in
    # options (ollama/ollama#15831, open). Offering it would produce an invalid-think-value
    # 400 on every model, which is the one failure this whole design exists to prevent.
    entry = next(p for p in ui._all_params() if p["var"] == "THINK_MODE")
    assert entry["options"] == ["default", "off", "low", "medium", "high"], entry["options"]
    assert entry["default"] == "default", "the safe value must be the default"
    assert "max" not in entry["options"], "max is not valid as a top-level think value"

    # ── 9. It is the first setting in the menu ───────────────────────────────
    assert ui._all_params()[0]["var"] == "THINK_MODE", (
        "Thinking Mode is meant to open the /parameters list")

    print("test_think_mode: OK")

finally:
    models.ollama.show = _real_show
    config.THINK_MODE = _real_mode
    state._thinking_cache.clear()
    state._think_rejected.clear()

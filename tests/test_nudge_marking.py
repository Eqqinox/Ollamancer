"""An automatic nudge must not look like a new user request.

Nudges are appended as ordinary `role: user` messages, which is indistinguishable from the
human typing. Weaker models acted on them as tasks: aileen1.0 wrote the citation nudge
verbatim into persistent memory — where .agentic/memory.md would then re-inject it into every
future session's system prompt — and another model ran a web search for the text of the nudge.
Neither corrected its answer, which was the whole point.
"""
import ast
import inspect
import pathlib

import agent  # noqa: F401
from agentic import config, i18n, loop

# ── 1. every nudge goes through the wrapper ─────────────────────────────────
src = pathlib.Path("agentic/loop.py").read_text()
tree = ast.parse(src)
raw = 0
for node in ast.walk(tree):
    # messages.append({"role": "user", ...}) built inline = an unwrapped nudge
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "append":
        for a in node.args:
            if isinstance(a, ast.Dict):
                keys = [k.value for k in a.keys if isinstance(k, ast.Constant)]
                vals = [v.value for v in a.values if isinstance(v, ast.Constant)]
                if "role" in keys and "user" in vals:
                    raw += 1
assert raw == 0, f"{raw} nudge(s) still injected as a bare user message — use _nudge()"

# ── 2. the wrapper actually prefixes ────────────────────────────────────────
for lang in ("en", "fr"):
    config.LANG = lang
    msg = loop._nudge("Add citations.")
    assert msg["role"] == "user"
    assert msg["content"].endswith("Add citations."), msg["content"][-40:]
    assert msg["content"] != "Add citations.", "prefix missing"
    head = msg["content"][: -len("Add citations.")].lower()
    # must name the three wrong reactions actually observed, in the right language
    words = {"en": ("search", "memory", "file"),
             "fr": ("recherche", "mémoire", "fichier")}[lang]
    for w, what in zip(words, ("searching for it", "saving it to memory", "writing it to a file")):
        assert w in head, f"[{lang}] prefix must forbid {what} (missing {w!r})"
config.LANG = "en"

# ── 3. the string exists in both languages and is not a format landmine ────
for lang in ("en", "fr"):
    p = i18n.STR[lang]["nudge_prefix"]
    assert p.strip(), f"missing nudge_prefix for {lang}"
    assert "{" not in p, "nudge_prefix must not contain format placeholders"

# ── 4. it composes with a nudge that DOES take arguments ───────────────────
from agentic.i18n import t
body = t("grounding_check_nudge", values="1.3%, 33 vessels")
composed = loop._nudge(body)["content"]
assert "1.3%" in composed and composed.startswith(t("nudge_prefix")[:20])

print("nudge marking: ALL PASS")

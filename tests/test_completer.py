import agent
from agentic import config
from prompt_toolkit.document import Document

comp = agent._SlashCompleter()

def completions_for(text):
    doc = Document(text=text, cursor_position=len(text))
    return [c.text for c in comp.get_completions(doc, None)]

# 1. typing "/" lists ALL commands
allc = completions_for("/")
assert len(allc) == len(agent._SLASH_COMMANDS), (len(allc), len(agent._SLASH_COMMANDS))
assert "/compact" in allc and "/architect" in allc and "/help" in allc

# 2. refining narrows the list — "/c" → only /clear, /context, /compact
c = set(completions_for("/c"))
assert c == {"/clear", "/context", "/compact"}, c

# 3. more characters refine further — "/co" → /context, /compact
assert set(completions_for("/co")) == {"/context", "/compact"}, completions_for("/co")
assert set(completions_for("/com")) == {"/compact"}, completions_for("/com")

# 4. "/a" → /architect, /architect-models, /add, /audit
assert set(completions_for("/a")) == {"/architect", "/architect-models", "/add", "/audit"}, completions_for("/a")

# 5. exact full command still offered (so Enter/Tab completes it)
assert completions_for("/undo") == ["/undo"]

# 6. once a space is typed (entering an argument), NO command completions (don't interrupt args)
assert completions_for("/model ") == []
assert completions_for("/review-by qwen") == []

# 7. ordinary prose (not starting with /) → no completions, never interrupts typing
assert completions_for("hello world") == []
assert completions_for("fix the bug in game.py") == []

# 8. no match → empty (e.g. a typo'd command)
assert completions_for("/zzz") == []

# 9. completion replaces the whole typed prefix (start_position spans it)
doc = Document(text="/co", cursor_position=3)
comps = list(comp.get_completions(doc, None))
assert all(x.start_position == -3 for x in comps), [x.start_position for x in comps]

# 10. descriptions follow the interface language
config.LANG = "fr"
doc = Document(text="/compact", cursor_position=8)
meta_fr = list(comp.get_completions(doc, None))[0].display_meta_text
assert "Compacter" in meta_fr, meta_fr
config.LANG = "en"
meta_en = list(comp.get_completions(doc, None))[0].display_meta_text
assert "Compact" in meta_en, meta_en

print("SLASH COMPLETER ALL PASS")

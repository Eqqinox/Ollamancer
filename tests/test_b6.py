import os, tempfile, pathlib, types
import agent

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); agent.PROJECT_ROOT = d.resolve()
agent._AUDIT_LOG = d / "audit.log"

# a real (tiny) image file + a non-image
img = d / "shot.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
txt = d / "notes.txt"; txt.write_text("hi")

# 1. detection: configured VISION_MODEL wins
agent.VISION_MODEL = "myvision:model"
assert agent._detect_vision_model() == "myvision:model"

# 2. detection: auto-detect via REAL ollama.show() capabilities, not name guessing.
#    Deliberately named to fool the old name-heuristic the wrong way in both directions:
#    "llama3-vl:8b" LOOKS multimodal by name but reports no vision capability, while
#    "totally-plain-name:13b" has NO vision-sounding name but genuinely has the capability.
agent.VISION_MODEL = ""
agent.ollama.list = lambda: types.SimpleNamespace(models=[
    types.SimpleNamespace(model="llama3-vl:8b"),          # name suggests vision, capability does not
    types.SimpleNamespace(model="totally-plain-name:13b"), # name suggests nothing, capability does
])
def fake_show(name):
    caps = {"llama3-vl:8b": ["completion", "tools"],
            "totally-plain-name:13b": ["completion", "vision", "tools"]}[name]
    return types.SimpleNamespace(capabilities=caps)
agent.ollama.show = fake_show
assert agent._detect_vision_model() == "totally-plain-name:13b", agent._detect_vision_model()
assert agent._model_has_vision("totally-plain-name:13b") is True
assert agent._model_has_vision("llama3-vl:8b") is False

# 3. no model has real vision capability → clear message, no crash (name-only match ignored)
agent.ollama.show = lambda name: types.SimpleNamespace(capabilities=["completion", "tools"])
msg = agent.analyze_image("shot.png", "what is this?")
assert "No multimodal model" in msg, msg

# 2b. fallback to name-hints only if ollama.show() fails for every model (old Ollama)
def show_always_fails(name):
    raise RuntimeError("no capabilities field on this Ollama version")
agent.ollama.show = show_always_fails
assert agent._detect_vision_model() == "llama3-vl:8b"   # name-hint fallback picks the "vl" one

# 4. happy path: sequential load/unload + images passed to the model
agent.VISION_MODEL = "vis:model"
agent._CURRENT_MODEL = "main:model"
unloaded = []
agent._unload_model = lambda m: unloaded.append(m)
captured = {}
def fake_chat(**kw):
    captured.update(kw)
    return types.SimpleNamespace(message=types.SimpleNamespace(content="A red login button on a dark UI."))
agent.ollama.chat = fake_chat
out = agent.analyze_image("shot.png", "describe the button")
assert out == "A red login button on a dark UI.", out
assert captured["model"] == "vis:model"
assert captured["messages"][0]["images"] == [str(img.resolve())], captured["messages"]
# main unloaded BEFORE vision call, vision unloaded AFTER → order [main, vis]
assert unloaded == ["main:model", "vis:model"], unloaded

# 5. missing file → error + path hint
r = agent.analyze_image("shdot.png", "q")
assert r.startswith("Image not found:") and "shot.png" in r, r

# 6. non-image extension refused
r2 = agent.analyze_image("notes.txt", "q")
assert "Not a recognized image" in r2, r2

# 7. vision model error handled, and model still unloaded (finally)
unloaded.clear()
def boom(**kw): raise agent.ollama.ResponseError("model not found")
agent.ollama.chat = boom
r3 = agent.analyze_image("shot.png", "q")
assert "Vision model error" in r3, r3
assert "vis:model" in unloaded, unloaded

# registration
assert agent.analyze_image in agent.TOOLS
assert "analyze_image" not in agent._READ_ONLY_TOOL_NAMES  # heavy side-call, excluded from architect
log = agent._AUDIT_LOG.read_text()
assert "ANALYZE_IMAGE" in log
print("B6 ALL PASS")

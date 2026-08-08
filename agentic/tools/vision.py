"""Agentic_1A — image understanding.

One tool, `analyze_image`, which hands a picture to an installed multimodal model.

**Capability detection is real, not name-based.** `_model_has_vision` asks `ollama.show()` for
the declared capabilities; `_VISION_NAME_HINTS` is only a fallback for when that call fails.
Verified necessary in both directions on real installs: a `gemma-4-12B` variant matches the
name pattern but has no vision capability, and other models have it while matching none of the
expected names.

**Loading is sequential.** The main model is unloaded before the vision model is called, then
reloads next turn. Two resident models do not fit in 24 GB — a hard constraint, not an
optimisation. `_unload_model` is called through the `models` module rather than imported by
name, so a test patching `models._unload_model` reaches it.
"""

from pathlib import Path

import ollama

from agentic import config, models, state, ui
from agentic.safety import _audit, _check_file_path
from agentic.tools.files import _closest_path_hint

# ── Vision : analyze_image (B6) ──────────────────────────────────────────────────
# Name-based fallback, used ONLY if ollama.show() fails for a given model (an old
# Ollama version, a corrupted model...) — primary detection is now the real
# "vision" capability exposed by ollama.show(model).capabilities. Verified under
# real conditions (2026-08-05): the name alone is misleading in both directions for the
# installed here: `igorls/gemma-4-12B-...-heretic` matches "gemma-4" but does NOT have the
# vision capability (a text-only community requantisation), while `qwen3.5:4b` does have
# vision capability without matching any of the expected names (llava/-vl/moondream/...).
_VISION_NAME_HINTS = ("llava", "vision", "-vl", "minicpm-v", "moondream", "bakllava",
                      "gemma3", "gemma-3", "gemma4", "gemma-4", "qwen2.5-vl", "qwen2-vl", "pixtral")


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".heic"}


def _model_has_vision(name: str) -> bool:
    """Authoritative check: does this installed model actually declare the 'vision'
    capability in ollama.show()? False (not raised) on any lookup failure."""
    try:
        caps = ollama.show(name).capabilities or []
        return "vision" in caps
    except Exception:
        return False


def _detect_vision_model() -> str:
    """The multimodal model to use: the configured VISION_MODEL, else the first installed
    model whose real Ollama capabilities include 'vision' (ollama.show, authoritative — not
    a name guess). Falls back to the name-hint heuristic only if ollama.show() itself fails
    for every model (e.g. a very old Ollama without the capabilities field). Empty string if
    none is found either way."""
    if config.VISION_MODEL:
        return config.VISION_MODEL
    try:
        names = [getattr(m, "model", None) for m in ollama.list().models]
    except Exception:
        return ""
    show_failed_for_all = True
    for name in names:
        if not name:
            continue
        try:
            caps = ollama.show(name).capabilities or []
            show_failed_for_all = False
        except Exception:
            continue
        if "vision" in caps:
            return name
    if show_failed_for_all:
        for name in names:
            if name and any(h in name.lower() for h in _VISION_NAME_HINTS):
                return name
    return ""


def analyze_image(path: str, question: str) -> str:
    """Look at an image file and answer a question about it (describe a screenshot, read a
    chart, triage a photo, debug a UI capture). Runs a one-shot call to an installed
    multimodal model. The model is loaded on its own and unloaded afterwards so it never sits
    in RAM alongside the main model (24 GB machine) — expect a short load delay.
    Args:
        path: Path to a local image file (.png/.jpg/.jpeg/.gif/.webp/...), relative or absolute
        question: What you want to know about the image
    """
    safe, reason = _check_file_path(path)
    if not safe:
        return f"⛔ Blocked: {reason}"
    p = Path(path).expanduser()
    if not p.exists():
        return f"Image not found: {p}{_closest_path_hint(path)}"
    if p.suffix.lower() not in _IMAGE_EXTS:
        return f"Not a recognized image file: {p.name} (expected one of {', '.join(sorted(_IMAGE_EXTS))})."
    vision_model = _detect_vision_model()
    if not vision_model:
        return ("No multimodal model available. Install one (e.g. `ollama pull llava` or a "
                "gemma3 vision build) and select it with /vision-model.")
    # Sequential loading: release the current model before loading the vision model.
    if state._CURRENT_MODEL and state._CURRENT_MODEL != vision_model:
        models._unload_model(state._CURRENT_MODEL)
    _audit("ANALYZE_IMAGE", {"path": str(p), "model": vision_model})
    try:
        resp = ollama.chat(
            model=vision_model, stream=False,
            messages=[{"role": "user", "content": question, "images": [str(p.resolve())]}],
        )
        answer = (resp.message.content or "").strip()
        return answer or "(the vision model returned no text)"
    except Exception as e:
        return f"Vision model error ({type(e).__name__}: {e}). Is '{vision_model}' installed and multimodal?"
    finally:
        models._unload_model(vision_model)   # frees the VRAM; the main model reloads on the next turn

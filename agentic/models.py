"""Agentic_1A — model management.

Everything about *which* model runs and how it is configured: discovering what Ollama has
installed, deciding what to start with, negotiating the context window, tracking RAM, and
the interactive `/model` picker.

Three things here are less obvious than they look:

**Context negotiation.** Ollama silently defaults to 16384 context tokens when you don't ask
for anything, regardless of the model's real maximum. `get_num_ctx` reads the true maximum
from `ollama.show()` and caps it at `config.SAFE_NUM_CTX`. Getting this wrong produced empty
and incoherent answers after ~10 tool rounds, and the cause was invisible until the running
llama-server's `-c` flag was inspected directly.

**Sequential loading.** `_unload_model` exists so the architect and editor models, or the
main and vision models, are never resident at once. On a 24 GB machine that is the difference
between working and swapping.

**Startup resolution.** The preferred default may have been deleted with `ollama rm` since it
was chosen. Rather than crashing, `_resolve_startup_model` falls back to a random installed
tool-capable model and says so. Tool calling is non-negotiable — a model without it cannot
drive this agent at all, which is why `_tool_capable_models` filters on the real capability
rather than on the name.

Model categorisation (`classify_model_by_name`, `_categorize_via_search`) is an explicitly
best-effort keyword heuristic used only to label rows in the `/model` table. It is cached per
model, and it is not, and does not claim to be, a judgement about quality.
"""

import json
import os
import platform
import random
import re
import shutil
import subprocess
import time
from pathlib import Path

import ollama
import requests
from rich.table import Table

from agentic import config, state, ui
from agentic.i18n import t
from agentic.ui import _prompt

def _load_default_model() -> str:
    """The effective default model: the one chosen by the user via /default-model
    if present, otherwise the DEFAULT_MODEL constant in the code."""
    try:
        saved = config.DEFAULT_MODEL_FILE.read_text().strip()
        if saved:
            return saved
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return config.DEFAULT_MODEL


def _save_default_model(model: str) -> None:
    try:
        config.DEFAULT_MODEL_FILE.write_text(model)
    except Exception:
        pass  # non-blocking: a failed save must never break the session


def _load_models_config() -> dict:
    """Persisted model-name settings (failover/architect/editor/vision), kept separate from
    /parameters because the curses menu adjusts values with ←/→, not free text."""
    try:
        if config.MODELS_CONFIG_FILE.exists():
            data = json.loads(config.MODELS_CONFIG_FILE.read_text())
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_models_config(updates: dict) -> None:
    try:
        data = _load_models_config()
        data.update(updates)
        config.MODELS_CONFIG_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass  # non bloquant


def _plumbing_failover_target(current_model: str) -> str | None:
    """The backup model to use when an Ollama plumbing bug has exhausted its retry
    budget (A7). "" = disabled (default). Never fails over to the same model."""
    target = (config.PLUMBING_FAILOVER_MODEL or "").strip()
    if not target or target == current_model:
        return None
    return target


def _unload_model(model: str) -> None:
    """Force Ollama to unload a model from RAM (`ollama stop`). Best-effort — used to
    guarantee the architect and editor are never both resident at once (documented VRAM
    contention on this 24 GB machine). No-op if the ollama CLI isn't on PATH."""
    if not model or shutil.which("ollama") is None:
        return
    try:
        subprocess.run(["ollama", "stop", model], capture_output=True, timeout=30)
    except Exception:
        pass


def _tool_capable_models() -> list:
    """Installed Ollama models that support tool calling — the only valid
    candidates for this agent, which depends on it entirely to function
    (same checks as pick_model_interactive)."""
    try:
        models = ollama.list().models
    except Exception:
        return []
    result = []
    for m in models:
        try:
            if "tools" in ollama.show(m.model).capabilities:
                result.append(m.model)
        except Exception:
            continue
    return result


def _resolve_startup_model() -> str | None:
    """The model to use at startup. The preferred default (chosen, or the code
    constant) if it is still installed; otherwise — instead of crashing as it
    used to when that model had since been deleted — a random choice among the
    currently installed tool-capable models. None if no usable model is
    installed at all."""
    desired = _load_default_model()
    try:
        installed = [m.model for m in ollama.list().models]
    except Exception:
        installed = []

    if any(desired in m for m in installed):
        return desired

    candidates = _tool_capable_models()
    if not candidates:
        return None

    fallback = random.choice(candidates)
    ui.console.print(f"[yellow]{t('default_model_missing', wanted=desired, picked=fallback)}[/yellow]")
    return fallback


def check_ollama(model: str) -> bool:
    try:
        available = [m.model for m in ollama.list().models]
        if not any(model in m for m in available):
            ui.console.print(f"\n[red]{t('model_not_found')}[/red] [bold]{model}[/bold]")
            if available:
                ui.console.print(f"[yellow]{t('available')}[/yellow] {', '.join(available[:8])}")
            return False
        return True
    except Exception:
        ui.console.print(f"\n[red]{t('ollama_not_started')}[/red]")
        return False


def get_num_ctx(model: str) -> int:
    """The context to request from Ollama for this model: its real maximum capped at
    SAFE_NUM_CTX (not Ollama's default, which uses 16384 without ever looking at
    the model's actual capacity). Cached per model to avoid an ollama.show() call
    on every message."""
    if model in state._num_ctx_cache:
        return state._num_ctx_cache[model]
    num_ctx = config.SAFE_NUM_CTX
    try:
        info = ollama.show(model).modelinfo or {}
        for k, v in info.items():
            if k.endswith(".context_length"):
                num_ctx = min(int(v), config.SAFE_NUM_CTX)
                break
    except Exception:
        pass
    state._num_ctx_cache[model] = num_ctx
    return num_ctx


def get_system_ram_gb() -> float:
    """Total unified memory of the machine (GB), via sysctl (macOS)."""
    try:
        out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=3)
        return int(out.stdout.strip()) / 1_000_000_000
    except Exception:
        return 16.0  # default estimate if unavailable


def get_chip_name() -> str:
    try:
        out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=3)
        return out.stdout.strip() or "Mac"
    except Exception:
        return "Mac"


_RUNNER_MARKERS = ("llama-server", "ollama_llama_server", "ollama runner")


def ollama_runner_rss_gb() -> float | None:
    """Real RAM (GB) currently held by Ollama's model-runner subprocess(es) — not an
    estimate from file size, an actual live measurement via `ps`. None if not found."""
    try:
        out = subprocess.run(["ps", "-axo", "rss=,command="], capture_output=True, text=True, timeout=3)
        total_kb = 0
        found = False
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line or "--model" not in line:
                continue
            if not any(marker in line for marker in _RUNNER_MARKERS):
                continue
            rss_str = line.split(None, 1)[0]
            if rss_str.isdigit():
                total_kb += int(rss_str)
                found = True
        return total_kb / 1_000_000 if found else None  # KB -> GB
    except Exception:
        return None


def _gen_options(model: str) -> dict:
    """Ollama options dict for a chat call — context window plus every generation
    parameter tunable live via /parameters."""
    return {
        "num_ctx": get_num_ctx(model),
        "temperature": config.GEN_TEMPERATURE,
        "top_p": config.GEN_TOP_P,
        "top_k": config.GEN_TOP_K,
        "repeat_penalty": config.GEN_REPEAT_PENALTY,
        "num_predict": config.GEN_NUM_PREDICT,
        "seed": config.GEN_SEED,
    }


def usage_tier(size_gb: float, ram_gb: float, is_moe: bool) -> str:
    """Estimate a model's load (speed) relative to the machine's total RAM.

    is_moe should come from real Ollama metadata (an `expert_count` field in
    `ollama.show(model).modelinfo`), not from guessing off the model name —
    naming conventions like "26B-A4B" only cover some publishers (Qwen,
    Gemma); others (e.g. gpt-oss) are MoE without encoding it in the tag."""
    ratio = size_gb / ram_gb if ram_gb else 1.0
    if ratio <= 0.35:
        tier = f"[green]{t('tier_light')}[/green]"
    elif ratio <= 0.65:
        tier = f"[yellow]{t('tier_medium')}[/yellow]"
    elif ratio <= 0.90:
        tier = f"[orange3]{t('tier_heavy')}[/orange3]"
    else:
        tier = f"[red]{t('tier_very_heavy')}[/red]"
    if is_moe:
        tier += " ⚡"  # MoE: faster than its size suggests
    return tier


def _is_moe_model(modelinfo: dict) -> bool:
    """True if Ollama's real model metadata reports a nonzero expert count."""
    for key, value in modelinfo.items():
        if key.rsplit(".", 1)[-1] == "expert_count":
            try:
                return int(value) > 0
            except (TypeError, ValueError):
                return bool(value)
    return False


# Local knowledge base (from earlier research), avoids a
# web search for model families already identified.
_MODEL_CATEGORY_RULES = [
    (r"qwen3-coder",       "Code"),
    (r"devstral",          "Agentic coding"),
    (r"dolphincoder",      "Lightweight code"),
    (r"glm-4\.7-flash",    "Code / Agentic"),
    (r"glm-5",             "Agentic"),
    (r"glm-ocr",           "OCR / Vision"),
    (r"gpt-oss",           "Agentic / General-purpose"),
    (r"command-r",         "Research / RAG"),
    (r"claude-coder",      "Agentic coding"),
    (r"qwen3\.6",          "Agentic / Code"),
    (r"qwen3\.5",          "General-purpose multimodal"),
    (r"\bqwen3\b",         "Reliable agentic"),
    (r"qwen2\.5-coder",    "Code"),
    (r"deepseek-coder",    "Code"),
    (r"mistral-small",     "General-purpose multimodal"),
    (r"gemma4.*coding",    "Code"),
    (r"gemma4",            "General-purpose multimodal"),
    (r"gemma2",            "Basic chat"),
    (r"translategemma",    "Translation"),
    (r"bge-m3|embed",      "Embeddings (not chat)"),
    (r"zen-pro",           "Uncensored chat"),
]


def classify_model_by_name(name: str) -> str | None:
    """Categorize a model from its name using the local knowledge base.
    Returns None if no rule matches (triggers a web search fallback)."""
    lname = name.lower()
    label = None
    for pattern, cat in _MODEL_CATEGORY_RULES:
        if re.search(pattern, lname):
            label = cat
            break
    if label is None:
        return None
    if re.search(r"abliterat|uncensor|heretic", lname) and "uncensored" not in label.lower():
        label += " (uncensored)"
    return label


_CATEGORY_KEYWORDS = [
    ("Code",                  (r"\bcod(e|ing|er)\b", r"\bprogram", r"swe-bench", r"\bdevelopers?\b")),
    ("Agentic",                (r"\bagent(ic)?\b", r"tool[- ]calling", r"function[- ]calling", r"multi-step")),
    ("Research / RAG",         (r"\brag\b", r"\bresearch\b", r"citation", r"retrieval", r"grounding")),
    ("Vision",                 (r"\bvision\b", r"multimodal", r"\bimage\b")),
    ("Translation",            (r"translat",)),
    ("Embeddings (not chat)",  (r"embedding",)),
    ("General-purpose",        (r"\bchat\b", r"general[- ]purpose", r"assistant")),
]


def _categorize_via_search(name: str) -> str:
    """Categorize an unknown model via a local SearXNG search (same backend as the search_web tool)."""
    text = ""
    try:
        r = requests.get(config.SEARXNG_URL, params={"q": f"{name} ollama model", "format": "json"}, timeout=8)
        results = r.json().get("results", [])[:5]
        text = " ".join(f"{res.get('title','')} {res.get('content','')}" for res in results).lower()
    except Exception:
        pass

    scores = {cat: sum(bool(re.search(p, text)) for p in pats) for cat, pats in _CATEGORY_KEYWORDS}
    best = max(scores, key=scores.get) if any(scores.values()) else "General-purpose (uncategorized)"

    if re.search(r"abliterat|uncensor|heretic", name.lower() + " " + text) and "uncensored" not in best.lower():
        best += " (uncensored)"
    return best


def _category_cache_path() -> Path | None:
    return state._SNAPSHOT_DIR.parent / "model_categories.json" if state._SNAPSHOT_DIR else None


def _load_category_cache() -> dict:
    path = _category_cache_path()
    if path and path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def _save_category_cache(cache: dict) -> None:
    path = _category_cache_path()
    if path:
        try:
            path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        except Exception:
            pass


def _parameter_size(info) -> str:
    """Human-readable parameter count from an ollama.show() response.

    `ollama.list()` reports an empty parameter_size for MLX builds, which left the Params
    column blank in the /model table. show() still knows: either details.parameter_size
    ("12.4B") or modelinfo["general.parameter_count"] (12382568756). Prefer the former, derive
    the latter, and return "" rather than guessing from the model name — a name like
    "gemma-4-26B-A4B" states two different numbers and neither is the real total.
    """
    try:
        size = (getattr(getattr(info, "details", None), "parameter_size", "") or "").strip()
        if size:
            return size
        count = (info.modelinfo or {}).get("general.parameter_count")
        if isinstance(count, (int, float)) and count > 0:
            return f"{count / 1e9:.1f}B" if count >= 1e9 else f"{count / 1e6:.2f}M"
    except Exception:
        pass
    return ""


def pick_model_interactive(current_model: str) -> str | None:
    """Show the list of installed Ollama models and let the user pick one."""
    try:
        models = sorted(ollama.list().models, key=lambda m: m.model)
    except Exception:
        ui.console.print(f"\n[red]{t('ollama_not_started')}[/red]")
        return None

    if not models:
        ui.console.print(f"[yellow]{t('no_models')}[/yellow]")
        return None

    ram_gb = get_system_ram_gb()
    chip   = get_chip_name()
    ui.console.print(f"[dim]{t('machine_detected', chip=chip, ram=ram_gb)}[/dim]")

    cache = _load_category_cache()
    cache_dirty = False

    with ui.console.status(f"[dim]{t('analyzing_models')}[/dim]", spinner="dots"):
        tools_ok = {}
        is_moe = {}
        categories = {}
        param_size = {}
        for m in models:
            try:
                info = ollama.show(m.model)
                tools_ok[m.model] = "tools" in info.capabilities
                is_moe[m.model] = _is_moe_model(info.modelinfo or {})
                # ollama.list() leaves parameter_size empty for MLX builds, so the Params
                # column was blank for them, and the size-only fallback made the usage tier
                # less accurate too. show() has the number; we are already calling it here.
                param_size[m.model] = _parameter_size(info)
            except Exception:
                tools_ok[m.model] = None  # unknown
                is_moe[m.model] = False
                param_size[m.model] = ""

            cat = classify_model_by_name(m.model)
            if cat is None:
                cat = cache.get(m.model)
            if cat is None:
                cat = _categorize_via_search(m.model)
                cache[m.model] = cat
                cache_dirty = True
            categories[m.model] = cat

    if cache_dirty:
        _save_category_cache(cache)

    table = Table(title=t("table_title"), show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column(t("label_model"), style="cyan", no_wrap=True, overflow="ellipsis", max_width=48)
    table.add_column(t("col_size"), justify="right", no_wrap=True)
    table.add_column(t("col_params"), justify="right", style="dim", no_wrap=True)
    table.add_column(t("col_usage"), justify="center", no_wrap=True)
    table.add_column(t("col_task"), justify="left", no_wrap=True, overflow="ellipsis", max_width=24)
    table.add_column(t("col_tools"), justify="center", no_wrap=True)
    table.add_column(t("col_active"), justify="center", no_wrap=True)

    for i, m in enumerate(models, start=1):
        size_gb = m.size / 1_000_000_000 if m.size else 0.0
        size_cell = f"{size_gb:.1f} GB" if m.size else "?"
        params  = ((m.details.parameter_size if m.details else "") or ""
                   or param_size.get(m.model, ""))   # MLX: falls back to show()
        actif   = "✓" if m.model == current_model else ""
        ok      = tools_ok.get(m.model)
        tools_cell = "[green]✓[/green]" if ok else ("[red]✗[/red]" if ok is False else "[dim]?[/dim]")
        usage_cell = usage_tier(size_gb, ram_gb, is_moe.get(m.model, False))
        task_cell  = categories.get(m.model, "General-purpose")
        row_style = "dim strike" if ok is False else None
        table.add_row(str(i), m.model, size_cell, params, usage_cell, task_cell, tools_cell, actif, style=row_style)

    ui.console.print(table)
    ui.console.print(f"[dim]{t('legend_tools')}[/dim]")
    ui.console.print(f"[dim]{t('legend_usage')}[/dim]")
    ui.console.print(f"[dim]{t('legend_task')}[/dim]")

    choice = _prompt(t("prompt_choice")).strip()
    if not choice:
        return None

    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(models):
            picked = models[idx - 1].model
        else:
            ui.console.print(f"[red]{t('invalid_number', idx=idx)}[/red]")
            return None
    else:
        matches = [m.model for m in models if choice in m.model]
        if len(matches) == 1:
            picked = matches[0]
        elif len(matches) > 1:
            ui.console.print(f"[yellow]{t('ambiguous', matches=', '.join(matches))}[/yellow]")
            return None
        else:
            ui.console.print(f"[red]{t('no_match', choice=choice)}[/red]")
            return None

    if tools_ok.get(picked) is False:
        ui.console.print(f"[red]{t('tools_incompatible', picked=picked)}[/red]")
        return None

    return picked

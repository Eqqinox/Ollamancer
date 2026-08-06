"""Agentic_1A — command-line entry point.

Parses the flags, prepares the session, and runs either the interactive prompt loop or a
headless job (`--run` / `--recipe`).

Startup order matters in two places, and both were bugs first:

  * The headless console swap happens **before anything prints**. `_init_mcp()` emits one line
    per connected server, and in headless mode stdout must carry only the final answer — it
    used to run first, so every MCP user's `--run` output was polluted.
  * Under `--private`, the session paths are simply never assigned. `_AUDIT_LOG`,
    `_SNAPSHOT_DIR`, `_SESSION_FILE` and `_CHECKPOINT_GITDIR` stay None, so the writers become
    no-ops. Defence by absence rather than by a conditional someone can forget to add.

Interactive input is deliberately forgiving at the edges: Ctrl+C at the prompt cancels the
line rather than quitting (consistent with Ctrl+C meaning "stop" during generation), so
leaving takes `/exit` or Ctrl+D. Every background process still alive at exit is killed.
"""

import atexit
import os
import readline
import shutil
import signal
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import ollama
from rich.markdown import Markdown
from rich.markup import escape as rich_escape
from rich.panel import Panel
from rich.rule import Rule

from agentic import (checkpoints, commands, config, i18n, loop, mcp_client, models, safety,
                     skills, state, tools, ui)
from agentic.i18n import t
from agentic.skills import load_skill
from agentic.tools import exec as toolexec
from agentic.tools.exec import kill_process, list_processes
from agentic.tools import notes, web

# Cleanup that must happen however the process ends — /exit, Ctrl+C, or a crash.
# Registered at import so an early failure still tears down the sandbox container,
# the REPL subprocess, background processes and the MCP servers.
atexit.register(safety._cleanup_sandbox)
atexit.register(toolexec._repl_stop)
atexit.register(toolexec._cleanup_background_processes)
atexit.register(mcp_client._cleanup_mcp)


def main():

    ui._load_params()  # réglages /parameters sauvegardés d'une session précédente
    _mc = models._load_models_config()
    config.PLUMBING_FAILOVER_MODEL = _mc.get("failover", "")  # A7: persisted backup model
    config.ARCHITECT_MODEL = _mc.get("architect", "")          # B4
    config.EDITOR_MODEL = _mc.get("editor", "")                # B4
    config.EMBED_MODEL = _mc.get("embed", config.EMBED_MODEL)         # B5 : modèle d'embedding (surchargeable)
    config.VISION_MODEL = _mc.get("vision", "")                # B6 : modèle vision (vide = auto-détection)
    try:
        config.SKILLS_GLOBAL_DIR.mkdir(parents=True, exist_ok=True)  # location of the global skills (empty at first)
    except Exception:
        pass
    argv = sys.argv[1:]
    state.SAFE_MODE = "--safe" in argv
    state.SANDBOX_MODE = "--sandbox" in argv
    state.PRIVATE_MODE = "--private" in argv or "--incognito" in argv

    # B9: headless mode. --run "prompt" (one prompt) / --recipe file.md (steps).
    run_prompt = None
    recipe_file = None
    cleaned: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--safe", "--sandbox", "--private", "--incognito"):
            i += 1; continue
        if a == "--run" and i + 1 < len(argv):
            run_prompt = argv[i + 1]; i += 2; continue
        if a == "--recipe" and i + 1 < len(argv):
            recipe_file = argv[i + 1]; i += 2; continue
        cleaned.append(a); i += 1
    argv = cleaned
    headless = run_prompt is not None or recipe_file is not None
    # Must happen before ANY output: _init_mcp() prints one line per connected server, and in
    # headless mode stdout has to carry the final answer and nothing else.
    if headless:
        # stdout carries only the final answer(s); banner/panels -> stderr.
        ui.use_stderr_console()
        config.STREAM_FINAL = "off"

    mcp_client._init_mcp()      # connects the configured MCP servers (silent if absent/not installed)

    if argv:
        project_root = Path(argv[0]).expanduser().resolve()
        if not project_root.exists():
            ui.console.print(f"[red]{t('project_not_found', path=project_root)}[/red]")
            sys.exit(1)
    else:
        project_root = Path.cwd().resolve()

    os.chdir(project_root)
    state.PROJECT_ROOT = project_root

    # .agentic/ folder for the audit log and persistent snapshots
    agent_dir    = project_root / ".agentic"
    agent_dir.mkdir(exist_ok=True)
    if state.PRIVATE_MODE:
        # Ephemeral session: we wire up NO conversation trace on disk.
        # _AUDIT_LOG/_SNAPSHOT_DIR/_SESSION_FILE stay None -> _audit/_auto_snapshot/
        # _save_session are no-ops. Git checkpoints disabled (/undo -> RAM fallback).
        # bg_logs in a temporary folder deleted on exit.
        state._AUDIT_LOG = None
        state._SNAPSHOT_DIR = None
        state._SESSION_DIR = None
        state._SESSION_FILE = None
        state._CHECKPOINT_GITDIR = None
        state._BG_LOG_DIR = Path(tempfile.mkdtemp(prefix="agentic_private_bg_"))
    else:
        state._AUDIT_LOG   = agent_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.log"
        state._SNAPSHOT_DIR = agent_dir / "snapshots"
        state._SNAPSHOT_DIR.mkdir(exist_ok=True)
        state._BG_LOG_DIR  = agent_dir / "bg_logs"
        state._BG_LOG_DIR.mkdir(exist_ok=True)
        checkpoints._init_checkpoints()   # B1: shadow git repository for /undo checkpoints (silent if git is absent)
        state._SESSION_DIR = agent_dir / "sessions"   # B3 : persistance de session + /resume
        state._SESSION_DIR.mkdir(exist_ok=True)
        state._SESSION_FILE = state._SESSION_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    state._SEMANTIC_DB = agent_dir / "semantic_index.db"   # B5: local RAG index (read; re-indexed only if search_semantic is used)
    state._memory = notes._load_memory()   # read existing memory (context); in private mode _save_memory is blocked

    # Private session: typed lines must NOT go into ~/.agentic_1a_history.
    # We recreate the prompt_toolkit session with an in-memory history (cleared on exit).
    if state.PRIVATE_MODE:
        ui.use_ephemeral_history()

    model = models._resolve_startup_model()
    if model is None:
        ui.console.print(f"\n[red]{t('no_models')}[/red]")
        sys.exit(1)

    if ui._prompt_session is None and not state.PRIVATE_MODE:
        # input()/readline fallback only — prompt_toolkit handles its own
        # history persistence via FileHistory, so the two must not
        # write to the same file in different formats.
        readline.set_history_length(500)
        try:
            readline.read_history_file(config.HISTORY_FILE)
        except (FileNotFoundError, PermissionError, OSError):
            pass

    ui.console.print()
    ui.console.print(Rule("[bold blue]  Agentic_1A v3.0  [/bold blue]", style="blue"))
    labels = [t("label_project"), t("label_model"), t("label_tools"), t("label_audit"), t("label_help")]
    w = max(len(l) for l in labels)
    ui.console.print(f"  [dim]{t('label_project').ljust(w)} :[/dim] [bold white]{project_root}[/bold white]")
    ui.console.print(f"  [dim]{t('label_model').ljust(w)} :[/dim] [cyan]{model}[/cyan]")
    ui.console.print(f"  [dim]{t('label_tools').ljust(w)} :[/dim] [green]{t('tools_suffix', n=len(tools.TOOLS))}[/green]")
    ui.console.print(f"  [dim]{t('label_audit').ljust(w)} :[/dim] [dim]{state._AUDIT_LOG}[/dim]")
    ui.console.print(f"  [dim]{t('label_help').ljust(w)} :[/dim] {t('help_hint')} [yellow]/help[/yellow]")
    ui.console.print(f"  [dim]{t('esc_hint')}[/dim]")
    if state.PRIVATE_MODE:
        ui.console.print(f"  [bold magenta]{t('private_mode_on')}[/bold magenta]")
    if state.SAFE_MODE:
        ui.console.print(f"  [bold yellow]{t('safe_mode_on')}[/bold yellow]")
    if state.SANDBOX_MODE:
        ui.console.print(f"  [bold yellow]{t('sandbox_mode_on')}[/bold yellow]")
    ui.console.print(Rule(style="dim"))
    ui.console.print()

    if not models.check_ollama(model):
        sys.exit(1)

    system_prompt = commands.make_system_prompt(project_root)
    messages = [{"role": "system", "content": system_prompt}]

    # Session-start log entry
    safety._audit("SESSION_START", {"project": str(project_root), "model": model})

    # ── B9: headless execution (one prompt or a recipe), then exit ──
    if headless:
        if recipe_file is not None:
            try:
                prompts = commands._parse_recipe(recipe_file)
            except Exception as e:
                ui.console.print(f"[red]Recipe error: {e}[/red]")
                sys.exit(2)
        else:
            prompts = [run_prompt]
        safety._audit("HEADLESS_START", {"mode": "recipe" if recipe_file else "run", "steps": len(prompts)})
        all_ok = True
        for step in prompts:
            messages.append({"role": "user", "content": step})
            try:
                final = loop.run_agent(messages, model)
            except Exception as e:
                ui.console.print(f"[red]{t('unexpected_error')}[/red] {e}")
                print(f"ERROR: {e}")
                all_ok = False
                break
            messages.append({"role": "assistant", "content": final})
            print(final)            # -> stdout (the only thing on stdout)
            if loop._looks_like_failure(final):
                all_ok = False
        commands._save_session(messages, model)
        toolexec._cleanup_background_processes(verbose=False)
        safety._cleanup_sandbox()
        toolexec._repl_stop()
        safety._audit("HEADLESS_END", {"ok": all_ok})
        sys.exit(0 if all_ok else 1)

    while True:
        try:
            user_input = ui._prompt(t("prompt_user")).strip()
        except KeyboardInterrupt:
            # Ctrl+C at the prompt: cancels the current line, does NOT quit (consistent with
            # Ctrl+C = "stop" during generation, and it avoids accidental exits).
            ui.console.print(f"[dim]{t('ctrl_c_at_prompt')}[/dim]")
            continue
        except EOFError:
            # Ctrl+D (or end of stream): a deliberate exit.
            ui.console.print(f"\n[dim]{t('session_ended')}[/dim]")
            break

        if not user_input:
            continue

        # ── Commandes slash ──────────────────────────────────────────────────
        if user_input == "/exit":
            ui.console.print(f"[dim]{t('goodbye')}[/dim]")
            break

        if user_input == "/help":
            ui.console.print(i18n.get_help_text())
            continue

        if user_input == "/clear":
            messages = [{"role": "system", "content": system_prompt}]
            state._context_files.clear()
            state._todo = ""
            state._LAST_PROMPT_TOKENS = 0   # fresh context: the token count starts over
            ui.console.print(f"[dim]{t('history_cleared')}[/dim]\n")
            continue

        if user_input == "/private":
            if state.PRIVATE_MODE:
                ui.console.print(f"[magenta]{t('private_status_on')}[/magenta]\n")
            else:
                ui.console.print(f"[dim]{t('private_status_off')}[/dim]\n")
            continue

        if user_input == "/context":
            cap = models.get_num_ctx(model)
            used = state._LAST_PROMPT_TOKENS or loop._estimate_tokens(messages)
            pct = int(used / cap * 100) if cap else 0
            ui.console.print(f"[dim]{t('context_usage', used=used, cap=cap, pct=pct, auto=config.AUTO_COMPACT, thr=config.COMPACT_THRESHOLD_PCT)}[/dim]\n")
            continue

        if user_input == "/compact":
            ui.console.print(f"[cyan]{loop._compact_now(messages, model, forced=True)}[/cyan]\n")
            commands._save_session(messages, model)
            continue

        if user_input == "/todo":
            if state._todo:
                ui.console.print()
                ui.console.print(Rule(f"[bold cyan]{t('todo_title')}[/bold cyan]", style="cyan"))
                ui.console.print(Markdown(state._todo))
                ui.console.print(Rule(style="dim"))
                ui.console.print()
            else:
                ui.console.print(f"[dim]{t('todo_empty')}[/dim]\n")
            continue

        if user_input == "/memory":
            if state._memory:
                ui.console.print()
                ui.console.print(Rule(f"[bold cyan]{t('memory_title')}[/bold cyan]", style="cyan"))
                ui.console.print(Markdown(state._memory))
                ui.console.print(Rule(style="dim"))
                ui.console.print()
            else:
                ui.console.print(f"[dim]{t('memory_empty')}[/dim]\n")
            continue

        if user_input == "/forget":
            state._memory = ""
            notes._save_memory()
            system_prompt = commands.make_system_prompt(project_root)
            messages[0] = {"role": "system", "content": system_prompt}
            safety._audit("FORGET", {})
            ui.console.print(f"[dim]{t('forget_done')}[/dim]\n")
            continue

        if user_input == "/ps":
            if state._bg_processes:
                ui.console.print()
                ui.console.print(Rule(f"[bold cyan]{t('ps_title')}[/bold cyan]", style="cyan"))
                ui.console.print(list_processes(), markup=False)
                ui.console.print(Rule(style="dim"))
                ui.console.print()
            else:
                ui.console.print(f"[dim]{t('no_bg_processes')}[/dim]\n")
            continue

        if user_input.startswith("/kill "):
            pid_label = user_input[6:].strip()
            if not pid_label:
                ui.console.print(f"[yellow]{t('kill_usage')}[/yellow]\n")
            else:
                ui.console.print(f"[cyan]{kill_process(pid_label)}[/cyan]\n")
            continue

        if user_input == "/lang":
            ui.console.print(f"[dim]{t('lang_current', lang=config.SUPPORTED_LANGS[config.LANG])}[/dim]")
            choice = ui._prompt(t("lang_prompt")).strip().lower()
            if choice in config.SUPPORTED_LANGS:
                config.LANG = choice
                system_prompt = commands.make_system_prompt(project_root)
                messages[0] = {"role": "system", "content": system_prompt}
                ui.console.print(f"[cyan]{t('lang_set', lang=config.SUPPORTED_LANGS[config.LANG])}[/cyan]\n")
            elif choice:
                ui.console.print(f"[red]{t('lang_invalid', codes=', '.join(config.SUPPORTED_LANGS))}[/red]\n")
            continue

        if user_input.startswith("/lang "):
            choice = user_input[6:].strip().lower()
            if choice in config.SUPPORTED_LANGS:
                config.LANG = choice
                system_prompt = commands.make_system_prompt(project_root)
                messages[0] = {"role": "system", "content": system_prompt}
                ui.console.print(f"[cyan]{t('lang_set', lang=config.SUPPORTED_LANGS[config.LANG])}[/cyan]\n")
            else:
                ui.console.print(f"[red]{t('lang_invalid', codes=', '.join(config.SUPPORTED_LANGS))}[/red]\n")
            continue

        if user_input == "/safe":
            state.SAFE_MODE = not state.SAFE_MODE
            style = "bold yellow" if state.SAFE_MODE else "dim"
            ui.console.print(f"[{style}]{t('safe_mode_on' if state.SAFE_MODE else 'safe_mode_off')}[/{style}]\n")
            continue

        if user_input == "/sandbox":
            state.SANDBOX_MODE = not state.SANDBOX_MODE
            style = "bold yellow" if state.SANDBOX_MODE else "dim"
            ui.console.print(f"[{style}]{t('sandbox_mode_on' if state.SANDBOX_MODE else 'sandbox_mode_off')}[/{style}]\n")
            if not state.SANDBOX_MODE:
                safety._cleanup_sandbox()  # no need to keep the container running once disabled
            continue

        if user_input in ("/parameters", "/params"):
            ui.run_parameters_menu()
            continue

        if user_input in ("/model", "/models"):
            picked = models.pick_model_interactive(model)
            if picked:
                model = picked
                ui.console.print(f"[cyan]{t('model_switch', model=model)}[/cyan]\n")
            else:
                ui.console.print(f"[dim]{t('model_cancelled')}[/dim]\n")
            continue

        if user_input.startswith("/model "):
            nm = user_input[7:].strip()
            if models.check_ollama(nm):
                model = nm
                ui.console.print(f"[cyan]{t('model_switch', model=model)}[/cyan]\n")
            continue

        if user_input in ("/default-model", "/defaultmodel"):
            picked = models.pick_model_interactive(model)
            if picked:
                models._save_default_model(picked)
                model = picked
                ui.console.print(f"[cyan]{t('default_model_set', model=picked)}[/cyan]\n")
            else:
                ui.console.print(f"[dim]{t('model_cancelled')}[/dim]\n")
            continue

        if user_input in ("/failover-model", "/failover") or user_input.startswith("/failover-model "):
            arg = user_input.split(" ", 1)[1].strip() if " " in user_input else ""
            if arg.lower() in ("off", "none", "disable", "disabled", "désactiver"):
                config.PLUMBING_FAILOVER_MODEL = ""
                models._save_models_config({"failover": ""})
                ui.console.print(f"[cyan]{t('failover_model_off')}[/cyan]\n")
            elif arg:
                config.PLUMBING_FAILOVER_MODEL = arg
                models._save_models_config({"failover": arg})
                ui.console.print(f"[cyan]{t('failover_model_set', model=arg)}[/cyan]\n")
            else:
                cur = t("failover_model_current", model=config.PLUMBING_FAILOVER_MODEL) if config.PLUMBING_FAILOVER_MODEL else t("failover_model_none")
                ui.console.print(f"[dim]{cur}[/dim]")
                picked = models.pick_model_interactive(model)
                if picked:
                    config.PLUMBING_FAILOVER_MODEL = picked
                    models._save_models_config({"failover": picked})
                    ui.console.print(f"[cyan]{t('failover_model_set', model=picked)}[/cyan]\n")
                else:
                    ui.console.print(f"[dim]{t('model_cancelled')}[/dim]\n")
            continue

        if user_input in ("/architect-models", "/architectmodels"):
            ui.console.print(f"[dim]{t('architect_models_current', arch=config.ARCHITECT_MODEL or '(current)', editor=config.EDITOR_MODEL or '(current)')}[/dim]")
            ui.console.print(f"[bold]{t('architect_pick_arch')}[/bold]")
            a = models.pick_model_interactive(model)
            if a:
                ui.console.print(f"[bold]{t('architect_pick_editor')}[/bold]")
                e = models.pick_model_interactive(model)
                if e:
                    config.ARCHITECT_MODEL, config.EDITOR_MODEL = a, e
                    models._save_models_config({"architect": a, "editor": e})
                    ui.console.print(f"[cyan]{t('architect_models_saved', arch=a, editor=e)}[/cyan]\n")
                else:
                    ui.console.print(f"[dim]{t('model_cancelled')}[/dim]\n")
            else:
                ui.console.print(f"[dim]{t('model_cancelled')}[/dim]\n")
            continue

        if user_input.startswith("/architect ") or user_input == "/architect":
            task = user_input[len("/architect"):].strip()
            if not task:
                ui.console.print(f"[yellow]{t('architect_usage')}[/yellow]\n")
                continue
            try:
                plan, final = commands.cmd_architect(task, messages, model)
            except (loop._UserAbort, KeyboardInterrupt):
                ui.console.print(f"\n[yellow]{t('user_stopped')}[/yellow]\n")
                continue
            except ollama.ResponseError as e:
                ui.console.print(f"\n[red]{t('model_error', model=model)}[/red] {e.error}\n")
                continue
            except Exception as e:
                ui.console.print(f"\n[red]{t('unexpected_error')}[/red] {e}\n")
                continue
            ui.console.print()
            ui.console.print(Rule("[bold green] Agent (editor) [/bold green]", style="green"))
            ui.console.print(Markdown(final))
            ui.console.print(Rule(style="dim"))
            ui.console.print()
            # Main history: the task + a plan/result summary (without the tool spam)
            messages.append({"role": "user", "content": f"/architect {task}"})
            messages.append({"role": "assistant", "content": f"**Plan (architect)**\n\n{plan}\n\n**Result (editor)**\n\n{final}"})
            commands._save_session(messages, model)
            continue

        if user_input in ("/vision-model", "/visionmodel") or user_input.startswith("/vision-model "):
            arg = user_input.split(" ", 1)[1].strip() if " " in user_input else ""
            if arg.lower() in ("auto", "off", "none", ""):
                if arg:
                    config.VISION_MODEL = ""
                    models._save_models_config({"vision": ""})
                    ui.console.print(f"[cyan]{t('vision_model_auto')}[/cyan]\n")
                else:
                    picked = models.pick_model_interactive(model)
                    if picked:
                        config.VISION_MODEL = picked
                        models._save_models_config({"vision": picked})
                        ui.console.print(f"[cyan]{t('vision_model_set', model=picked)}[/cyan]\n")
                    else:
                        ui.console.print(f"[dim]{t('model_cancelled')}[/dim]\n")
            else:
                config.VISION_MODEL = arg
                models._save_models_config({"vision": arg})
                ui.console.print(f"[cyan]{t('vision_model_set', model=arg)}[/cyan]\n")
            continue

        if user_input == "/tools":
            commands.show_tools()
            ui.console.print()
            continue

        if user_input == "/skills":
            found_skills = skills._discover_skills()
            if not found_skills:
                ui.console.print(f"[dim]{t('skills_none', dir=config.SKILLS_GLOBAL_DIR)}[/dim]\n")
            else:
                ui.console.print(f"[bold cyan]{t('skills_header')}[/bold cyan]")
                for name, info in sorted(found_skills.items()):
                    ui.console.print(f"  [yellow]{name}[/yellow] — {info['description']}")
                ui.console.print(f"[dim]{t('skills_usage')}[/dim]\n")
            continue

        if user_input.startswith("/skill "):
            name = user_input[7:].strip()
            loaded = load_skill(name)
            if loaded.startswith("No skill named"):
                ui.console.print(f"[yellow]{loaded}[/yellow]\n")
            else:
                messages.append({"role": "user", "content": loaded})
                ui.console.print(f"[cyan]{t('skill_loaded', name=name)}[/cyan]\n")
            continue

        if user_input == "/mcp":
            commands.show_mcp()
            ui.console.print()
            continue

        if user_input == "/history":
            commands.show_history(messages)
            ui.console.print()
            continue

        if user_input == "/resume" or user_input.startswith("/resume "):
            arg = user_input[8:].strip() if user_input.startswith("/resume ") else ""
            if not arg:
                ui.console.print(commands.cmd_resume_list())
                ui.console.print()
            else:
                loaded = commands.cmd_resume_load(arg)
                if loaded is None:
                    ui.console.print(f"[yellow]{t('resume_badindex', which=arg)}[/yellow]\n")
                else:
                    resumed_messages, saved_model = loaded
                    messages = resumed_messages
                    messages[0] = {"role": "system", "content": system_prompt}  # rafraîchit projet/mémoire courants
                    n = len([m for m in messages if m.get("role") != "system"])
                    ui.console.print(f"[cyan]{t('resume_loaded', updated=datetime.now().strftime('%H:%M:%S'), n=n)}[/cyan]\n")
            continue

        if user_input == "/pwd":
            ui.console.print(f"[bold white]{project_root}[/bold white]\n")
            continue

        if user_input.startswith("/add "):
            commands.cmd_add(user_input[5:], messages)
            continue

        if user_input == "/files":
            if not state._context_files:
                ui.console.print(f"[dim]{t('files_empty')}[/dim]\n")
            else:
                for key, name in state._context_files.items():
                    ui.console.print(f"  [green]✓[/green] {name}  [dim]{key}[/dim]")
                ui.console.print()
            continue

        if user_input.startswith("/drop "):
            target  = user_input[6:].strip()
            removed = [k for k, v in state._context_files.items() if target in k or target in v]
            for k in removed:
                del state._context_files[k]
            msg = f"[dim]{t('drop_removed', target=target)}[/dim]" if removed else f"[yellow]{t('drop_not_found', target=target)}[/yellow]"
            ui.console.print(msg + "\n")
            continue

        if user_input.startswith("/plan "):
            task = user_input[6:].strip()
            if not task:
                ui.console.print(f"[yellow]{t('plan_usage')}[/yellow]\n")
                continue
            if config.LANG == "fr":
                plan_msg = (
                    "PLANIFICATION UNIQUEMENT — N'exécute aucun outil et ne modifie aucun fichier.\n"
                    "Analyse la tâche et explique :\n"
                    "1. Les fichiers concernés et pourquoi\n"
                    "2. Les étapes dans l'ordre\n"
                    "3. Les risques ou points d'attention\n\n"
                    f"Tâche : {task}"
                )
            else:
                plan_msg = (
                    "PLANNING ONLY — Do not run any tool and do not modify any file.\n"
                    "Analyze the task and explain:\n"
                    "1. The files involved and why\n"
                    "2. The steps in order\n"
                    "3. Risks or points of attention\n\n"
                    f"Task: {task}"
                )
            messages.append({"role": "user", "content": plan_msg})
            resp = loop._chat_with_live_ram(
                "planning_status",
                lambda: ollama.chat(model=model, messages=messages, stream=False,
                                     options=models._gen_options(model)),
            )
            plan_content = resp.message.content or ""
            ui.console.print()
            ui.console.print(Rule("[bold yellow] Plan [/bold yellow]", style="yellow"))
            ui.console.print(Markdown(plan_content))
            ui.console.print(Rule(style="dim"))
            ui.console.print(f"[dim]{t('plan_footer')}[/dim]\n")
            messages.append({"role": "assistant", "content": plan_content})
            continue

        if user_input == "/diff":
            ui.console.print()
            ui.console.print(Rule("[bold magenta] Diff [/bold magenta]", style="magenta"))
            ui.console.print(Markdown(commands.cmd_diff()))
            ui.console.print(Rule(style="dim"))
            ui.console.print()
            continue

        if user_input == "/review-by" or user_input.startswith("/review-by "):
            reviewer = user_input[len("/review-by"):].strip()
            if not reviewer:
                ui.console.print(f"[yellow]{t('review_by_usage')}[/yellow]\n")
                continue
            critique = commands.cmd_review_by(reviewer, messages, model)
            if critique is None:
                ui.console.print(f"[yellow]{t('review_by_no_diff')}[/yellow]\n")
                continue
            # The main model answers the critique (and can fix the real problems).
            if config.LANG == "fr":
                followup = (f"Un second modèle ({reviewer}) a relu tes changements de cette session. "
                            f"Voici sa critique :\n\n{critique}\n\nEs-tu d'accord ? Corrige les vrais "
                            f"problèmes qu'il a trouvés (ou explique pourquoi ils n'en sont pas).")
            else:
                followup = (f"A second model ({reviewer}) reviewed your changes this session. Here is "
                            f"its critique:\n\n{critique}\n\nDo you agree? Fix any real issues it found "
                            f"(or explain why they aren't issues).")
            messages.append({"role": "user", "content": followup})
            ui.console.print(f"[dim]{t('review_by_responding')}[/dim]")
            try:
                final = loop.run_agent(messages, model)
            except (loop._UserAbort, KeyboardInterrupt):
                ui.console.print(f"\n[yellow]{t('user_stopped')}[/yellow]\n")
                continue
            except Exception as e:
                ui.console.print(f"\n[red]{t('unexpected_error')}[/red] {e}\n")
                messages.pop()
                continue
            ui.console.print()
            ui.console.print(Rule("[bold green] Agent [/bold green]", style="green"))
            ui.console.print(Markdown(final))
            ui.console.print(Rule(style="dim"))
            ui.console.print()
            messages.append({"role": "assistant", "content": final})
            commands._save_session(messages, model)
            continue

        if user_input == "/undo" or user_input.startswith("/undo "):
            if not checkpoints._checkpoints_available():
                ui.console.print(f"[cyan]{commands.cmd_undo_legacy()}[/cyan]\n")
                continue
            arg = user_input[6:].strip() if user_input.startswith("/undo ") else ""
            if not arg:
                ui.console.print(commands.cmd_undo_list())
                ui.console.print()
            else:
                ui.console.print(f"[cyan]{commands.cmd_undo_restore(arg)}[/cyan]\n")
            continue

        if user_input == "/audit":
            commands.cmd_audit()
            continue

        # ── Message normal ───────────────────────────────────────────────────
        messages.append({"role": "user", "content": user_input})
        web._maybe_force_search(user_input, messages)
        try:
            final = loop.run_agent(messages, model)
        except (loop._UserAbort, KeyboardInterrupt):
            ui.console.print(f"\n[yellow]{t('user_stopped')}[/yellow]\n")
            safety._audit("USER_ABORT", {})
            continue   # session reste vivante ; on revient à l'invite
        except ollama.ResponseError as e:
            ui.console.print(f"\n[red]{t('model_error', model=model)}[/red] {e.error}\n")
            if "does not support tools" in e.error.lower():
                ui.console.print(f"[yellow]{t('model_no_tools_hint')}[/yellow]\n")
            messages.pop()  # retire le message utilisateur non traité
            continue
        except Exception as e:
            ui.console.print(f"\n[red]{t('unexpected_error')}[/red] {e}\n")
            messages.pop()
            continue

        ui.console.print()
        ui.console.print(Rule("[bold green] Agent [/bold green]", style="green"))
        ui.console.print(Markdown(final))
        ui.console.print(Rule(style="dim"))
        ui.console.print()

        messages.append({"role": "assistant", "content": final})
        loop._maybe_compact(messages, model)  # auto-compaction if enabled and the context is above the threshold
        commands._save_session(messages, model)   # B3: persist after each turn (crash-safe)

    commands._save_session(messages, model)       # B3: final save on exit (no-op in private mode)
    toolexec._cleanup_background_processes(verbose=True)
    safety._cleanup_sandbox()
    safety._audit("SESSION_END", {})
    if state.PRIVATE_MODE:
        # Private session: delete the temporary bg-log folder (nothing else was ever
        # written). Nothing from the conversation survives on disk.
        try:
            if state._BG_LOG_DIR and str(state._BG_LOG_DIR).startswith(tempfile.gettempdir()):
                shutil.rmtree(state._BG_LOG_DIR, ignore_errors=True)
        except Exception:
            pass
    elif ui._prompt_session is None:
        try:
            readline.write_history_file(config.HISTORY_FILE)
        except (PermissionError, OSError):
            pass

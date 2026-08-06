"""Agentic_1A — settings (user configuration, persisted).

This module holds the **tunable** values: config paths, model choices, generation
parameters, web-search settings, and the loop guardrails. All 30 settings exposed by
`/parameters` live here and are persisted to `PARAMS_FILE`.

⚠️ IMPORT RULE (enforced by tests/test_import_rules.py) — these values are **rebound at
runtime** (the /parameters menu, /lang, /architect-models, /vision-model…). So always go
through the module; never import the names:

    from agentic import config      # ✅
    config.STREAM_FINAL             # ✅ resolved on every access

    from agentic.config import STREAM_FINAL   # ❌ frozen copy: will never see a change

Non-persisted runtime state (project folder, safe mode, current session…) lives in
`agentic/state.py`, not here.
"""

from pathlib import Path

# ── Paths & configuration files ──────────────────────────────────────────────
# Skills (the open SKILL.md format, compatible with Claude Code/Cursor/Codex…). Three
# sources, most specific wins: shipped with the agent (<repo>/skills/), user-global
# (~/.agentic_1a_skills/), and per-project (<project>/.agentic/skills/).
# NB: this module lives in agentic/, so the repository root is two levels up
# (agentic/config.py -> agentic/ -> <repo>). Used to locate the bundled skills.
_AGENT_HOME = Path(__file__).resolve().parent.parent
HISTORY_FILE  = Path("~/.agentic_1a_history").expanduser()
PARAMS_FILE   = Path("~/.agentic_1a_params.json").expanduser()
MCP_CONFIG_FILE = Path("~/.agentic_1a_mcp.json").expanduser()
DEFAULT_MODEL_FILE = Path("~/.agentic_1a_default_model.txt").expanduser()
# Model-name settings that don't fit the ←/→ slider in /parameters (they're free text):
# the plumbing-bug failover model (A7), the architect/editor pair (B4), and the vision
# model (B6). Same spirit as DEFAULT_MODEL_FILE, grouped into a single JSON file.
MODELS_CONFIG_FILE = Path("~/.agentic_1a_models.json").expanduser()
SKILLS_GLOBAL_DIR = Path("~/.agentic_1a_skills").expanduser()

# ── Models ───────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M"
PLUMBING_FAILOVER_MODEL = ""   # backup model name; "" = disabled (default, see A7)
ARCHITECT_MODEL = ""           # B4: "architect" model (plans, read-only); "" = current model
EDITOR_MODEL = ""              # B4: "editor" model (executes the plan, all tools); "" = current model
EMBED_MODEL = "bge-m3"         # B5: embedding model for search_semantic
VISION_MODEL = ""              # B6: multimodal model for analyze_image; "" = auto-detect

# ── Interface language ───────────────────────────────────────────────────────
# The agent's UI is deliberately bilingual EN/FR (banner, /help, messages, system
# prompt). Switch at runtime with /lang. Documentation is English-only; the interface
# is not.
LANG = "en"
SUPPORTED_LANGS = {"en": "English", "fr": "Français"}

# ── Context ──────────────────────────────────────────────────────────────────
# Ollama defaults to 16384 context tokens when you don't ask for anything — regardless
# of the model's real maximum (e.g. qwen3:8b supports 40960). An agentic session with
# several tool rounds (especially with a "thinking" model, whose reasoning also counts
# against the context) can pass 16K within a dozen exchanges, causing a context shift
# and empty or incoherent replies. We explicitly request the model's maximum, capped so
# huge-context models (256K/1M) don't blow up RAM.
SAFE_NUM_CTX = 65536   # context cap requested from Ollama (doubled 32768 -> 65536 on 2026-08-05; tunable via /parameters)

# ── Ollama generation parameters ─────────────────────────────────────────────
# Generation and web-search parameters — all adjustable live via /parameters. The
# defaults match Ollama's own defaults and the agent's behaviour before the menu
# existed, so nothing changes until the user touches something.
GEN_TEMPERATURE     = 0.8
GEN_TOP_P           = 0.9
GEN_TOP_K           = 40
GEN_REPEAT_PENALTY  = 1.1
GEN_NUM_PREDICT     = -1     # -1 = no limit
GEN_SEED            = -1     # -1 = random
STREAM_FINAL              = "on"    # "on"/"off" — stream the final answer live (B2); "off" = the older buffered behaviour (fallback if a model regresses on tool-calling while streaming)

# ── Web search ───────────────────────────────────────────────────────────────
SEARXNG_URL   = "http://localhost:8080/search"
SEARCH_LANGUAGE          = "en-US"  # "auto" = let the SearXNG instance decide
SEARCH_RESULT_CAP        = 5        # results kept by search_web
DEEP_SEARCH_FETCH_COUNT  = 3        # pages actually opened by search_web_deep
DEEP_SEARCH_CHAR_BUDGET  = 2000     # characters of clean text kept per page
DEEP_SEARCH_TIMEOUT      = 5        # seconds before giving up on a page
DEEP_SEARCH_THIN_THRESHOLD = 200    # characters — below this the text is judged a "JS shell", escalate to browser rendering
RSS_ENABLED               = "on"    # "on"/"off" — add press RSS feeds (real dates, no JS/anti-bot) for news queries
# Major-press RSS feeds verified live on 2026-08-02 — see DESIGN.md. Reuters and AP have
# had no direct RSS feed since 2020, so we go through the Google News search feed (which
# only references articles from that domain): a documented, verified-working workaround,
# not an invention.
NEWS_RSS_FEEDS = [
    ("Reuters", "https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com"),
    ("AP", "https://news.google.com/rss/search?q=when:24h+allinurl:apnews.com"),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml"),
    ("The Guardian World", "https://www.theguardian.com/world/rss"),
    ("Fox News World", "https://moxie.foxnews.com/google-publisher/world.xml"),
]
# A bare "Mozilla/5.0" is neither a real browser (no actual browser sends that token on
# its own — it is a "bot" signal in itself) nor an honest identification. We use a recent,
# complete browser string to blend into normal traffic; honouring robots.txt (see
# _check_robots) is the real compliance mechanism, not the User-Agent string.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
SEARCH_CACHE_TTL = 300  # seconds — avoids re-hitting SearXNG for a recent identical query

# ── Context compaction ───────────────────────────────────────────────────────
# Context compaction (v3.0, research-backed — see DESIGN.md). "off" by default: the
# community's main complaint is compaction that destroys working context by surprise, so
# we never enable it implicitly. Triggered on the REAL prompt token count
# (prompt_eval_count returned by Ollama), not an estimate.
AUTO_COMPACT              = "off"   # "on"/"off" — automatically summarise old history when the context fills up
COMPACT_THRESHOLD_PCT     = 70      # % of num_ctx reached before compacting (triggering early is recommended, not at 95%)
COMPACT_KEEP_TURNS        = 3       # number of recent user turns kept verbatim (the rest is summarised)
COMPACT_TOOL_TRUNC        = 800     # characters: older tool results longer than this are truncated (lossless cleanup first)

# ── Project scanning ─────────────────────────────────────────────────────────
# Which files count as "source", and which directories to skip when walking a project.
# Shared by three tool modules (files, codenav, rag), so they live here rather than in any
# one of them — config imports nothing, so this can never create a cycle.
_REF_SOURCE_EXTS  = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt"}
_REF_EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".next", "dist", "build", ".cache"}

# ── Local RAG (search_semantic) ──────────────────────────────────────────────
SEMANTIC_CHUNK_LINES = 60      # B5: size of the indexed chunks (lines)
SEMANTIC_TOP_K = 5             # B5: number of nearest chunks returned

# ── Loop guardrails & retry budgets ──────────────────────────────────────────
MAX_TOOL_ROUNDS   = 25  # guardrail: prevents an endless tool-call loop
MAX_VERIFY_NUDGES = 2   # max auto "verify your edit" re-prompts per user turn
MAX_THIN_SEARCHES = 4   # beyond this, force the model to stop searching into the void
MAX_DEEP_SEARCHES = 6   # beyond this, force a stop even when the results are real — avoids
                         # a chain of (expensive) search_web_deep calls that never converges
                         # on an answer (observed in practice: v2.9.15, 7+ calls on a
                         # self-refining sub-topic until timeout, every result real but
                         # unusable — the "empty results" circuit breaker never fires in this
                         # case because the content is never actually empty)
MAX_EMPTY_RETRIES = 2   # retries before giving up on an empty final answer
MAX_FAKE_TOOLCALL_RETRIES = 2  # retries before giving up on a tool call written as plain text
MAX_TEMPLATE_PARSER_RETRIES = 2  # retries on the Ollama error "Unable to generate parser for
                                  # this template" — confirmed Ollama-side bug (registry #16988),
                                  # observed reproducibly mid-session (not only on the first
                                  # call) on hf.co GGUFs with an auto-generated tool-calling
                                  # parser (e.g. Ornith). Simply retry the same request rather
                                  # than abandoning the whole turn — see DESIGN.md for how this
                                  # was found.
MAX_XML_PARSE_RETRIES = 2  # retries on "XML syntax error" while parsing a tool call
                            # (e.g. "element <parameter> closed by </function>") — distinct from
                            # #16988: here Ollama did generate a parser, but the *model* drifts
                            # from its own expected tool-call format (Qwen3.5/3.6 family,
                            # confirmed upstream ollama/ollama#14834, #16383, #16810 — the model
                            # occasionally emits an XML wrapper different from the one its own
                            # chat_template documents). No upstream fix available as of
                            # 2026-08-04 (issues open, nothing fixed on the Ollama side); a
                            # retry of the same request is the only possible client-side
                            # intervention, same logic as MAX_TEMPLATE_PARSER_RETRIES but on a
                            # different error signature (confirmed in real conditions on
                            # qwen3.5:4b — see DESIGN.md).
MAX_JSON_TRUNCATION_RETRIES = 2  # retries on "unexpected end of JSON input" — a third Ollama
                                  # failure signature, distinct from the two above, found on
                                  # 2026-08-04 (the "build an original script/game" benchmark on
                                  # Ornith): instead of a bad parser (#16988) or an XML format
                                  # drift (#14834/#16383), here the raw JSON of a tool call's
                                  # arguments (seen on write_file with bulky content — a ~14 KB
                                  # file in a single call) is truncated mid-generation by
                                  # llama-server before the closing braces. Standard Go message
                                  # (encoding/json) for an incomplete JSON stream — not a
                                  # client-side problem, nothing to fix in the request we send.
                                  # Same treatment: retry the identical request, then fall back
                                  # cleanly if it persists.
MAX_STUCK_SEARCH_NUDGES = 2  # "search the web" re-prompts when a verification (run_command/
                              # lint_file/run_tests) fails with exactly the same error as the
                              # previous attempt despite an edit in between — a concrete signal
                              # that the model is guessing rather than making progress. The model
                              # has search_web, but nothing before this explicitly pushed it to
                              # use it on a debugging problem rather than a factual lookup —
                              # see DESIGN.md.
MAX_CITATION_NUDGES = 1  # "cite your sources" re-prompts — a soft nudge, not a strict gate
MAX_GROUNDING_NUDGES = 1  # "don't invent a hypothetical tool result" re-prompts — observed in
                           # practice (v2.9.16, test T8): a model that calls no tool at all but
                           # describes "what get-structured-content would return" with precise
                           # invented values (population, dates...), presented as a plausible
                           # example rather than as clearly made up
MAX_GROUNDING_CHECK_NUDGES = 1  # "these values appear in no tool result this turn" re-prompts —
                                 # a deterministic post-answer check (_grounding_check), no LLM
                                 # involved: extracts the hard tokens (numbers with 2+ digits,
                                 # dates, URLs, quoted proper nouns) from the final answer and
                                 # substring-searches them in the turn's raw tool results. A
                                 # nudge, never a gate — legitimately derived values (sums,
                                 # conversions) or paraphrases can slip through or false-positive,
                                 # hence the cap of 1.
MAX_CLAIM_ACTION_NUDGES = 1  # "you claim to have fixed/verified but no edit/verification happened
                              # this turn" re-prompts — would have caught gpt-oss's "fix" on a
                              # bit-for-bit identical file, and gemma-26B's "citations added" with
                              # no write at all.
MAX_READONLY_REFUSALS = 3    # B4: beyond this many write tools refused during the architect
                              # (read-only) phase, push the model to write the plan as prose
                              # rather than keep retrying tools it does not have — found
                              # necessary in v3.0 live testing (qwen3.5:4b as architect burned
                              # all 25 rounds on refusals).

# ── Miscellaneous tool settings ──────────────────────────────────────────────
MAX_BACKGROUND_PROCESSES = 5
LARGE_WRITE_LINES = 80  # beyond this, suggest writing in chunks (write_file + append_file)
MEMORY_SOFT_LIMIT = 3000  # a warning, not a block — see the memory_write docstring

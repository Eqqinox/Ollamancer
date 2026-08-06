"""Agentic_1A — réglages (configuration utilisateur, persistée).

Ce module contient les valeurs **réglables** : chemins de configuration, choix de modèles,
paramètres de génération, réglages de recherche web, et les garde-fous de boucle. Les 30
paramètres exposés par `/parameters` vivent tous ici et sont persistés dans `PARAMS_FILE`.

⚠️ RÈGLE D'IMPORT (vérifiée par tests/test_import_rules.py) — ces valeurs sont **réassignées
à l'exécution** (menu /parameters, /lang, /architect-models, /vision-model…). Il faut donc
toujours passer par le module, jamais importer les noms :

    from agentic import config      # ✅
    config.STREAM_FINAL             # ✅ résolu à chaque accès

    from agentic.config import STREAM_FINAL   # ❌ copie figée : ne verra jamais un changement

L'état d'exécution non persisté (dossier projet, mode sûr, session courante…) vit dans
`agentic/state.py`, pas ici.
"""

from pathlib import Path

# ── Chemins & fichiers de configuration ───────────────────────────────────────
# Skills (format ouvert SKILL.md, compatible Claude Code/Cursor/Codex…). Trois sources,
# la plus spécifique gagne : livrées avec l'agent (<repo>/skills/), globales utilisateur
# (~/.agentic_1a_skills/), et par projet (<projet>/.agentic/skills/).
# NB: ce module vit dans agentic/, donc la racine du dépôt est deux niveaux au-dessus
# (agentic/config.py -> agentic/ -> <repo>). Sert à trouver les skills livrés (<repo>/skills/).
_AGENT_HOME = Path(__file__).resolve().parent.parent
HISTORY_FILE  = Path("~/.agentic_1a_history").expanduser()
PARAMS_FILE   = Path("~/.agentic_1a_params.json").expanduser()
MCP_CONFIG_FILE = Path("~/.agentic_1a_mcp.json").expanduser()
DEFAULT_MODEL_FILE = Path("~/.agentic_1a_default_model.txt").expanduser()
# Réglages nom-de-modèle qui ne rentrent pas dans le curseur ←/→ de /parameters
# (texte libre) : modèle de secours plumbing-bug (A7), paire architecte/éditeur (B4),
# modèle vision (B6). Même esprit que DEFAULT_MODEL_FILE, regroupés en un seul JSON.
MODELS_CONFIG_FILE = Path("~/.agentic_1a_models.json").expanduser()
SKILLS_GLOBAL_DIR = Path("~/.agentic_1a_skills").expanduser()

# ── Modèles ───────────────────────────────────────────────────────────────────
# ── Configuration ────────────────────────────────────────────────────────────
DEFAULT_MODEL = "hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M"
PLUMBING_FAILOVER_MODEL = ""   # nom du modèle de secours ; "" = désactivé (défaut, cf. A7)
ARCHITECT_MODEL = ""           # B4 : modèle "architecte" (planifie, lecture seule) ; "" = modèle courant
EDITOR_MODEL = ""              # B4 : modèle "éditeur" (exécute le plan, tous outils) ; "" = modèle courant
EMBED_MODEL = "bge-m3"         # B5 : modèle d'embedding pour search_semantic (déjà installé)
VISION_MODEL = ""              # B6 : modèle multimodal pour analyze_image ; "" = auto-détection

# ── Langue de l'interface / UI language ───────────────────────────────────────
# ── Langue de l'interface / UI language ─────────────────────────────────────
LANG = "en"
SUPPORTED_LANGS = {"en": "English", "fr": "Français"}

# ── Contexte ──────────────────────────────────────────────────────────────────
# Ollama utilise 16384 tokens de contexte par défaut si on ne demande rien —
# quel que soit le max réel du modèle (ex: qwen3:8b supporte 40960). Une
# session agentique à plusieurs tours d'outils (surtout avec un modèle qui
# "thinke", ce qui compte aussi dans le contexte) peut dépasser 16K en une
# dizaine d'échanges, provoquant un context-shift et des réponses vides ou
# incohérentes. On demande explicitement le max du modèle, plafonné pour ne
# pas exploser la RAM sur les modèles à contexte énorme (256K/1M).
SAFE_NUM_CTX = 65536   # plafond de contexte demandé à Ollama (doublé de 32768 → 65536 le 2026-08-05 sur demande ; réglable via /parameters)

# ── Paramètres de génération Ollama ───────────────────────────────────────────
# Paramètres de génération Ollama et de recherche web — tous ajustables en direct
# via /parameters. Valeurs par défaut = défauts standards d'Ollama / de l'agent
# tel qu'il se comportait avant l'ajout du menu (aucun changement de comportement
# tant que l'utilisateur n'a rien touché).
GEN_TEMPERATURE     = 0.8
GEN_TOP_P           = 0.9
GEN_TOP_K           = 40
GEN_REPEAT_PENALTY  = 1.1
GEN_NUM_PREDICT     = -1     # -1 = pas de limite
GEN_SEED            = -1     # -1 = aléatoire
STREAM_FINAL              = "on"    # "on"/"off" — streame la réponse finale en direct (B2) ; "off" = ancien comportement bufferisé (repli si un modèle régresse sur le tool-calling en streaming)

# ── Recherche web ─────────────────────────────────────────────────────────────
SEARXNG_URL   = "http://localhost:8080/search"
SEARCH_LANGUAGE          = "en-US"  # "auto" = laisse l'instance SearXNG décider
SEARCH_RESULT_CAP        = 5        # résultats gardés par search_web
DEEP_SEARCH_FETCH_COUNT  = 3        # pages réellement ouvertes par search_web_deep
DEEP_SEARCH_CHAR_BUDGET  = 2000     # caractères de texte propre gardés par page
DEEP_SEARCH_TIMEOUT      = 5        # secondes avant d'abandonner une page
DEEP_SEARCH_THIN_THRESHOLD = 200    # caractères — sous ce seuil, texte jugé "coquille JS", escalade vers le rendu navigateur
RSS_ENABLED               = "on"    # "on"/"off" — ajoute des flux RSS de presse (vraies dates, pas de JS/anti-bot) pour les requêtes actualité
# Flux RSS de presse majeure vérifiés vivants le 2026-08-02 — voir agentic_contexte.md.
# Reuters et AP n'ont plus de flux RSS direct depuis 2020 : on passe par le flux de
# recherche Google News (qui référence uniquement des articles de ce domaine),
# solution documentée et vérifiée fonctionnelle, pas une invention.
NEWS_RSS_FEEDS = [
    ("Reuters", "https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com"),
    ("AP", "https://news.google.com/rss/search?q=when:24h+allinurl:apnews.com"),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml"),
    ("The Guardian World", "https://www.theguardian.com/world/rss"),
    ("Fox News World", "https://moxie.foxnews.com/google-publisher/world.xml"),
]
# Bare "Mozilla/5.0" n'est ni un vrai navigateur (aucun navigateur réel n'envoie
# ce token seul — c'est un signal "bot" en soi) ni une identification honnête.
# On utilise une chaîne de navigateur récente et complète pour se fondre dans le
# trafic normal ; le respect de robots.txt (voir _check_robots) est le mécanisme
# de conformité réel, pas la chaîne User-Agent elle-même.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
SEARCH_CACHE_TTL = 300  # secondes — évite de re-frapper SearXNG pour une requête identique récente

# ── Compaction de contexte ────────────────────────────────────────────────────
# Compaction de contexte (v3.0, recherche-backed — voir agentic_contexte.md). "off" par
# défaut : la communauté se plaint surtout d'une compaction qui détruit le contexte de
# travail en surprise ; on ne l'active jamais sans le vouloir. Déclenchée sur le VRAI compte
# de tokens du prompt (prompt_eval_count renvoyé par Ollama), pas une estimation.
AUTO_COMPACT              = "off"   # "on"/"off" — résume automatiquement l'historique ancien quand le contexte se remplit
COMPACT_THRESHOLD_PCT     = 70      # % de num_ctx atteint avant de compacter (déclenchement précoce recommandé, pas 95%)
COMPACT_KEEP_TURNS        = 3       # nombre de tours utilisateur récents gardés mot pour mot (le reste est résumé)
COMPACT_TOOL_TRUNC        = 800     # caractères : les vieux résultats d'outils plus longs sont tronqués (nettoyage sans perte d'abord)

# ── RAG local (search_semantic) ───────────────────────────────────────────────
SEMANTIC_CHUNK_LINES = 60      # B5 : taille des morceaux indexés (lignes)
SEMANTIC_TOP_K = 5             # B5 : nombre de morceaux les plus proches renvoyés

# ── Garde-fous de boucle & budgets de relance ─────────────────────────────────
MAX_TOOL_ROUNDS   = 25  # garde-fou : évite une boucle d'appels d'outils sans fin
MAX_VERIFY_NUDGES = 2   # nombre max de relances auto "vérifie ton édition" par tour utilisateur
MAX_THIN_SEARCHES = 4   # au-delà, on force le modèle à arrêter de chercher dans le vide
MAX_DEEP_SEARCHES = 6   # au-delà, on force l'arrêt même si les résultats sont réels — évite
                         # une chaîne de search_web_deep (coûteux) qui ne converge jamais vers
                         # une réponse (observé en pratique : v2.9.15, 7+ appels sur un
                         # sous-sujet auto-affiné jusqu'au timeout, chaque résultat réel mais
                         # inexploitable — le coupe-circuit "résultats vides" ne se déclenche
                         # jamais dans ce cas puisque le contenu n'est jamais réellement vide)
MAX_EMPTY_RETRIES = 2   # nombre de relances avant d'abandonner sur une réponse finale vide
MAX_FAKE_TOOLCALL_RETRIES = 2  # relances avant d'abandonner sur un appel d'outil écrit en texte brut
MAX_TEMPLATE_PARSER_RETRIES = 2  # relances sur l'erreur Ollama "Unable to generate parser for
                                  # this template" — bug confirmé côté Ollama (registry #16988),
                                  # observé de façon reproductible en cours de session (pas
                                  # seulement au premier appel) sur des GGUF hf.co avec parser de
                                  # tool-calling auto-généré (ex: Ornith). Simple relance de la
                                  # même requête plutôt qu'un abandon complet du tour — voir
                                  # agentic_contexte.md pour le détail de la découverte.
MAX_XML_PARSE_RETRIES = 2  # relances sur "XML syntax error" lors du parsing d'un tool-call
                            # (ex: "element <parameter> closed by </function>") — bug distinct
                            # de #16988 : ici Ollama a bien généré un parser, mais le *modèle*
                            # dérive de son propre format de tool-call attendu (famille Qwen3.5/
                            # 3.6, confirmé upstream ollama/ollama#14834, #16383, #16810 — le
                            # modèle émet occasionnellement un wrapper XML différent de celui que
                            # son propre chat_template documente). Aucun correctif amont
                            # disponible au 2026-08-04 (issues ouvertes, pas de fix côté Ollama) ;
                            # une relance de la même requête est la seule intervention possible
                            # côté client, même logique que MAX_TEMPLATE_PARSER_RETRIES mais sur
                            # une signature d'erreur différente (confirmé en conditions réelles
                            # sur qwen3.5:4b — voir agentic_contexte.md, section "7 sedecies").
MAX_JSON_TRUNCATION_RETRIES = 2  # relances sur "unexpected end of JSON input" — troisième signature
                                  # d'échec Ollama distincte des deux ci-dessus, trouvée le 2026-08-04
                                  # (benchmark "construire un script/jeu original" sur Ornith) : au
                                  # lieu d'un mauvais parser (#16988) ou d'une dérive de format XML
                                  # (#14834/#16383), ici le JSON brut des arguments d'un tool call
                                  # (observé sur write_file, contenu volumineux — un fichier ~14 Ko en
                                  # un seul appel) est tronqué en cours de génération côté llama-server
                                  # avant la fermeture des accolades. Message Go standard
                                  # (encoding/json) pour un flux JSON incomplet — pas un problème côté
                                  # client, rien à corriger dans la requête envoyée. Même traitement :
                                  # relance de la requête identique, puis repli propre si ça persiste.
MAX_STUCK_SEARCH_NUDGES = 2  # relances "cherche sur le web" quand une vérification (run_command/
                              # lint_file/run_tests) échoue avec exactement la même erreur qu'à la
                              # tentative précédente malgré une édition entre les deux — signal
                              # concret que le modèle devine plutôt que de progresser. Le modèle a
                              # search_web mais rien avant ceci ne le poussait explicitement à
                              # l'utiliser sur un problème de debug plutôt que sur une recherche
                              # factuelle — voir agentic_contexte.md, section "systemic issue".
MAX_CITATION_NUDGES = 1  # relances "cite tes sources" — nudge doux, pas un gate strict
MAX_GROUNDING_NUDGES = 1  # relances "n'invente pas un résultat d'outil hypothétique" — observé en
                           # pratique (v2.9.16, test T8) : un modèle qui n'appelle aucun outil mais
                           # décrit "ce que get-structured-content renverrait" avec des valeurs
                           # inventées précises (population, dates...), présentées comme un exemple
                           # plausible plutôt que clairement inventées
MAX_GROUNDING_CHECK_NUDGES = 1  # relances "ces valeurs n'apparaissent dans aucun résultat d'outil de
                                 # ce tour" — vérification déterministe post-réponse (_grounding_check),
                                 # sans LLM : extrait les jetons durs (nombres ≥2 chiffres, dates, URLs,
                                 # noms propres entre guillemets) de la réponse finale et les cherche en
                                 # sous-chaîne dans les résultats bruts d'outils du tour. Nudge, jamais un
                                 # gate — les valeurs dérivées légitimement (sommes, conversions) ou
                                 # paraphrasées peuvent passer/faux-positiver, d'où le plafond à 1.
MAX_CLAIM_ACTION_NUDGES = 1  # relances "tu affirmes avoir corrigé/vérifié mais aucune édition/vérification
                              # n'a eu lieu ce tour" — aurait rattrapé le "fix" de gpt-oss sur un fichier
                              # bit-à-bit identique et le "citations ajoutées" de gemma-26B sans écriture.
MAX_READONLY_REFUSALS = 3    # B4 : au-delà de ce nombre d'outils d'écriture refusés en phase architecte

# ── Divers outils ─────────────────────────────────────────────────────────────
MAX_BACKGROUND_PROCESSES = 5
LARGE_WRITE_LINES = 80  # au-delà, on suggère l'écriture en morceaux (write_file + append_file)
MEMORY_SOFT_LIMIT = 3000  # avertissement, pas un blocage — voir docstring de memory_write


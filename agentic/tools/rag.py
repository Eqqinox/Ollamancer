"""Agentic_1A — local RAG (semantic code search).

`search_semantic` answers questions like "where is the retry logic handled?" — matching by
meaning rather than by name, which grep and even AST analysis cannot do.

**Deliberately dependency-free.** Embeddings come from the already-installed `bge-m3` via
`ollama.embed`, and the index is a stdlib `sqlite3` file in `.agentic/`. No ChromaDB, no
FAISS, no numpy — vectors are stored as `array('f')` blobs and compared with a hand-written
cosine over a brute-force scan. At single-project scale that is entirely adequate, and it
keeps the agent installable with four core dependencies.

**Re-indexing is incremental**, keyed on file mtime: only new or modified files are
re-embedded, so the cost after the first run is proportional to what changed rather than to
the size of the project.
"""

import array
import hashlib
import math
import os
import sqlite3
from pathlib import Path

import ollama

from agentic import config, state
from agentic.safety import _audit
from agentic.tools.codenav import _iter_source_files

# ── RAG local / recherche sémantique (B5) ───────────────────────────────────────
# The third search pillar alongside search_in_files (exact text) and
# find_references (symboles) : la recherche *conceptuelle*. Embeddings locaux via
# the already-installed bge-m3 model (ollama.embed), stored in a stdlib SQLite
# (.agentic/semantic_index.db) ; similarité cosinus en pur Python (aucune dépendance
# added: no numpy, no chromadb, no sqlite-vec, none of which are in this venv). Re-indexing
# is incremental on mtime: only new/modified files are re-embedded.
_SEMANTIC_EXTS = config._REF_SOURCE_EXTS | {".md", ".txt", ".rst", ".toml", ".yaml", ".yml", ".json", ".sh", ".cfg", ".ini"}


def _iter_semantic_files(root: Path):
    count = 0
    for p in root.rglob("*"):
        if p.is_dir() or p.suffix.lower() not in _SEMANTIC_EXTS:
            continue
        if any(part in config._REF_EXCLUDE_DIRS or part == ".agentic" for part in p.parts):
            continue
        yield p
        count += 1
        if count >= 800:  # garde-fou perf
            return


def _chunk_text(text: str) -> list[tuple[int, int, str]]:
    """Split file text into ~SEMANTIC_CHUNK_LINES-line chunks. Returns (chunk_index,
    start_line, chunk_text) tuples. Skips whitespace-only chunks."""
    lines = text.splitlines()
    out = []
    step = max(1, config.SEMANTIC_CHUNK_LINES)
    idx = 0
    for start in range(0, len(lines), step):
        chunk = "\n".join(lines[start:start + step])
        if chunk.strip():
            out.append((idx, start + 1, chunk))
            idx += 1
    return out


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with the local bge-m3 model via Ollama. Tolerates both the
    newer ollama.embed(input=...) response shape and the older embeddings() one. Raises on
    failure so the caller can report that the embedding model isn't available."""
    if not texts:
        return []
    resp = ollama.embed(model=config.EMBED_MODEL, input=texts)
    embs = getattr(resp, "embeddings", None)
    if embs is None and isinstance(resp, dict):
        embs = resp.get("embeddings")
    if embs is None:
        raise RuntimeError("no embeddings returned")
    return [list(e) for e in embs]


def _vec_to_blob(vec) -> bytes:
    return array.array("f", vec).tobytes()


def _blob_to_vec(blob: bytes) -> array.array:
    a = array.array("f")
    a.frombytes(blob)
    return a


def _cosine(a, b) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _open_semantic_db() -> sqlite3.Connection:
    conn = sqlite3.connect(state._SEMANTIC_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS chunks "
                 "(path TEXT, mtime REAL, idx INTEGER, start_line INTEGER, text TEXT, vec BLOB)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON chunks(path)")
    return conn


def _reindex_semantic(conn: sqlite3.Connection) -> int:
    """Incrementally sync the index to disk: re-embed new/changed files (mtime differs),
    drop rows for deleted files. Returns the number of files (re)indexed this call."""
    root = state.PROJECT_ROOT or Path.cwd()
    disk = {str(p): p.stat().st_mtime for p in _iter_semantic_files(root)}
    cur = conn.cursor()
    indexed = {path: mt for path, mt in cur.execute("SELECT DISTINCT path, mtime FROM chunks")}
    for path in list(indexed):
        if path not in disk:
            cur.execute("DELETE FROM chunks WHERE path=?", (path,))
    reindexed = 0
    for path, mt in disk.items():
        if indexed.get(path) == mt:
            continue
        cur.execute("DELETE FROM chunks WHERE path=?", (path,))
        try:
            text = Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        chunks = _chunk_text(text)
        if not chunks:
            continue
        vecs = _embed_texts([c[2] for c in chunks])
        for (idx, start, ctext), vec in zip(chunks, vecs):
            cur.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                        (path, mt, idx, start, ctext, _vec_to_blob(vec)))
        reindexed += 1
    conn.commit()
    return reindexed


def search_semantic(query: str) -> str:
    """Search the project's own files by meaning, not exact text — for questions like
    "where is retry logic handled?" or "which file builds the system prompt?". Complements
    search_in_files (exact text/regex) and find_references (symbol definitions/usages) with
    conceptual retrieval. Files are embedded locally with the bge-m3 model (nothing leaves
    this machine) into a small on-disk index that refreshes automatically when files change.
    Returns the most relevant chunks with their file path and starting line.
    Args:
        query: A natural-language description of what you are looking for
    """
    if state._SEMANTIC_DB is None:
        return "Semantic index not initialized (no project root)."
    try:
        conn = _open_semantic_db()
    except Exception as e:
        return f"Semantic index error: {e}"
    try:
        try:
            _reindex_semantic(conn)
        except Exception as e:
            return (f"Could not build the semantic index — the embedding model '{config.EMBED_MODEL}' "
                    f"may not be installed (ollama pull {config.EMBED_MODEL}). Details: {type(e).__name__}: {e}")
        try:
            qvec = _embed_texts([query])[0]
        except Exception as e:
            return f"Could not embed the query ({type(e).__name__}: {e}). Is '{config.EMBED_MODEL}' installed?"
        rows = conn.execute("SELECT path, start_line, text, vec FROM chunks").fetchall()
        if not rows:
            return "No indexable project files found to search semantically."
        root = state.PROJECT_ROOT or Path.cwd()
        scored = []
        for path, start, text, vec in rows:
            scored.append((_cosine(qvec, _blob_to_vec(vec)), path, start, text))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:max(1, config.SEMANTIC_TOP_K)]
        out = [f"Top {len(top)} semantically-closest chunks for: {query}"]
        for score, path, start, text in top:
            try:
                rel = str(Path(path).relative_to(root))
            except ValueError:
                rel = path
            snippet = text.strip()
            if len(snippet) > 500:
                snippet = snippet[:500] + "…"
            out.append(f"\n── {rel}:{start}  (similarity {score:.2f}) ──\n{snippet}")
        return "\n".join(out)
    finally:
        conn.close()

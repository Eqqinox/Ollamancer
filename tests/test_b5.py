import os, tempfile, pathlib, re
import agent
from agentic import config

# Deterministic hashing embedder (bag-of-words over 64 buckets) — same process, so query
# and chunks share the same mapping; word overlap → high cosine. No real model needed.
DIM = 64
def fake_embed(texts):
    out = []
    for t in texts:
        v = [0.0] * DIM
        for w in re.findall(r"[a-z]+", t.lower()):
            v[hash(w) % DIM] += 1.0
        out.append(v)
    return out
agent._embed_texts = fake_embed

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); agent.PROJECT_ROOT = d.resolve()
agent._SEMANTIC_DB = d / "sem.db"

# 0. chunking
chunks = agent._chunk_text("\n".join(f"line{i}" for i in range(130)))
config.SEMANTIC_CHUNK_LINES = 60
chunks = agent._chunk_text("\n".join(f"line{i}" for i in range(130)))
assert [c[1] for c in chunks] == [1, 61, 121], chunks   # start lines
assert len(chunks) == 3

# project files
(d / "retry.py").write_text("def retry():\n    # retry retry retry backoff attempts loop again retry\n    pass\n")
(d / "colors.py").write_text("def paint():\n    blue red green yellow pixels canvas draw color\n    pass\n")

# 1. semantic search ranks the retry file first for a retry query
res = agent.search_semantic("where is retry logic and backoff handled")
assert "retry.py" in res, res
first_block = res.split("── ", 1)[1]           # first result block after the header
assert first_block.startswith("retry.py"), first_block
assert res.index("retry.py") < res.index("colors.py"), res

# 2. incremental reindex: nothing changed → 0 reindexed
conn = agent._open_semantic_db()
assert agent._reindex_semantic(conn) == 0
conn.close()

# 3. change one file (+bump mtime) → exactly 1 reindexed
(d / "colors.py").write_text("def helper():\n    retry retry retry backoff attempts loop\n")
os.utime(d / "colors.py", (9999999999, 9999999999))
conn = agent._open_semantic_db()
n = agent._reindex_semantic(conn)
assert n == 1, n
conn.close()

# 4. delete a file → its rows are dropped on next reindex
(d / "retry.py").unlink()
conn = agent._open_semantic_db()
agent._reindex_semantic(conn)
paths = {row[0] for row in conn.execute("SELECT DISTINCT path FROM chunks")}
conn.close()
assert not any("retry.py" in p for p in paths), paths

# 5. embedding-model-missing path returns a clear message, never crashes
def boom(texts): raise agent.ollama.ResponseError("model 'bge-m3' not found")
agent._embed_texts = boom
msg = agent.search_semantic("anything")
assert "bge-m3" in msg and ("not be installed" in msg or "installed" in msg), msg

# 6. cosine sanity
assert abs(agent._cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-6
assert abs(agent._cosine([1.0, 0.0], [0.0, 1.0])) < 1e-6

# registration
assert agent.search_semantic in agent.TOOLS
assert "search_semantic" in agent._READ_ONLY_TOOL_NAMES
print("B5 ALL PASS")

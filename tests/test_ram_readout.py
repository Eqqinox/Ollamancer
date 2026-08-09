"""The live RAM readout must ask Ollama, not measure process RSS.

Process RSS is the wrong number for the MLX engine: llama.cpp mmaps its weights so they
appear in RSS, while MLX allocates them as Metal unified-memory buffers that are not
attributed to the process. Measured on `gemma4:12b-mlx`, a 7.6 GB model, RSS reported
0.76 GB just after loading and 6.21 GB after generating, while `ollama.ps()` reported
7.6 GB throughout. GGUF was never wrong, which is why the bug survived.

Offline: `ollama.ps` is replaced with fakes, so nothing here needs a server or a model.

    PYTHONPATH="$PWD" python tests/test_ram_readout.py
"""

from types import SimpleNamespace

from agentic import models


def _fake_ps(*sizes_bytes):
    return lambda: SimpleNamespace(models=[SimpleNamespace(size=s) for s in sizes_bytes])


_real_ps = models.ollama.ps
try:
    # 1. A single loaded model reports its real size, in GB.
    models.ollama.ps = _fake_ps(7_600_000_000)
    got = models.ollama_runner_rss_gb()
    assert got is not None and abs(got - 7.6) < 0.01, got

    # 2. Several loaded models sum. The agent loads strictly one at a time, but the
    #    readout should still be right if something else loaded one behind its back.
    models.ollama.ps = _fake_ps(3_400_000_000, 5_200_000_000)
    got = models.ollama_runner_rss_gb()
    assert abs(got - 8.6) < 0.01, got

    # 3. Nothing loaded is None, not 0.0. The caller renders None as "no model resident";
    #    0.0 would be displayed as a model occupying no memory.
    models.ollama.ps = _fake_ps()
    assert models.ollama_runner_rss_gb() is None

    # 4. A missing or broken size field must not raise.
    models.ollama.ps = lambda: SimpleNamespace(models=[SimpleNamespace(size=None)])
    assert models.ollama_runner_rss_gb() is None

    # 5. If ollama.ps() itself fails, fall back to the ps scan rather than crashing the
    #    status line. The fallback returns None here because no runner is running.
    def _boom():
        raise RuntimeError("too old to support ps()")
    models.ollama.ps = _boom
    models.ollama_runner_rss_gb()          # must not raise

    # 6. The fallback still exists and is callable, since it is the only path on an
    #    Ollama predating ollama.ps().
    assert callable(models._runner_rss_gb_via_ps)

finally:
    models.ollama.ps = _real_ps

print("test_ram_readout: ALL PASS")

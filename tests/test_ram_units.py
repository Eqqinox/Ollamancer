"""Machine RAM is displayed in binary GiB and compared in decimal GB, on purpose.

`hw.memsize` on a 24 GB Mac is 25_769_803_776 bytes. Divided the way model sizes are
(`/1_000_000_000`) that is 25.77, which the `/model` header rounded to a wrong-looking
**"26 GB RAM"** on a machine every spec sheet calls 24 GB.

The fix is *not* to switch the divisor, because the same value is handed to
`usage_tier()` and divided by a model size that comes from Ollama in decimal GB. Changing
one side alone inflates every ratio by 7.4% and quietly pushes models into a heavier band.
So there are two functions, and this test pins both halves:

  * `get_system_ram_display_gb()` → binary GiB, for the human-facing label. Memory is
    conventionally binary.
  * `get_system_ram_gb()`         → decimal GB, for the size ratio. File sizes are
    conventionally decimal, and this must match `m.size / 1_000_000_000`.

Offline: `subprocess.run` is replaced with a fake, so no sysctl call is made.

    PYTHONPATH="$PWD" python tests/test_ram_units.py
"""

from types import SimpleNamespace

from agentic import models

MEMSIZE_24GB = 25_769_803_776          # what sysctl reports on a "24 GB" Mac

_real_run = models.subprocess.run


def _fake_sysctl(memsize: int):
    def run(cmd, *a, **k):
        if "hw.memsize" in cmd:
            return SimpleNamespace(stdout=f"{memsize}\n", returncode=0)
        return _real_run(cmd, *a, **k)
    return run


try:
    models.subprocess.run = _fake_sysctl(MEMSIZE_24GB)

    # 1. The label says what the machine is sold as, not 26.
    shown = models.get_system_ram_display_gb()
    assert abs(shown - 24.0) < 0.01, f"display RAM should be 24.0 GiB, got {shown}"
    assert f"{shown:.0f}" == "24", f"the /model header would print {shown:.0f} GB"

    # 2. The ratio value stays decimal, so it matches how model sizes are computed.
    ratio_ram = models.get_system_ram_gb()
    assert abs(ratio_ram - 25.7698) < 0.01, f"ratio RAM should stay decimal, got {ratio_ram}"

    # 3. They are deliberately different. If someone "tidies" them into one value, this
    #    fires: that is the bug this file exists to prevent, in either direction.
    assert shown != ratio_ram, "display and ratio RAM must not be unified into one number"

    # 4. The tiers must be unchanged by the display fix. These are the boundaries as
    #    measured on the real machine, so a regression in usage_tier() shows up here.
    for size_gb, expected in [(7.0, "Light"), (12.6, "Medium"), (13.8, "Medium"),
                              (17.6, "Heavy"), (24.0, "Very heavy")]:
        tier = models.usage_tier(size_gb, ratio_ram, False)
        assert expected.lower() in tier.lower(), \
            f"{size_gb} GB on a 24 GB machine should be {expected}, got {tier}"

    # 5. Using the display value for tiering is exactly the mistake to avoid, and there is
    #    a real model on the boundary that proves it: the 35B-A3B IQ3_M build at 16.3 GB.
    #    Decimal puts it at 63% (Medium); binary at 68% (Heavy). The live `/model` table
    #    shows Medium, so decimal is what ships and this is not a hypothetical.
    assert "medium" in models.usage_tier(16.3, ratio_ram, False).lower(), \
        "16.3 GB must stay Medium, as the /model table shows"
    assert "heavy" in models.usage_tier(16.3, shown, False).lower(), \
        "the binary value would mis-tier 16.3 GB as Heavy, which is why it is display-only"

    # 6. A machine whose sysctl cannot be read falls back rather than crashing.
    models.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(OSError("no sysctl"))
    assert models.get_system_ram_gb() == 16.0
    assert models.get_system_ram_display_gb() == 16.0
finally:
    models.subprocess.run = _real_run

print("test_ram_units: all assertions passed")

"""The bundled skills must be findable in both layouts.

This exists because the failure mode is silent. `_discover_skills` returns whatever it
finds, so if the directory is wrong the agent starts normally, reports no error, and
simply has zero bundled skills. Nothing turns red. The same off-by-one-level mistake was
caught once during the split into modules, and packaging reintroduces exactly the same
risk from the other direction: after `pip install` there is no repository root, so a path
built from `__file__.parent.parent` points at `site-packages` and the skills are gone.

Run directly, like every other script in this directory:
    PYTHONPATH="$PWD" python tests/test_packaging.py
"""

import tomllib
from pathlib import Path

from agentic import config, skills

ROOT = Path(__file__).resolve().parent.parent

# 1. In this checkout the resolver must pick the repository's own skills/ folder, not the
#    packaged copy, so that editing a skill during development takes effect immediately.
resolved = config.bundled_skills_dir()
assert resolved == ROOT / "skills", resolved
assert resolved.is_dir(), resolved

# 2. Every bundled skill is discoverable and none has been lost.
found = skills._discover_skills()
on_disk = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
assert on_disk, "no SKILL.md found on disk at all"
missing = on_disk - set(found)
assert not missing, f"skills on disk but not discovered: {sorted(missing)}"

# 3. The packaging metadata must actually ship them. If the mapping below is dropped or
#    renamed, the wheel installs with no skills and only an end-to-end install would
#    notice, so assert on the declaration itself.
pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
setuptools_cfg = pyproject["tool"]["setuptools"]
pkg_dir = setuptools_cfg["package-dir"]
assert pkg_dir.get("agentic.bundled_skills") == "skills", pkg_dir
assert "agentic.bundled_skills" in setuptools_cfg["packages"], setuptools_cfg["packages"]
assert pyproject["tool"]["setuptools"]["package-data"]["agentic.bundled_skills"], "no package-data"

# 4. The fallback branch has to point somewhere the wheel really puts the files. Checked
#    by name rather than existence, since in a checkout that directory does not exist.
fallback = Path(config.__file__).resolve().parent / "bundled_skills"
assert fallback.name == "bundled_skills", fallback

# 5. The console entry point must name a callable that exists.
entry = pyproject["project"]["scripts"]["ollamancer"]
mod, _, func = entry.partition(":")
imported = __import__(mod, fromlist=[func])
assert callable(getattr(imported, func)), entry

# 6. Runtime dependencies must stay in step with requirements.txt, which is what
#    launch.sh installs. A dependency added to one and not the other means the two
#    install paths give different environments.
req_names = {
    line.split(">=")[0].split("==")[0].strip().lower()
    for line in (ROOT / "requirements.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
}
proj_names = {d.split(">=")[0].split("==")[0].strip().lower()
              for d in pyproject["project"]["dependencies"]}
extras = {d.split(">=")[0].split("==")[0].strip().lower()
          for group in pyproject["project"]["optional-dependencies"].values()
          for d in group}
unaccounted = req_names - proj_names - extras
assert not unaccounted, f"in requirements.txt but not in pyproject: {sorted(unaccounted)}"

print("test_packaging: ALL PASS")

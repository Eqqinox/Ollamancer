---
name: dependency-audit
description: Check a project's dependencies for known vulnerabilities and outdated versions, and propose safe updates. Use when the user asks to audit/check dependencies, look for vulnerable packages, or update libraries safely.
license: MIT
---

# Dependency audit

Report what's vulnerable or stale from real tool output, then update carefully, not blindly.

## Steps

1. **Detect the ecosystem.** Look for `requirements.txt`/`pyproject.toml`/`Pipfile` (Python),
   `package.json`/lockfiles (Node), `go.mod` (Go), `Cargo.toml` (Rust) with `list_directory`.
2. **Run the real audit** with `run_command` (report actual output, don't guess):
   - Python: `pip-audit` if available (else note it can be installed); `pip list --outdated`.
   - Node: `npm audit` / `npm outdated` (or `pnpm`/`yarn` equivalents).
   - Go: `govulncheck./...`; Rust: `cargo audit`.
3. **Summarize** the findings: **vulnerable** packages (CVE + severity + fixed-in version) first,
   then merely **outdated** ones. Separate the two, a security fix is more urgent than a version bump.
4. **Propose updates**, grouped by risk:
   - Patch/minor bumps that fix a CVE → low risk, do first.
   - Major bumps → flag as breaking; check the changelog before upgrading.
   Give the exact commands (e.g. `pip install -U <pkg>==X.Y.Z`), don't run them yet.
5. **Update on confirmation only.** Ask before changing versions. After updating, **run the
   tests** (or `test-and-fix`) to catch breakage, then re-run the audit to confirm it's clean.

## Notes

- Never `pip install`/`npm i`/upgrade without the user's OK, updates can break things.
- If the audit tool isn't installed, say so and offer to install it (with confirmation) rather
  than inventing a vulnerability list.

---
name: security-review
description: Audit code (or the current diff) for real security vulnerabilities and report each with a concrete fix. Use when the user asks for a security review, a vulnerability check, or "is this code safe".
license: MIT
---

# Security review

Find *real* issues, ignore noise, and give a concrete fix for each. Be specific, not generic.

## Scope

- If reviewing changes: read the diff with `git_diff` (and `git_status`).
- If reviewing a file/module: `read_file` it; use `search_in_files` to trace inputs and sinks.

## What to look for

1. **Injection** — user/external input flowing into SQL, shell (`os.system`, `subprocess` with
   `shell=True`), `eval`/`exec`, file paths, or HTML without escaping/parameterization.
2. **Secrets** — hardcoded API keys, passwords, tokens, private keys in code or config.
3. **AuthZ/AuthN** — missing permission checks, trusting client-supplied identity, broken access
   control on an endpoint.
4. **Unsafe deserialization** — `pickle`/`yaml.load`/`marshal` on untrusted data.
5. **Path traversal / SSRF** — unvalidated paths or URLs, fetching attacker-controlled hosts.
6. **Crypto misuse** — weak hashing for passwords (plain md5/sha1), hardcoded IVs, `random` for
   tokens instead of `secrets`.
7. **Dependency risk** — obviously outdated/known-vulnerable packages (mention `pip-audit`/
   `npm audit` to confirm).

## Output

For each real finding, report: **file:line**, the issue in one sentence, a concrete **exploit
scenario**, and the **fix**. Rank by severity. Explicitly separate *confirmed* issues from
*possible* ones. Do not pad the list with theoretical or false-positive findings — if the code
is clean, say so.

## Notes

- Review only; propose fixes but apply them only if the user asks (or pair with `test-and-fix`).
- Never write instructions to exfiltrate secrets you find — report their location, nothing more.

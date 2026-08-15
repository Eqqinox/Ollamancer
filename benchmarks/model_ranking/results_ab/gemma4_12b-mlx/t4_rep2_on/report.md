## Timeline
On May 11, 2026, the threat actor TeamPCP launched a coordinated supply chain attack known as "Mini Shai Hulud" [1]. The campaign targeted over 170 packages across both the npm and PyPI ecosystems, including prominent libraries in the TanStack, Mistral AI, and OpenSearch communities [1]. Subsequent reports identified that malicious versions of @antv data-visualization packages were published to exploit downstream dependencies like echarts-for-react, which sees millions of weekly downloads [2].

## How it spreads
The worm utilizes a multi-stage infection vector primarily targeting CI/CD environments. It leverages GitHub Actions "pull_request_target" triggers and OIDC token extraction to forge valid publish tokens with SLSA Build Level 3 provenance attestations [1]. The payload, often found in files like `router_init.js` or `setup.mjs`, executes during the `npm install` process via a preinstall hook [2].

Once active, the malware performs environment profiling and identifies GitHub Actions runners on Linux systems [2]. It employs several techniques for credential theft:
- **Multi-Platform Extraction:** The payload targets secrets from GitHub (GITHUB_TOKEN), Amazon Web Services (via Instance Metadata Service), HashiCorp Vault (searching over 12 token paths), and Kubernetes service account tokens [2].
- **Memory Scraping:** It identifies the Runner.Worker PID via `/proc` scanning to extract secret values directly from process memory, bypassing standard secret masking [2].
- **Persistence:** The worm injects hooks into VS Code settings (`.vscode/tasks.json`) and Claude Code configurations (`~/.claude/settings.json`) to ensure re-execution upon IDE launch or system reboot [1].

## Remediation steps
Organizations should prioritize the following actions to mitigate impact:
- **Audit & Cleanup:** Scan `node_modules` for unauthorized files such as `router_init.js`, `setup.mjs`, or `transformers.pyz`. Check configuration files (`.vscode/tasks.json` and `~/.claude/settings.json`) for suspicious persistence hooks [1].
- **Credential Rotation:** Immediately rotate all GitHub Personal Access Tokens, npm publish tokens, AWS access keys, and HashiCorp Vault tokens if a compromise is suspected [1].
- **System Hardening:** Disable unauthorized system services (e.g., `gh-token-monitor.service`) and implement DNS-level blocking for known malicious domains like `api.masscan.cloud` [1].
- **Dependency Management:** Utilize lockfiles to ensure dependency integrity and consider pinning packages to specific, verified hashes to prevent automatic updates to compromised versions [1].

## Sources
1. https://expel.com/blog/mini-shai-hulud-cross-ecosystem-supply-chain-worm-targeting-npm-pypl/
2. https://www.microsoft.com/en-us/security/blog/2026/05/20/mini-shai-hulud-compromised-antv-npm-packages-enable-ci-cd-credential-theft/

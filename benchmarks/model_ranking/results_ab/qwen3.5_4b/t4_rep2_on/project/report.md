
## Timeline

The original Shai-Hulud worm was first reported in September 2025, where Unit 42 investigated a novel self-replicating attack compromising hundreds of npm packages [1]. In early November 2025, the campaign escalated to "Shai-Hulud 2.0," affecting over 25,000 malicious repositories across approximately 350 unique users on GitHub as of late November 2025, threat actor TeamPCP launched a coordinated attack dubbed "Mini Shai Hulud" that compromised over 170 npm and PyPI packages spanning the TanStack, Mistral AI, and OpenSearch ecosystems [3][4].

## How it spreads

Shai-Hulud operates as an automated self-replicating worm. The initial compromise often stems from credential-harvesting phishing campaigns spoofing npm to deceive developers into updating multi-factor authentication options [1][5]. Once access is gained, the malware deploys post-install or pre-install scripts that scan for sensitive credentials including .npmrc files and environment variables containing GitHub Personal Access Tokens (PATs), AWS IAM keys, Google Cloud Platform tokens, Microsoft Azure API keys, HashiCorp Vault tokens, and Kubernetes secrets [1][5].

The worm exfiltrates harvested data to an actor-controlled endpoint by programmatically creating a new public GitHub repository named "Shai-Hulud" under the victim's account with stolen credentials committed publicly [1]. It then uses these compromised npm tokens to authenticate as victims on the registry, identifying other packages maintained by those developers and injecting malicious code before publishing updated versions—enabling exponential propagation without direct actor intervention [5][6].

Mini Shai Hulud employs workflow hijacking via GitHub Actions "pull_request_target" triggers combined with OIDC token extraction to forge valid publish tokens. Compromised package versions contain obfuscated JavaScript files (router_init.js or setup.mjs) that profile the environment and launch modular credential stealers [4][6]. The malware attempts self-propagation by locating npm tokens bypassing 2FA, infecting other packages from same maintainers while injecting persistence hooks into Claude Code and VS Code settings to survive reboots [5].

## Remediation steps

Organizations should audit systems for router_init.js in node_modules or suspicious persistence entries in .vscode/tasks.json and ~/.claude/settings.json before rotating all compromised credentials including GitHub PATs, npm publish tokens, AWS access keys, HashiCorp Vault tokens, and Kubernetes secrets [4][6]. Unauthorized system services such as gh-token-monitor.service should be disabled immediately. DNS-level blocking must implement for api.masscan.cloud to prevent data exfiltration attempts via the decentralized Session Protocol (getsession.org) used by Mini Shai Hulud to evade traditional detection methods [5][6]. Dependencies should be pinned using lockfiles with specific verified hashes, and affected packages removed from production environments pending verification of clean versions.

## Sources

1. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
3. https://expel.com/blog/mini-shai-hulud-cross-ecosystem-supply-chain-worm-targeting-npm-pypl/
5. https://www.akamai.com/blog/security-research/mini-shai-hulud-worm-returns-goes-public

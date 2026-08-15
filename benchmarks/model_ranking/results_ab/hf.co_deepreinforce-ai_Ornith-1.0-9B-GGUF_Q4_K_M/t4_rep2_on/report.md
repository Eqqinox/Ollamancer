# Shai-Hulud npm Supply-Chain Worm

## Timeline

The "Shai-Hulud" campaign is a self-replicating supply-chain worm that first appeared in the npm ecosystem around mid-September 2025. StepSecurity published an initial report on September 15, documenting compromise of over 500 packages [1]. CISA issued its own alert on September 23, confirming the scale and providing remediation guidance [4]. By late November/December 2025, a second wave — "Shai-Hulud 2.0" — was detected by Microsoft Security Research, having compromised over 700 packages and created more than 27,000 malicious GitHub repositories under the operator name "The Second Coming" [6]. In May 2026, a further resurgence called "Mini Shai-Hulud" expanded across both npm and PyPI registries simultaneously, affecting 170+ npm packages in total [8].

## How it spreads

The worm enters developer environments through the `preinstall` script embedded in compromised package.json files. The first wave used a preinstall named `set_bun.js`, which scoped an environment for the Bun runtime; if Bun was not present, the script installed it automatically. Once executed, the bundled `bun_environment.js` downloaded and installed a GitHub Actions Runner archive containing TruffleHog — a credential-harvesting tool that scanned local systems for stored cloud API keys (AWS, GCP, Azure) and GitHub Personal Access Tokens [2]. The stolen credentials were then exfiltrated to an attacker-controlled endpoint and uploaded publicly to a repository named "Shai-Hulud" via the GitHub `user/repos` API [4].

The self-replication mechanism was the most dangerous aspect of the campaign. After harvesting credentials, the worm authenticated to the npm registry as the compromised developer's account, injected malicious code into other packages, and published those poisoned versions back to the registry — effectively using each victim as a stepping stone for further compromise [3]. Shai-Hulud 2.0 refined this chain by adding commit signatures attributed to "Linus Torvalds" to evade basic trust checks, while Mini Shai-Hulud (May 2026) introduced triple-obfuscated credential stealers and targeted the `@tanstack/setup` optional dependency as a new infection vector [8].

## Remediation steps

CISA recommended that organizations immediately rotate all developer credentials for GitHub, npm, AWS, GCP, and Azure accounts. Organizations should also mandate phishing-resistant multifactor authentication on every developer account [4]. A full dependency review is necessary: teams must check `package-lock.json` or `yarn.lock` files to identify affected packages at any depth in the dependency tree, including nested transitive dependencies [4]. Pinning npm package versions to known-safe releases produced before September 16, 2025 provides a temporary containment measure for the first wave [4].

Network-level controls include blocking outbound connections to `webhook.site` domains and monitoring firewall logs for suspicious domain activity. GitHub security should be hardened by removing unnecessary apps and OAuth applications, auditing repository webhooks and secrets, enabling branch protection rules, activating Secret Scanning alerts, and turning on Dependabot security updates [4]. Microsoft Defender introduced dedicated detection alerts — "Sha1-Hulud Campaign Detected – Possible command injection to exfiltrate credentials" — which correlate endpoint telemetry with runtime anomalies for faster identification of compromised devices [6].

## Sources

[1] Ashish Kurmi, StepSecurity: https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised
[2] Palo Alto Networks Unit 42: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
[3] CISA Alert (September 23, 2025): https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[4] Microsoft Security Blog – Shai-Hulud 2.0 guidance (December 9, 2025): https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/
[6] Zscaler – Shai-Hulud V2 poses risk to npm supply chain: https://www.zscaler.com/blogs/security-research/shai-hulud-v2-poses-risk-npm-supply-chain

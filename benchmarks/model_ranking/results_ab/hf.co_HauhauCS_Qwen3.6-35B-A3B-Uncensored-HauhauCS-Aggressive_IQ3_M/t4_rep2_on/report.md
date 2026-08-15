# The Shai-Hulud npm Supply-Chain Worm Campaigns

## Timeline

**September 2025:** Shai-Hulud V1 was first detected, compromising over 500 npm packages through post-install hooks [1]. Within weeks the worm had infected hundreds of widely used libraries including @ctrl/tinycolor and CrowdStrike's npm package [1].

**November 24, 2025:** Shai-Hulud V2 ("The Second Coming") launched, escalating to pre-install phase execution. The campaign compromised over 700 npm packages, created more than 27,000 malicious GitHub repositories, and exposed approximately 14,000 secrets across nearly 500 organizations [3].

**March–April 2026:** Threat group TeamPCP backdoored the axios package (~100 million weekly downloads) in March, then targeted SAP-related npm packages with obfuscated Bun payloads in April. Researchers also attributed compromises of Aqua Security's Trivy scanner and Bitwarden CLI to TeamPCP [5].

**May 11, 2026:** The "Mini Shai-Hulud" wave hit hardest: TeamPCP published 404 malicious versions across 172 npm packages in under six hours. For the first time, a worm produced SLSA Build Level 3 provenance attestations by hijacking legitimate GitHub Actions pipelines rather than exfiltrating credentials externally [5].

**August 2026:** A resurgence began with keyv and cacheable as starting points, affecting over 400 packages across 1,700 versions under the banner "Shai-Hulud: Here We Go Again" [4].

## How it spreads

The worm executes during npm's pre-install lifecycle phase using a lightweight Bun runtime instead of Node.js. It scans for credentials (.npmrc files, GitHub PATs, AWS/GCP/Azure keys), exfiltrates them to public GitHub repositories named "Shai-Hulud," then authenticates back to the npm registry as the compromised developer [2]. From there it enumerates all writable packages owned by that account, injects its payload (setup.mjs loader + math_init.js worm body), bumps the patch version, and publishes infected releases — creating a self-replicating chain reaction.

V2 introduced cross-victim token recycling: stolen npm tokens from one victim are used to infect other victims' packages, forming a botnet-like propagation network [3]. V2 also added persistence via self-hosted GitHub Actions runners and a "dead man's switch" that wipes the user's home directory if exfiltration fails. The May 2026 wave bypassed credential theft entirely by hijacking trusted build pipelines with SLSA Level 3 attestations, making detection harder [5].

## Remediation steps

1. **Pin dependencies** to known-safe versions produced before September 16, 2025 in package-lock.json or yarn.lock files [2].
2. **Rotate all developer credentials**, including npm tokens, GitHub PATs, and cloud API keys [2].
3. **Enforce phishing-resistant MFA** on npm, GitHub, and cloud platforms; use scoped, short-lived tokens with least privilege [3].
4. **Block outbound connections** to webhook.site domains and monitor for suspicious firewall traffic [2].
5. **Audit GitHub Apps, OAuth applications,** repository webhooks, and secrets; remove unnecessary access [2].
6. **Use `npm ci` instead of `npm install`**, apply lockfiles strictly, and reduce dependency surface by auditing unused packages [3].
7. **Clear caches** in artifact repositories and re-install clean versions of affected dependencies [2].
8. **Treat impacted systems as compromised** — isolate, scan, or reimaging where infection occurred [3].

## Sources

[1] CISA Alert: Widespread Supply Chain Compromise Impacting npm Ecosystem (September 23, 2025) — https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[2] Palo Alto Networks Unit 42: "Shai-Hulud" Worm Compromises npm Ecosystem in Supply Chain Attack (Updated September 17, 2025) — https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
[3] Zscaler ThreatLabz: Shai-Hulud V2 Poses Risk To NPM Supply Chain (December 2, 2025) — https://www.zscaler.com/blogs/security-research/shai-hulud-v2-poses-risk-npm-supply-chain
[4] JFrog Research: Shai-Hulud Is Back — August Campaign Analysis — https://research.jfrog.com/post/shai-hulud-is-back-august/
[5] Cloud Security Alliance: Mini Shai-Hulud AI Developer npm Supply Chain Worm (May 14, 2026) — https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/

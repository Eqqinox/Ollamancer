# Shai-Hulud: The npm Supply-Chain Worm Campaigns of 2025–2026

## Timeline

The first self-replicating worm appeared on September 15, 2025 when ReversingLabs identified `rxnt-authentication` v0.0.3 as Patient Zero [1]. Within days more than 40 packages were compromised and CISA issued an alert on September 23 [6]. On November 24 the community detected Shai-Hulud 2.0, which had already infected over 796 unique packages representing roughly 20 million weekly downloads [3]. In February–March 2026 the SANDWORM_MODE variant introduced adaptive CI/CD targeting and typosquatted AI-agent names such as `claud-code` and `opencraw` [4]. On May 11, 2026 TeamPCP launched "Mini Shai-Hulud," publishing 404 malicious versions across 172 npm packages (including the entire @tanstack namespace) in under six hours by chaining three GitHub Actions vulnerabilities to forge SLSA Build Level 3 provenance [5]. A fourth wave hit in August 2026 starting with `keyv` and `cacheable`, affecting more than 400 packages across 1,700 versions [8].

## How it spreads

The worm executes during package install—initially via hijacked postinstall hooks; later variants use preinstall scripts that bootstrap the Bun runtime for obfuscated payloads [2]. The payload scans for npm tokens and GitHub PATs, harvests AWS/GCP/Azure credentials using TruffleHog and cloud metadata endpoints, then uploads secrets to public attacker-controlled repos as dead drops [6]. With a valid npm token it authenticates under the victim's identity, injects its payload (typically `setup.mjs` / `math_init.js`), bumps the patch version, and publishes—turning each compromised developer into a new distribution node [2]. Shai-Hulud 2.0 added self-directed lateral movement: searching public GitHub repos for credentials exfiltrated by other infected machines to reuse them in spreading further [3]. The Mini Shai-Hulud campaign bypassed credential theft entirely in some cases by hijacking the trusted CI/CD pipeline—poisoning a GitHub Actions cache through `pull_request_target`, then extracting OIDC tokens from runner process memory to publish packages with valid SLSA attestations without stealing developer secrets [5].

## Remediation steps

1. **Pin dependencies** — Lock npm package versions to known-safe releases before September 16, 2025; review `package-lock.json` / `yarn.lock` for affected transitive deps [6].
2. **Rotate credentials immediately** — All developer tokens, GitHub PATs, and cloud workload identities reachable from an infected build should be considered compromised [6].
3. **Enforce phishing-resistant MFA** on all developer accounts with publish or write access to public repositories [6].
4. **Audit GitHub Apps & OAuth tokens** — Remove unnecessary integrations; review webhooks, secrets, and Actions runners for unknown entries such as `SHA1Hulud` repos [3][6].
5. **Block outbound connections** to known exfiltration endpoints including `webhook.site` domains used by early variants [6].
6. **Enable branch protection, GitHub Secret Scanning alerts, and Dependabot security updates** on all repositories that publish or consume npm packages [6].

## Sources

[1] StepSecurity, "Shai-Hulud: Self Replicating Worm Compromises 500+ NPM Packages," September 15, 2025 — https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised
[2] Palo Alto Networks Unit 42, "'Shai-Hulud' Worm Compromises npm Ecosystem in Supply Chain Attack," September 17, 2025 — https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
[3] Datadog Security Labs, "The Shai-Hulud 2.0 npm worm: analysis and what you need to know," November 25, 2025 — https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/
[4] Cloud Security Alliance AI Safety Initiative, "Shai-Hulud: npm Worm Targeting AI Developer Toolchains," April 25, 2026 — https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/
[5] Cloud Security Alliance / Tenable, "Mini Shai-Hulud: AI Developer npm Supply Chain Worm," May 14–21, 2026 — https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/
[6] CISA, "Widespread Supply Chain Compromise Impacting npm Ecosystem," September 23, 2025 — https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[7] Microsoft Security Blog, "Shai-Hulud 2.0: Guidance for detecting, investigating, and defending," December 9, 2025 — https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/
[8] JFrog Security Research, "Shai-Hulud is Back: August 2026 Campaign," August 4, 2026 — https://research.jfrog.com/post/shai-hulud-is-back-august/

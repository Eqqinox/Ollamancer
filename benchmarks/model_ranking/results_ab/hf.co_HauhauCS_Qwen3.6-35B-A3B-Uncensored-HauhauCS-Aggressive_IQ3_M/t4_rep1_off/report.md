# The Shai-Hulud npm Worm Campaigns (2025–2026)

## Timeline

The first wave of the Shai-Hulud worm was identified in September 2025, beginning with `@ctrl/tinycolor`, a package receiving over two million weekly downloads [1]. Within days, more than 40 packages were compromised across multiple maintainers' ecosystems. On November 24, 2025, Shai-Hulud 2.0 was discovered, backdooring an estimated 796 npm packages with over 20 million combined weekly downloads [3]. In March 2026, the group compromised `axios` (approximately 100 million weekly downloads) by hijacking a maintainer account [5]. A fresh wave in April 2026 targeted SAP-related packages and introduced obfuscated Bun payloads. On May 11, 2026, threat group TeamPCP launched the "Mini Shai-Hulud" campaign, publishing 404 malicious versions across 172 npm packages in under six hours [5]. In August 2026, JFrog identified a new variant starting with `keyv` and `cacheable`, affecting over 400 packages across more than 1,700 versions [4].

## How it spreads

The worm executes during package installation via preinstall or postinstall hooks. A minified JavaScript bundle is injected into the compromised distribution [2]. On first install, malware scans for npm tokens in `.npmrc` files, GitHub personal access tokens, and cloud keys from AWS, GCP, and Azure [3]. It repurposes tools like TruffleHog to hunt high-entropy secrets on disk. Harvested credentials are exfiltrated to public GitHub repositories created under the victim's account or uploaded via HTTPS endpoints [2].

The self-replication engine makes Shai-Hulud distinctive: with a stolen npm token, it queries the registry for all packages owned by the compromised developer, downloads each tarball, injects its payload, bumps the patch version, and publishes it back—creating cascading chain reactions across ecosystems [1]. It also plants execution hooks in GitHub repositories via Actions workflows or `.vscode` configuration files, infecting any developer who clones an affected repo [4].

The May 2026 Mini Shai-Hulud wave introduced a novel twist: hijacking trusted CI/CD pipelines rather than stealing credentials externally. By chaining three GitHub Actions vulnerabilities—a "Pwn Request" via `pull_request_target`, cross-fork cache poisoning, and runtime OIDC token extraction—it produced packages with valid SLSA Build Level 3 provenance attestations [5].

## Remediation steps

- Audit all `package-lock.json` or `yarn.lock` files for compromised versions across direct and transitive dependencies [2].
- Pin npm package dependency versions to known-safe releases from before September 15, 2025 [3].
- Rotate all developer credentials, especially GitHub PATs and npm authentication tokens.
- Mandate phishing-resistant multifactor authentication (MFA) on all developer accounts for critical platforms including GitHub and npm [2].
- Monitor outbound connections to suspicious domains such as `webhook.site` [1].
- Harden GitHub security by removing unnecessary Apps/OAuth applications, auditing webhooks and secrets, and enabling branch protection with Secret Scanning alerts [3].

## Sources

[1] StepSecurity blog: https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised
[2] CISA Alert: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[3] Datadog Security Labs: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/
[4] JFrog Research: https://research.jfrog.com/post/shai-hulud-is-back-august/
[5] Cloud Security Alliance: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/

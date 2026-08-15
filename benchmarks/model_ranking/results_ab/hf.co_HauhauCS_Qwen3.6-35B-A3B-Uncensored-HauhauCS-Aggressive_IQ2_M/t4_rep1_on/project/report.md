# Shai-Hulud: npm Supply-Chain Worm Attacks (2025–2026)

## Timeline

The Shai-Hulud worm first appeared in mid-September 2025 when the popular package `@ctrl/tinycolor`—receiving over two million weekly downloads and maintained by a widely-used UI library author—was found compromised [1]. The initial variant executed via a post-install script, scanning for npm tokens, GitHub personal access tokens (PATs), and cloud credentials on affected developer machines. Within days the worm had spread to more than forty other packages across multiple maintainers [1]. By September 23, CISA confirmed over five hundred npm packages were compromised in total [2].

In early November 2025 the campaign resurged as "Shai-Hulud 2.0," widening its scope from hundreds of packages to tens of thousands of GitHub repositories and introducing pre-install execution via a Bun runtime binary [3][4]. This variant added an aggressive fallback mechanism that could destroy a victim's home directory if credential exfiltration failed, and it began impersonating "Linus Torvalds" on malicious commits [3][4].

On May 11, 2026, Microsoft Security Research identified a resurgence dubbed "Mini Shai-Hulud," compromising over one hundred seventy npm packages and two PyPI packages across four-hundred-and-four versions—the first coordinated supply-chain attack spanning both registries simultaneously [5].

## How it spreads

The worm's propagation engine queries the npm registry API to enumerate up to twenty packages owned by a compromised maintainer, then force-publishes patched versions containing its payload into each one [1][2]. This creates cascading compromise: any downstream project that installs an affected package inherits the malicious post-install or pre-install script.

The core malware is a ~3.6 MB Webpack-bundled JavaScript file (~70% of which is triple-obfuscated) that runs during `npm install` [1][5]. It harvests `.npmrc` files, GitHub PATs, and cloud credentials (AWS access keys via regex pattern `AKIA[0-9A-Z]{16}`, Google Cloud service accounts, Azure tokens), then uploads them to a newly created public GitHub repository under the victim's account using the `/user/repos` API [2][5].

In Shai-Hulud 2.0 and later variants, an optional Bun runtime is installed if absent; the payload downloads a GitHub Actions Runner archive containing TruffleHog for deeper credential scanning of stored secrets on disk [4][5]. The worm also injects a persistent GitHub Actions workflow file that triggers on push events to exfiltrate repository secrets via `${{ toJSON(secrets) }}` expressions [1].

## Remediation steps

- Pin npm package dependencies to known-safe versions released before September 16, 2025 (or the pre-install variant's release date if later) [2].
- Rotate all developer credentials: GitHub PATs, npm tokens, and cloud provider keys (AWS, GCP, Azure) [2][4].
- Enable phishing-resistant multifactor authentication on all developer accounts, especially for critical platforms like GitHub and npm [2].
- Block outbound connections to webhook endpoints used by the worm (e.g., `webhook.site` domains) and monitor firewall logs for suspicious traffic [2].
- Harden GitHub repositories: remove unnecessary GitHub Apps and OAuth applications; enable branch protection rules, Secret Scanning alerts, Dependabot security updates, and commit signature verification to detect impersonation of known personas such as "Linus Torvalds" [4][5].
- Search affected environments for the malicious payload files (`setup_bun.js`, `bun_environment.js`) and any newly created repositories with descriptions containing "Sha1-Hulud: The Second Coming" or similar variants [3][4].

## Sources

[1] [Source: https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised]StepSecurity, "Shai-Hulud: Self Replicating Worm Compromises 500+ NPM Packages," September 2025. https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised
[2] [Source:https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]CISA Alert, "Widespread Supply Chain Compromise Impacting npm Ecosystem," September 23, 2025. https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[3] [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/]Palo Alto Networks Unit 42, "Shai-Hulud Worm Compromises npm Ecosystem in Supply Chain Attack," November 25, 2025. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
[4] [Source:https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/]Microsoft Security Blog, "Shai-Hulud 2.0: Guidance for Detecting, Investigating, and Defending Against the Supply Chain Attack," December 9, 2025. https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/
[5] [Source: https://www.akamai.com/blog/security-research/mini-shai-hulud-worm-returns-goes-public]Akamai Research Blog, "Mini Shai-Hulud: The Worm Returns and Goes Public," May 2026. https://www.akamai.com/blog/security-research/mini-shai-hulud-worm-returns-goes-public

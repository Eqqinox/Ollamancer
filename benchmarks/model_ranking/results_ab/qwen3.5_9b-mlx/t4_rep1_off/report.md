# Shai-Hulud npm Supply Chain Worm Attacks (2025–2026)

## Timeline

The Shai‑Hulud campaign began in September 2025 as a self-replicating worm compromising over 500 packages across the npm registry [1]. Initial reports emerged on September 15, 2025 when @ctrl/tinycolor and approximately 40 other packages were found infected. CISA publicly disclosed this widespread supply chain compromise involving the world's largest JavaScript registry on September 23, 2025 [1].

In November 2025, Unit 42 researchers reported Shai-Hulud 2.0 affecting tens of thousands of GitHub repositories across approximately 350 unique users with over 25,000 malicious repositories identified by late November [2]. This second wave introduced execution during the pre-install phase instead of post-installation and more aggressive fallback mechanisms capable of destroying victim home directories if credential theft failed.

By May 2026, a new coordinated campaign emerged under TeamPCP combining Shai-Hulud with Megalodon operations targeting AI developer supply chains [3]. Wave 1 (Mini Shai‑Hulud) from April 29 to May 12 compromised 172 packages across 404 malicious versions and became the first publicly documented attack producing cryptographically valid SLSA Build Level 3 provenance attestations by hijacking legitimate build pipelines [3]. Wave 2 (Megalodon) on May 18 pushed 5,718 malicious commits to 5,561 GitHub repositories in under six hours using forged CI bot identities. TeamPCP publicly released the Shai-Hulud worm source code as open-source software on May 12 [3].

## How it spreads

The malware operates through automated propagation exploiting compromised maintainer accounts without requiring human interaction. After initial compromise—potentially via phishing campaigns spoofing npm requesting MFA updates—the threat actor deploys malicious code during package installation phases embedded in postinstall or pre-install scripts [1][2].

First, the malware scans for sensitive credentials including GitHub Personal Access Tokens (PATs), AWS access keys, Google Cloud Platform API keys, and Azure service principals. It uses tools like TruffleHog to search filesystem patterns matching high-entropy secrets [1][2]. Harvested credentials are exfiltrated via HTTP POST requests or uploaded directly to a public GitHub repository named "Shai-Hulud" using the /user/repos API with identifying commit messages [1].

Using stolen npm authentication tokens, malware authenticates to the registry and identifies other packages maintained by compromised developers. It injects malicious code into dependent packages—typically around 20 per infection—and publishes new versions containing worm payload back through automated processes using NpmModule.updatePackage [1]. This self-replicating capability allows exponential spread across ecosystems without direct attacker intervention, affecting tens of thousands downstream repositories.

The November variant introduced pre-install execution timing guaranteeing malware runs on every build server processing infected packages and bypasses static scanning tools inspecting code during later stages [2]. When credential theft fails, the fallback mechanism attempts to destroy victim home directories by overwriting all writable files owned by current users—a shift from pure espionage toward denial-of-service objectives.

## Remediation steps

CISA recommends immediately conducting comprehensive dependency reviews checking package-lock.json or yarn.lock files to identify affected dependencies including those nested in transitive trees [1]. Organizations should search artifact repositories for cached versions of compromised packages produced after September 16, 2025 and pin npm package versions to known safe releases before the compromise date—any unversioned version carries infection risk [1][4].

All developer credentials must be rotated immediately: GitHub Personal Access Tokens, AWS access keys and secret keys, Google Cloud Platform service account credentials, Azure subscription tokens, and npm authentication tokens all require regeneration as primary credential harvesting targets [1][2]. Organizations should mandate phishing-resistant multifactor authentication on platforms like GitHub and npm; traditional SMS-based MFA is insufficient.

Network monitoring must detect anomalous outbound connections to attacker-controlled endpoints particularly webhook.site domains used for exfiltration. Firewall logs require inspection for suspicious domain communications [1]. Remove unnecessary GitHub Apps from repositories, audit webhooks and OAuth applications serving as attack vectors, enable branch protection rules with required status checks, activate Secret Scanning alerts for real-time credential exposure detection, ensure Dependabot security updates enabled across all dependencies [1][4].

For organizations affected by Shai-Hulud 2.0's pre-install execution: implement comprehensive package provenance verification beyond simple registry trust and deploy runtime monitoring for anomalous build behavior since static scanning may miss early-stage infection [2][3]. Organizations relying solely on SLSA Level 3 attestations or signed commits should add behavioral detection capabilities to identify malicious activity regardless of code signing status.

## Sources

1. CISA Alert: Widespread Supply Chain Compromise Impacting npm Ecosystem — https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
2. Palo Alto Networks Unit 42: "Shai-Hulud" Worm Compromises npm Ecosystem in Supply Chain Attack (Updated September) — https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
3. Cloud Security Alliance Research Note: Shai-Hulud/Megalodon supply chain cascade attack — https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-megalon-supply-chain-cascade/

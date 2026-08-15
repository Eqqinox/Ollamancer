# Shai-Hulud npm Supply Chain Worm Attacks

## Timeline

The "Shai-Hulud" campaign is a self-replicating worm that compromised the npm JavaScript package registry. The original attack was first reported on September 15, 2025, when malicious versions of multiple popular packages were published to npm [1]. These packages contained post-installation scripts that harvested sensitive developer credentials and exfiltrated them to attacker-controlled endpoints [2].

By late September 2025, the worm had compromised over 500 packages. The malware targeted GitHub Personal Access Tokens (PATs) and API keys for cloud services including AWS, Google Cloud Platform, and Microsoft Azure [1]. In November 2025, a significantly escalated version known as "Shai-Hulud 2.0" was detected, which moved the malicious code from post-installation to preinstall execution in package.json files [3]. This change dramatically widened the attack's reach: over 700 npm packages were compromised and more than 25,000 malicious GitHub repositories were created across approximately 350 unique user accounts [4].

A further resurgence called "Mini Shai-Hulud" was identified on May 11, 2026. This variant expanded the campaign to also target Python's PyPI registry for the first time in a single coordinated operation, compromising over 170 npm packages and 2 PyPI packages across more than 400 malicious versions [3].

## How it spreads

The worm operates through an automated self-propagation loop. After initial compromise via a poisoned package, the malware scans the victim's environment for credentials stored in configuration files such as .npmrc, environment variables, and cloud service key stores [2]. Harvested secrets are exfiltrated to attacker-controlled servers and simultaneously committed to public GitHub repositories named "Shai-Hulud" under the victim's own account [1].

The stolen npm authentication token is then used by an automated process to authenticate to the npm registry as the compromised developer. The malware identifies other packages maintained by that same user, injects malicious code into them, and publishes new compromised versions back to the registry — all without any direct human intervention from the attacker [2]. This recursive cycle allows exponential spread: each newly infected package can compromise additional projects in subsequent installations.

In Shai-Hulud 2.0, execution shifted to the preinstall phase of npm packages (via a script named setup_bun.js), which guaranteed execution on virtually every build server processing the dependency without requiring human interaction [3]. The campaign also introduced an aggressive fallback mechanism: if credential theft fails and no exfiltration channel is available, the malware attempts to destroy the victim's home directory by securely overwriting all writable files owned by that user [4].

## Remediation steps

CISA recommends conducting a dependency review of all software leveraging npm packages, checking package-lock.json or yarn.lock files to identify affected dependencies including those nested in deeper dependency trees [1]. Organizations should pin npm package versions to known-safe releases produced prior to September 16, 2025, and rotate all developer credentials immediately [1].

Additional hardening measures include mandating phishing-resistant multifactor authentication on all developer accounts — particularly for GitHub and npm — removing unnecessary GitHub Apps and OAuth applications, auditing repository webhooks and secrets, enabling branch protection rules, and activating GitHub Secret Scanning alerts with Dependabot security updates [1]. Network defenses should block outbound connections to webhook.site domains and monitor firewall logs for suspicious domain activity. Organizations are also advised to enable Microsoft Defender or equivalent endpoint protection that can detect the campaign's characteristic behavior patterns [3].

## Sources

[1] CISA, "Widespread Supply Chain Compromise Impacting npm Ecosystem," September 23, 2025 — https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem

[2] Palo Alto Networks Unit 42, "'Shai-Hulud' Worm Compromises npm Ecosystem in Supply Chain Attack," September 17, 2025 — https://unit42.paloaltonetworks.com/npm-supply-chain-attack/

[3] Microsoft Security Blog, "Shai-Hulud 2.0: Guidance for detecting, investigating, and defending against the supply chain attack," December 9, 2025 (updated May 13, 2026) — https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/

[4] Wiz Blog, "Shai-Hulud npm Supply Chain Attack" — https://www.wiz.io/blog/shai-hulud-npm-supply-chain-attack

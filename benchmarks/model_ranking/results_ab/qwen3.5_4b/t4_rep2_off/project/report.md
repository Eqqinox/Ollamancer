
## Timeline

The original Shai-Hulud worm was first identified in September 2025, compromising over 500 npm packages [1]. On November 24, 2025, a second self-replicating variant dubbed "Shai-Hulud 2.0" emerged, backdooring approximately 796 unique npm packages with over 20 million weekly downloads [3]. The initial Shai-Hulud campaign was reported by CISA on September 23, 2025 as a widespread supply chain compromise affecting the world's largest JavaScript registry [1].

By November-November-December 2025, Unit42 documented that over 25,000 malicious repositories were created across approximately 350 unique users in this renewed campaign [2]. The attack escalated from simple credential theft to potential denial-of-service by crippling CI/CD pipelines. On May 11–13, 2026, Microsoft Security Research identified a significant resurgence tracked as "Mini Shai-Hulud," compromising over 170 npm packages and 2 PyPI versions [4]. This marked the first supply chain attack to simultaneously span both registries in coordinated operation.

## How it spreads

The worm exploits pre-install scripts added to package.json files, executing malicious code before security checks or tests run [3]. Attackers inject setup_bun.js (or set_bun.js) which installs and runs obfuscated payload using the Bun JavaScript runtime—capable of evading Node.js monitoring tools. The malware then executes bun_environment.js, which downloads GitHub Actions Runner archives to create self-install workers called "SHA1Hulud" [4].

Self-replication occurs without C2 server contact: worms read their own content and propagate by authenticating as compromised developer accounts on the npm registry to inject code into other packages. This eliminates human interaction requirements while bypassing static scanning tools that inspect code at later build stages [3]. Stolen credentials (GitHub PATs, AWS/GCP/Azure API keys) are exfiltrated via public GitHub repositories described as "Sha1-Hulud: The Second Coming" or uploaded to endpoints controlled by the attacker [2][4].

## Remediation steps

Organizations should pin npm package versions known safe prior to September 16, 2025 for original Shai-Hulud and before November/December dates for subsequent waves [1]. Conduct dependency reviews of all software using npm ecosystems, checking package-lock.json or yarn.lock files including nested dependencies. Search artifact repositories for cached affected versions immediately after discovery. Rotate all developer credentials and mandate phishing-resistant MFA on GitHub/npm accounts as CISA recommends [1].

Block outbound connections to webhook.site domains per Microsoft guidance; monitor firewall logs for suspicious domain activity. Use layered protection correlating telemetry across endpoint, container behavior, and runtime anomalies—Microsoft Defender specifically alerts via "Suspicious usage of the shred command" or dedicated Sha1-Hulud Campaign Detected indicators [4]. Verify commit signatures as fake personas like "Linus Torvalds" have been used to hide malicious activity.

## Sources

[1] https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[2] https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
[3] https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/
[4] https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/

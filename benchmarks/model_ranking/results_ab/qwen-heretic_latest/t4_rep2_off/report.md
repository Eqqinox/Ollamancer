# Shai-Hulud npm Supply Chain Worm Attacks

## Timeline

The "Shai-Hulud" campaign began in September 2025 as a self-replicating worm targeting the npm JavaScript registry. On **September 15, 2025**, malicious versions of multiple popular packages were published containing post-install scripts that harvested sensitive data and exfiltrated it to attacker-controlled public GitHub repositories [Source: https://www.wiz.io/blog/shai-hulud-npm-supply-chain-attack]. This marked the first successful self-propagating attack in the npm ecosystem, directly downstream of an earlier August compromise involving stolen developer credentials.

By **November 2025**, Unit42 researchers identified "Shai-Hulud 2.0," a significantly wider campaign affecting tens of thousands of GitHub repositories across approximately 350 unique users [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack]. The attack evolved through multiple waves over nine months, with each iteration introducing new capabilities and broader target sets.

In **April-May 2026**, the campaign escalated further under the designation "Mini Shai-Hulud." This wave represented a historic escalation when both npm and PyPI registries were simultaneously compromised in a coordinated operation targeting approximately 172 packages across 404 malicious versions [Source: https://falconfeeds.io/blogs/shai-hulud-npm-pypi-supply-chain-worm-analysis/]. The cumulative exposure spanned roughly 518 million weekly downloads at peak activity.

## How it spreads

The worm operates through several interconnected mechanisms:

**Initial Infection:** Malicious npm packages contain post-install or preinstall scripts that execute when dependencies are installed. These scripts use secret-scanning tools like TruffleHog to identify exposed credentials in the environment [Source: https://www.wiz.io/blog/shai-hulud-npm-supply-chain-attack].

**Self-Replication:** Once active, compromised packages automatically publish malicious versions of any other packages they can access if additional npm tokens exist in the victim's environment. This allows exponential spread without direct operator intervention [Source: https://www.wiz.io/blog/shai-hulud-npm-supply-chain-attack].

**Credential Harvesting and Exfiltration:** The malware scans for GitHub Personal Access Tokens (PATs), API keys for cloud services including AWS, Google Cloud Platform, and Microsoft Azure, then exfiltrates these credentials to attacker-controlled endpoints or uploads them to public repositories named "Shai-Hulud" [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem].

**Escalated Capabilities in Shai-Hulud 2.0:** The November campaign introduced execution during the preinstall phase rather than post-install, eliminating the need for human interaction and bypassing static scanning tools that inspect code at later build stages [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack]. New payload files named setup_bun.js and bun_environment.js were deployed with an aggressive fallback mechanism capable of attempting to destroy a user's home directory. Stolen credentials are exfiltrated to public GitHub repositories described as "Sha1-Hulud: The Second Coming" [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack].

## Remediation steps

CISA and security researchers recommend the following remediation measures:

- Conduct comprehensive dependency reviews across all software leveraging npm, checking for package-lock.json or yarn.lock files to identify affected packages including those nested in dependency trees [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]
- Search artifact repositories and dependency management tools for cached versions of compromised dependencies
- Pin npm package dependency versions to known safe releases produced **prior to September 16, 2025** [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]
- Immediately rotate all developer credentials, especially GitHub Personal Access Tokens and cloud service API keys [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]
- Mandate phishing-resistant multifactor authentication on all developer accounts for critical platforms like GitHub and npm [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]
- Monitor network behavior and block outbound connections to suspicious domains including webhook.site patterns identified in the campaign [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]
- Implement preinstall-phase security scanning since later build-stage tools may miss these threats [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack]

## Sources

1. Wiz Research blog on Shai-Hulud npm supply chain attack: https://www.wiz.io/blog/shai-hulud-npm-supply-chain-attack
2. CISA Alert on widespread npm ecosystem compromise: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
3. FalconFeeds analysis of Shai-Hulud cross-ecosystem threat: https://falconfeeds.io/blogs/shai-hulud-npm-pypi-supply-chain-worm-analysis/

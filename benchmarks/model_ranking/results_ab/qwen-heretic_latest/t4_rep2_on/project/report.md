# Shai-Hulud npm Supply Chain Worm Attacks

## Timeline

The initial "Shai-Hulud" campaign was first reported in September 2025, when Unit 42 researchers identified a self-replicating worm compromising over 500 packages on the npm registry [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/]. CISA issued an official alert on September 23, 2025, confirming widespread compromise and providing remediation guidance to organizations across government and industry [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem].

A significantly more aggressive second wave emerged in November 2025. Unit 42 researchers detected "Shai-Hulud 2.0" around early November, noting it was substantially wider in scope than its predecessor [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/]. By late December 2025, Zscaler reported the campaign had compromised over 700 packages and created more than 27,000 malicious GitHub repositories within hours of detection [Source: https://www.zscaler.com/blogs/security-research/shai-hulud-v2-poses-risk-npm-supply-chain]. The operators dubbed this escalation "The Second Coming," indicating their intent to persist in attacking the npm ecosystem.

## How it spreads

Shai-Hulud operates as a self-replicating worm that exploits compromised developer accounts on npm and GitHub [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]. After initial infection, malware scans environments for sensitive credentials including GitHub Personal Access Tokens (PATs) and cloud service API keys from AWS, Google Cloud Platform, and Microsoft Azure [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]. The harvested secrets are exfiltrated to attacker-controlled endpoints and uploaded to public repositories named "Shai-Hulud" via the GitHub/user/repos API [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/][Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem].

The worm spreads by authenticating as compromised developers to the npm registry, then injecting malicious code into other packages before publishing those versions back to the registry [Source: https://www.zscaler.com/blogs/security-research/shai-hulud-v2-poses-risk-npm-supply-chain]. This automated propagation allows rapid expansion without requiring human interaction. Shai-Hulud 2.0 introduced execution during the pre-install phase of software dependencies, which guarantees infection on every build server processing infected packages and bypasses static scanning tools that inspect code at later stages [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/].

The malware also deploys persistent backdoor access through self-hosted GitHub Actions runners to maintain long-term control over compromised repositories [Source: https://www.zscaler.com/blogs/security-research/shai-hulud-v2-poses-risk-npm-supply-chain]. A notable escalation in the November campaign included a "dead man's switch" mechanism designed to delete user data if containment measures are detected, escalating from espionage into potential denial-of-service operations against enterprise CI/CD pipelines.

## Remediation steps

Organizations should immediately conduct dependency reviews of all software leveraging npm packages, checking package-lock.json or yarn.lock files to identify affected dependencies including those nested in trees [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]. Pinning versions to known safe releases produced prior to September 16, 2025 provides a baseline for rollback [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]. Clearing cached artifact repositories and reinstalling clean packages eliminates lingering malicious code.

Credential rotation is critical: all npm tokens, GitHub Personal Access Tokens, cloud service keys, and CI/CD secrets must be revoked immediately [Source: https://www.zscaler.com/blogs/security-research/shai-hulud-v2-poses-risk-npm-supply-chain]. Implement phishing-resistant multifactor authentication on developer accounts, especially for critical platforms like GitHub and npm [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem][Source: https://www.zscaler.com/blogs/security-research/shai-hulud-v2-poses-risk-npm-supply-chain]. Organizations should use private registry proxies combined with Software Composition Analysis tools to filter and monitor third-party packages going forward.

Network controls include blocking outbound connections to webhook.site domains used by the attackers for secret exfiltration and monitoring firewall logs for suspicious domain communications [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]. Applying lockfiles strictly using commands like npm ci instead of standard npm install prevents installation of tampered dependencies. Reducing dependency surface area through regular audits removes unused packages that could serve as attack vectors.

## Sources

[Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/]
[Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]
[Source: https://www.zscaler.com/blogs/security-research/shai-hulud-v2-poses-risk-npm-supply-chain]

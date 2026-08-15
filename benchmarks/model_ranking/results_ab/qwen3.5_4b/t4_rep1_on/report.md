
## Timeline

The original Shai-Hulud worm was identified in September 2025, when CISA released an alert warning of a widespread supply chain compromise affecting over 500 npm packages [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]. Unit42 documented the attack as self-replicating malware scanning for credentials including GitHub PATs and cloud provider API keys (AWS, GCP, Azure) before exfiltration to public repositories named "Shai-Hulud" under compromised user accounts [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/].

In early November 2025, Shai-Hulud escalated into version 2.0 affecting over 796 npm packages with cumulative weekly downloads exceeding 20 million and impacting approximately 150 GitHub organizations [Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/]. The key difference was execution during pre-install rather than post-install phase, eliminating the need for human interaction to guarantee malware deployment across CI/CD pipelines [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/][Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/].

By December 2025, Microsoft documented attackers compromising maintainer accounts from major projects including Zapier, PostHog, and Postman [Source: https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/]. Stolen credentials were exfiltrated under fake personas like "Linus Torvalds" to evade detection through commit signature verification [Source: https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/].

A notable resurgence occurred in May 2026 as Microsoft identified Mini Shai-Hulud—a campaign compromising approximately 170 npm packages and two PyPI packages across over 400 malicious versions, with a cumulative download base exceeding 518 million downloads [Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-supply-chain-20260517-csa-st/]. This marked the first supply chain attack to simultaneously span both npm and PyPI registries in coordinated operation.

## How it spreads

The worm's propagation relies on self-replication without command-and-control server connections [Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/]. After initial access through credential-harvesting phishing campaigns spoofing npm authentication, attackers deploy malware executing post-install or pre-install scripts within compromised packages [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/][Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/]. The malicious code reads its own content to identify and infect other package versions maintained by the same developer account [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/][Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/].

Shai-Hulud 2.0 introduced new payload files named setup_bun.js and bun_environment.js, which install Bun JavaScript runtime if absent before executing credential-stealing scripts [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/][Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/]. The malware uses TruffleHog to scan for stored credentials across multiple platforms including GitHub Actions runners' process memory [Source: https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/].

Mini Shai-Hulud (May 2026) introduced novel capabilities: forging valid SLSA Build Level 3 provenance attestations by extracting OIDC tokens from runner processes and using them with legitimate Sigstore certificates, making malicious packages appear cryptographically verified to automated security tools [Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-supply-chain-20260517-csa-st/]. It also weaponized AI coding agent configuration files (.claude/settings.json for Claude Code) as persistence mechanisms that survive package removal [Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-supply-chain-20260517-csa-st/].

The attack chain typically follows: npm install triggers resolution of malicious optional dependencies → shell execution spawns Bun runtime if needed → credential stealer executes and harvests secrets from filesystem and cloud environments [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/][Source: https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/]. Fallback destruction occurs when exfiltration fails—malware securely overwrites every writable file in the victim's home directory [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/][Source: https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/].

## Remediation steps

Organizations should immediately conduct dependency reviews of all npm package usage, checking for affected packages including those nested deep within dependency trees by examining package-lock.json or yarn.lock files and artifact repositories [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]. Pinning to known safe releases predating September 2025 (for original Shai-Hulud) is critical—Microsoft recommends pinning before December's attack wave as well.

Credential rotation must occur immediately after detection, with phishing-resistant MFA mandated on all developer accounts especially for GitHub and npm [Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]. Organizations should block outbound connections to webhook.site domains and monitor firewall logs for suspicious domain activity per CISA guidance [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/][Source: https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem]. Microsoft recommends correlating telemetry across endpoint behavior, container runtime anomalies, and supply chain provenance validation.

For Mini Shai-Hulud specifically: disable any persistence hooks in IDE configuration files before rotating credentials—the malware triggers home directory destruction if rotation occurs without first disabling these services according to Cloud Security Alliance research [Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-supply-chain-20260517-csa-st/]. Verify SLSA Level 3 attestations for suspicious signatures and check GitHub Actions runner memory integrity.

## Sources

1. https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
2. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
3. https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/
4. https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/
5. https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-supply-chain-20260517-csa-st/

Word count: 483 words | Sources used: 9 (but only 5 unique URLs in the numbered list)


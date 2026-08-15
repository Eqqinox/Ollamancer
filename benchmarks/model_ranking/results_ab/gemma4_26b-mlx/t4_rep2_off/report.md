## Timeline
The Shai-Hulud attacks began in September 2025, followed by a massive "Shai-Hulud 2.0" campaign in November 2025 [1][Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/]. This second wave impacted tens of thousands of GitHub repositories and over 25,000 malicious repositories across approximately 350 users [1][Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/], featuring aggressive fallback mechanisms designed to destroy user home directories [1][Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/].

In May 2026, a "Mini Shai-Hulud" resurgence occurred when the group TeamPCP published hundreds of malicious package versions in under six hours [3][Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/]. This wave targeted major AI ecosystems including TanStack, Mistral AI, UiPath, OpenSearch, and Guardrails AI [3][Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/].

## How it spreads
Attackers utilize the `preinstall` phase of npm packages to execute code before security scans or tests can run [1][Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/][2][Source: https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/]. The 2.0 campaign also involved compromising maintainer accounts for projects like Zapier, PostHog, and Postman [2][Source: https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/].

The "Mini Shai-Hulud" attack (CVE-2026-45321) hijacked GitHub Actions release pipelines to produce packages with valid SLSA Build Level 3 provenance [3][Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/]. This method chained vulnerabilities involving `pull_request_target`, cache poisoning, and OIDC token extraction [3][Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/]. Additionally, some branches contained geofenced logic to wipe filesystems on systems in Israel or Iran [3][Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/].

## Remediation steps
For the May 2026 wave, developers using affected TanStack, Mistral AI, UiPath, OpenSearch, or Guardrails AI packages must immediately rotate all reachable secrets [3][Source: https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/].

General defense requires a layered approach, utilizing security coverage that spans from code to runtime anomaly detection [2][Source: https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/] to identify and contain malicious dependencies that evade traditional assessments [2][Source: https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/].

## Sources
[1] https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
[2] https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/
[3] https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/

# Shai-Hulud: The npm Supply-Chain Worm Campaign (2025–2026)

## Timeline

The campaign began in September 2025 when a self-replicating worm infected popular utility packages such as @ctrl/tinycolor on the npm registry, compromising tens of initial package versions through maintainer credential theft [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/]. In November 2025, Shai-Hulud 2.0 emerged with an expanded payload that executed during pre-install rather than post-install, backdoored hundreds of packages and exfiltrated credentials from over 500 GitHub users across more than 150 organizations before being halted on November 24 [Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/]. A second wave in April 2026 introduced the string "Shai-Hulud: The Third Coming" and included compromised package versions such as Axios [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/]. June saw a new campaign targeting the @redhat-cloud-services namespace with at least 32 packages, followed by July's compromise of four AsyncAPI repositories publishing trojanized artifacts under the codename Miasma-train-p1 [Source: https://unit42.paloaltonetworks.com/npm-supply-chain-attack/].

## How it spreads

Shai-Hulud operates as a self-replicating worm that compromises legitimate npm packages through maintainer credential theft. Once installed on a victim machine, the malware's pre-install script executes first during dependency resolution, harvesting credentials from .npmrc files and cloud metadata services (AWS, GCP, Azure). It then steals GitHub Personal Access Tokens and npm tokens from disk or via instance metadata queries [Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/]. Using these stolen credentials, it authenticates to the npm registry as the compromised developer, identifies other packages maintained by that account, injects malicious setup_bun.js and bun_environment.js payloads into them using pre-install hooks, and republishes up to 100 backdoored versions without human interaction [Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/]. Harvested secrets are exfiltrated to a newly created public GitHub repository described as "Sha1-Hulud: The Second Coming." If no credentials can be found for replication or exfiltration, the worm attempts an aggressive fallback that deletes all writable files in the user's home directory [Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/].

## Remediation steps

- Rotate npm tokens and GitHub Personal Access Tokens (PATs) of affected maintainers immediately.
- Pin dependencies to specific versions and verify package integrity using checksums or provenance attestations before installation.
- Remove pre-install hooks from suspicious packages by auditing node_modules for setup_bun.js, bun_environment.js, or references to the "Sha1-Hulud" repository description string [Source: https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/].
- Rotate cloud credentials (AWS access keys, GCP service accounts, Azure secrets) found in environment files and cloud secret stores.
- Audit CI/CD pipelines for injected GitHub Actions workflows that reference Shai-Hulud artifacts and remove them from the build matrix.
- Monitor npm install logs for unexpected pre-install script execution and maintain a blocklist of known compromised package versions [Source: https://phoenix.security/shai-hullud-campaign-timeline/].

## Sources

1. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/ — Palo Alto Networks Unit 42, Shai-Hulud worm analysis (November 25, 2025)
2. https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm — Datadog Security Labs, Shai-Hulud 2.0 technical breakdown (November 25, 2025)
3. https://phoenix.security/shai-hullud-campaign-timeline/ — Phoenix Security, campaign phases and affected organizations (November 27, 2025)
4. https://unit42.paloaltonetworks.com/monitoring-npm-supply-chain-attacks/ — Palo Alto Networks Unit 42, npm threat landscape overview with April–July 2026 incidents (July 15, 2026)

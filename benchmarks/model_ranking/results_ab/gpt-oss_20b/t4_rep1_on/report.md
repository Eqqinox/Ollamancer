## Timeline
The Shai‑Hulud worm first appeared in early September 2025, when a self‑replicating payload was discovered compromising more than five hundred npm packages on the public registry [1]. The initial wave involved automated injection of malicious code into package tarballs and rapid re‑publication under compromised maintainer accounts. By mid‑November 2025 the campaign had expanded to an estimated 25 000 infected repositories across roughly 350 unique users, with a new variant dubbed Shai‑Hulud 2.0 that executed during the pre‑install phase of npm packages [3]. In December 2025 Microsoft released guidance on detecting and defending against this second wave, noting that attackers had also begun targeting CI/CD pipelines and cloud workloads to harvest credentials [2]. A brief resurgence was reported in May 2026 when new Mini Shai‑Hulud activity appeared, prompting updates to Defender protection rules (Microsoft Defender now includes coverage for the latest variants) [2].

## How it spreads
The worm operates by first compromising a developer’s GitHub Personal Access Token or cloud API key. Once credentials are harvested, the malware uploads them to a public repository named Shai‑Hulud via the GitHub user/repos API and then authenticates to npmjs.com as the compromised maintainer. It injects malicious JavaScript into dependency tarballs during the pre‑install hook, ensuring execution before any build or test steps run [1][2]. The worm’s self‑replication loop allows it to scan for additional packages in a project’s dependency tree and publish infected versions rapidly, effectively turning every affected package into a vector that propagates the payload across thousands of downstream projects. The use of pre‑install execution also bypasses many static analysis tools that only inspect code after installation.

## Remediation steps
1. **Audit dependencies** – Scan all `package-lock.json` or `yarn.lock` files for known affected packages and remove any that reference versions published after September 16, 2025 [1].
2. **Pin safe releases** – Lock npm package versions to the last verified safe release before the worm’s first appearance.
3. **Rotate credentials** – Immediately revoke all compromised GitHub PATs, cloud API keys, and any other secrets that may have been exfiltrated; enable phishing‑resistant MFA on all developer accounts [1][2].
4. **Monitor network activity** – Block outbound connections to known malicious domains such as `webhook.site` and watch firewall logs for suspicious traffic.
5. **Leverage Defender coverage** – Deploy Microsoft Defender’s supply‑chain protection, which correlates telemetry across endpoints, containers, and runtime environments to detect anomalous pre‑install behavior [2].
6. **Patch CI/CD pipelines** – Ensure that build servers run with the latest security patches and enforce least‑privilege principles so that even if a package is infected, credential theft is limited.

## Sources
1. https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
2. https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/
3. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
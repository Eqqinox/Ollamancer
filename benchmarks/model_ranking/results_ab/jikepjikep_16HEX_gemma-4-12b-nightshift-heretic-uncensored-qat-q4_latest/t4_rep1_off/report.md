## Timeline
The "Shai-Hulud" worm was first reported in early November 2025 [1]. It is a self-replicating worm that has compromised over 500 packages within the npm ecosystem [2]. By August 4, 2026, researchers identified further propagation of this backdoor across hundreds of popular npm packages, some with over 150 million weekly downloads [3].

## How it spreads
The Shai-Hulud worm achieves scale through automated propagation by authenticating to the npm registry as a compromised developer and injecting code into other packages [2]. It targets the pre-install phase of software dependencies, which allows it to execute on virtually every build server without human interaction while bypassing static scanning tools that inspect code during later stages [1]. Once active, the malware scans the environment for sensitive credentials—specifically GitHub Personal Access Tokens (PATs) and API keys for cloud services like AWS, GCP, and Microsoft Azure [2]. It then exfiltrates these harvested secrets to an endpoint controlled by the actor and uploads them to a public repository named "Shai-Hulud" via the GitHub/user/repos API [2].

## Remediation steps
To mitigate the impact of the Shai-Hulud worm, organizations should conduct a thorough dependency review of all software using npm packages, checking `package-lock.json` or `yarn.lock` files to identify nested affected dependencies [2]. It is recommended to pin package versions to known safe releases produced prior to September 16, 2025 [2]. Developers should immediately rotate all credentials and mandate phishing-resistant multi-factor authentication (MFA) on critical platforms like GitHub and npm [2]. Finally, organizations should monitor for anomalous network behavior by blocking outbound connections to webhook.site domains and monitoring firewall logs for suspicious domain activity [2].

## Sources
1. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
2. https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
3. https://securitylabs.datadoghq.com/articles/npm-worm-compromises-popular-npm-packages/

## Timeline
The Shai-Hulud supply chain worm first emerged in September 2025 as a self-replicating entity that compromised over 500 npm packages [1]. By November 2025, the campaign evolved into "Shai-Hulud 2.0," which significantly expanded its scope to affect tens of thousands of GitHub repositories and over 25,000 malicious repositories across approximately 350 unique users [2]. This updated version continued to be a major focus through late 2025 and into early 2026, with Microsoft Defender providing coverage for "Mini Shai-Hulud" activity as recently as May 13, 2026 [3].

## How it spreads
The worm is characterized by its self-replicating nature within the npm ecosystem. It gains initial access and then scans the environment for sensitive credentials, specifically targeting GitHub Personal Access Tokens (PATs) and API keys for cloud services like AWS, GCP, and Microsoft Azure [1]. To propagate, the malware authenticates to the npm registry as the compromised developer, injects code into other packages, and publishes these compromised versions back to the registry [1]. In version 2.0, the attack became more aggressive by executing during the pre-install phase of dependencies, which ensures execution on almost every build server without human interaction and allows it to bypass static scanning tools that typically inspect code during later build stages [2].

## Remediation steps
To mitigate the impact of Shai-Hulud, organizations should conduct a thorough dependency review by checking package-lock.json or yarn.lock files for affected packages in both direct and nested trees [1]. It is recommended to pin npm package versions to known safe releases produced before September 16, 2025 [1]. Security teams should immediately rotate all developer credentials and mandate phishing-resistant multi-factor authentication (MFA) on critical platforms like GitHub and npm [1]. Additionally, monitoring for anomalous network behavior—specifically blocking outbound connections to webhook.site domains and watching firewall logs for suspicious domains—is essential for detecting exfiltrated data [1].

## Sources
1. https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
2. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
3. https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/

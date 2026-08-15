## Timeline

The Shai-Hulud worm campaign began in September 2025 when attackers compromised npm maintainer accounts through a targeted phishing campaign, injecting malicious code into widely used JavaScript packages [3][4]. By mid-September, the self-replicating nature of this malware had already affected over 500 npm packages and resulted in approximately $50 million worth of cryptocurrency theft from victims across North America and Europe [2][3].

On September 16, 2025, researchers at Socket identified nearly 500 impacted NPM packages while StepSecurity reported similar findings regarding the Nx supply chain attack [4]. CISA issued an official alert on September 23 warning that a self-replicating worm known as "Shai-Hulud" had compromised over 500 packages and was actively spreading through automated processes [1][4].

The campaign escalated dramatically in November 2025. Between November 21-23, attackers launched Shai-Hulud 2.0 ("The Second Coming"), compromising hundreds of npm packages and more than 25,000 GitHub repositories within hours alone [3]. By late November, security vendors began publishing widespread alerts confirming the compromise across npm registries and CI/CD environments on November 24-25 [1][3].

In April-May 2026, TeamPCP executed two coordinated attack waves. The first wave (Mini Shai-Hulud) ran from late April through mid-May affecting over 170 npm packages across AI developer ecosystems including Mistral AI and TanStack [8]. On May 12-13, the threat actor publicly released the original Shai-Hulud worm source code as open-source software. A second wave called Megalodon on May 18 pushed approximately 5,718 malicious commits to over 5,000 GitHub repositories in under six hours [8].

## How it spreads

The attack begins when threat actors compromise npm maintainer accounts through phishing or credential theft campaigns targeting developers with privileged repository access [3][4]. Once inside a compromised account, the malware scans developer environments for sensitive credentials including GitHub Personal Access Tokens (PATs) and cloud service API keys for AWS, Google Cloud Platform, and Microsoft Azure [1][2].

The worm then exfiltrates harvested credentials to an endpoint controlled by attackers. Using these stolen tokens as authentication, it authenticates directly to the npm registry under compromised developer identities [1][4]. The malware injects malicious code into legitimate packages that depend on or interact with infected repositories and publishes backdoored versions of those packages to the public registry [2][3].

Shai-Hulud 2.0 introduced a critical escalation by executing during the pre-install lifecycle script phase, which runs before installation completes even when it fails—eliminating any need for human interaction while bypassing static scanning tools that inspect code at later build stages [1][4]. This automated propagation allows infected packages to spread rapidly through dependency trees without requiring developer action.

The stolen credentials enable attackers to republish compromised package versions, which downstream projects install automatically during their own builds and CI/CD pipelines. The worm can also target GitHub Actions workflows directly when it gains access to repository secrets stored in these environments [8]. Each infected build server then becomes a new propagation node that repeats the credential harvesting cycle across its entire dependency graph.

## Remediation steps

Organizations should immediately conduct comprehensive dependency reviews of all software leveraging npm packages, checking package-lock.json or yarn.lock files for affected dependencies including those nested deep within transitive dependency trees [1][4]. Search artifact repositories and caching tools (such as GitHub Packages) for cached versions of compromised dependencies to identify exposure scope. Pin all npm package version pins in configuration to known safe releases produced prior to September 16, 2025—the date before the worm began spreading through automated processes [3][4].

Rotate all developer credentials immediately: this includes every Personal Access Token (PAT) for GitHub accounts and cloud service API keys that may have been harvested by malware scanning infected environments [1][2]. Mandate phishing-resistant multifactor authentication on critical platforms, particularly GitHub and npm repositories where maintainer access enables worm propagation. Traditional SMS-based MFA is insufficient as attackers can harvest these tokens through the same infection vector [4].

Monitor network traffic for anomalous outbound connections to suspicious domains including webhook.site (a domain used by Shai-Hulud 2.0) and any other unusual destinations in firewall logs that may indicate credential exfiltration or command-and-control communications from compromised build servers [1][3]. Block these malicious endpoints at the perimeter where possible while maintaining visibility into potential lateral movement attempts within internal networks.

Remove all packages known to be infected by Shai-Hulud variants, including any custom repositories created during infection that contain stolen credentials in their descriptions or metadata fields [4]. Isolate affected developer machines and CI/CD runners from network access until credential rotation is complete and malware persistence mechanisms are removed—this prevents re-infection through the same compromised accounts.

## Sources

[1] https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[2] https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
[3] https://blog.checkpoint.com/research/shai-hulud-2-0-inside-the-second-coming-the-most-aggressive-npm-supply-chain-attack-of-2025/
[4] https://www.zscaler.com/blogs/security-research/tracking-shai-hulud-inside-chaindrop-npm-worm

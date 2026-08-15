## Timeline

The "Shai-Hulud" campaign began September 2025 as a self-replicating worm targeting npm, compromising over 500 packages [1]. The initial attack exploited post-install scripts to deploy malware scanning for credentials and propagating by injecting malicious code into other developer-maintained packages.

By November 2025, Shai-Hulud evolved into "Shai-Hulud 2.0," executing during preinstall rather than postinstall [2]. This change widened impact across CI/CD pipelines while eliminating reliance on human interaction for execution. The malware introduced aggressive fallback mechanisms that could destroy victim home directories if credential harvesting failed, shifting tactics from espionage to denial-of-service sabotage [3].

In December 2025, Microsoft Security Research documented the attack's sophistication with compromised maintainer accounts including Zapier and PostHog [4], marking significant escalation in supply chain threats. By May 2026, "Mini Shai-Hulud" represented another resurgence affecting over 170 npm packages plus PyPI packages across approximately 404 malicious versions [5], becoming the first coordinated operation to simultaneously span both npm and Python package registries.

## How it Spreads

Shai-Hulud operates as a five-phase attack chain designed for automated, self-propagating spread without direct actor intervention [1]. The initial phase involves phishing developers into updating multi-factor authentication options on developer platforms like GitHub or npm. Once access is gained through credential theft from .npmrc files and environment variables, the malware scans filesystems using tools like TruffleHog to harvest high-entropy secrets including AWS keys (AKIA[0-9A-Z]{16}), Google Cloud Platform credentials, Azure tokens, and cloud metadata endpoints [2].

The propagation mechanism leverages npm's package ecosystem. After harvesting credentials from a compromised maintainer account, the malware authenticates as that developer to the npm registry API. It then identifies other packages maintained by the same user and force-publishes malicious patches—specifically Webpack-bundled bundle.js files containing credential stealers [2]. This creates cascading compromise effects where one infection automatically infects downstream dependencies without requiring additional human action or attacker intervention, achieving exponential spread across thousands of repositories.

The November 2025 variant introduced execution during the preinstall phase (npm install), allowing malware to run before security checks and tests could detect it [3]. The payload files setup_bun.js and bun_environment.js scoped environments for Bun runtime installation while downloading GitHub Actions Runner archives containing TruffleHog executables. In some cases, attackers used fake personas including "Linus Torvalds" when creating malicious repositories on victim accounts to bypass commit signature verification controls [4].

## Remediation steps

Organizations should immediately pin npm package dependency versions to releases produced prior to September 16, 2025 for the original attack and before December updates for Shai-Hulud variants [1]. Conduct thorough dependency reviews across all software leveraging the npm ecosystem by checking package-lock.json or yarn.lock files in nested dependencies. Search cached versions of affected packages within artifact repositories and implement monitoring for anomalous network behavior including outbound connections to webhook.site domains, suspicious domain activity on firewalls, and unauthorized GitHub App registrations [3].

Rotate all developer credentials immediately following any compromise event. Mandate phishing-resistant multifactor authentication (MFA) specifically on critical platforms like GitHub and npm accounts. Enable branch protection rules across repositories, activate GitHub Secret Scanning alerts for credential detection in code commits, and configure Dependabot security updates to automatically address known vulnerabilities [1]. Block outbound connections using firewall logs analysis and monitor network traffic patterns that deviate from baseline behavior.

Implement automated scanning tools like TruffleHog within CI/CD pipelines to detect exposed credentials before deployment. Verify commit signatures through author identity checks rather than relying solely on signature hashes, especially for suspicious commits under impersonated personas [4]. For affected packages specifically @ctrl/tinycolor and related dependencies from the initial 500+ package compromise list, revert versions prior to September 16, 2025 or update to patched releases that remove malicious postinstall scripts.

## Sources

[1] https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[2] https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
[3] https://panther.com/blog/shai-hulud-npm-supply-chain-attack
[4] https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/

# Shai-Hulud npm Supply Chain Worm Campaign Report

## Timeline

In September 2025, a self-replicating npm worm publicly known as "Shai-Hulud" compromised over 500 packages in the JavaScript ecosystem [1]. The attack was identified by security researchers and CISA issued an official alert on September 23, 2025 to warn organizations of the widespread supply chain compromise affecting the world's largest npm registry [1].

By November 24, 2025, a second iteration dubbed "Shai-Hulud 2.0" emerged with similar tactics but significantly wider scope [2][3]. This variant had successfully backdoored 796 unique npm packages totaling over 20 million weekly downloads at the time of identification [3]. The last observed compromised package was published on November 24, suggesting that defensive measures may have been deployed by that point to halt further infections [3].

## How it spreads

The worm operates through a self-replicating mechanism without requiring command-and-control server communication. It reads its own content from an infected legitimate npm package and propagates malicious code into other packages using the compromised developer's authenticated credentials [2][3]. The malware injects two payload files—setup_bun.js and bun_environment.js—and triggers execution by adding a new preinstall script to vulnerable dependencies [3].

During installation, the worm installs the Bun JavaScript runtime, likely chosen for its ability to evade standard Node.js monitoring tools. It then executes an obfuscated payload that scans local filesystems and cloud environments (AWS, Google Cloud Platform, Microsoft Azure) for sensitive credentials including GitHub Personal Access Tokens and API keys [1][2].

Stolen data is exfiltrated both directly to attacker-controlled endpoints and uploaded to public GitHub repositories with the distinctive description "Sha1-Hulud: The Second Coming" [2][3]. Shai-Hulud 2.0 notably targets the preinstall phase, allowing execution before traditional security scanning occurs during later build stages, effectively bypassing many static analysis tools [2].

## Remediation steps

CISA and security researchers recommend immediate remediation actions for affected organizations:

- Conduct comprehensive dependency reviews of all software leveraging npm packages, checking package-lock.json or yarn.lock files to identify compromised dependencies including those nested in dependency trees [1]
- Pin npm package versions to known safe releases produced prior to September 16, 2025 until full assessment is complete [1]
- Immediately rotate all developer credentials, particularly GitHub Personal Access Tokens and cloud service API keys that may have been exposed [1][3]
- Mandate phishing-resistant multifactor authentication on all developer accounts for critical platforms including GitHub and npm [1]
- Monitor network behavior and block outbound connections to webhook.site domains identified as exfiltration endpoints [1]
- Search artifact repositories for cached versions of affected dependencies that may contain malicious code [1]

## Sources

[1] https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem

[2] https://unit42.paloaltonetworks.com/npm-supply-chain-attack/

[3] https://securitylabs.datadoghq.com/articles/shai-hulud-2.0-npm-worm/

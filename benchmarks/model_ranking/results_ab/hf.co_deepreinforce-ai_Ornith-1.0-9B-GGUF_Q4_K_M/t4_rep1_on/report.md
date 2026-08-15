# Shai-Hulud npm Supply Chain Worm Campaign

## Timeline

The campaign, named "Shai-Hulud" after the three-legged sandworm from Dune, first appeared on September 15, 2025. Malicious versions of popular npm packages were published containing post-install scripts that harvested secrets and exfiltrated them to attacker-controlled public GitHub repositories [3]. The malware exhibited self-replicating worm behaviour: once a compromised package encountered additional npm tokens in its environment, it automatically published malicious versions of every other accessible package—making Shai-Hulud the first successful self-propagating attack observed in the npm ecosystem [1][2].

The initial wave affected over 500 packages and was directly downstream of an earlier August 2025 compromise of a widely used dependency management tool (s1ngularity/Nx), which provided the GitHub token theft that enabled subsequent npm registry access [2]. CISA issued its first alert on September 23, 2025 [1].

In November 2025, researchers identified "Shai-Hulud 2.0," a significantly wider campaign affecting tens of thousands of repositories across approximately 350 unique users and over 25,000 malicious repositories [4]. The key change was moving execution to the pre-install phase rather than post-install, eliminating the need for human interaction during package installation [6].

A further variant called CHAINDROP emerged in August 2026, targeting a maintainer of the widely used `keyv` library and using stolen npm credentials to backdoor every other package that same maintainer had publish rights to. Over 400 packages were compromised; keyv alone received more than 600 million downloads per month [5].

In May 2026, Microsoft identified "Mini Shai-Hulud," which targeted the @antv organization and cascaded into libraries like echarts-for-react (over one million weekly downloads) [7]. A resurgence of Mini Shai-Hulud activity was noted in early 2026 by Microsoft Defender [6].

## How it spreads

The attack chain follows a consistent pattern across variants. After initial compromise, the malware scans for sensitive credentials using tools like TruffleHog to identify secrets, and additionally harvests environment variables and cloud service keys exposed through IMDS when available [3]. Stolen GitHub Personal Access Tokens are then abused: they authenticate to the npm registry as the compromised developer, inject malicious code into other packages, and publish those poisoned versions back to the public registry—enabling automatic propagation without further victim interaction [1][4].

In Shai-Hulud 2.0 and later variants (CHAINDROP), execution shifts from post-install to pre-install hooks in package.json, which run arbitrary commands before tests or security checks execute [5][6]. This bypasses static scanning tools that inspect code at later build stages. CHAINDROP specifically uses a dropper (`setup.mjs`) embedded across every subpackage of the compromised monorepo; worm-generated commits are identifiable by author name "claude" and commit message "chore: update config" [5].

Stolen credentials are exfiltrated to public GitHub repositories described as "Shai-Hulud" or "Sha1-Hulud: The Second Coming," enabling further lateral movement across cloud workloads (AWS, GCP, Azure) [3][4]. Mini Shai-Hulud additionally forges SLSA provenance data and scrapes process memory from GitHub Action runners to steal CI/CD secrets [7].

## Remediation steps

CISA recommends conducting a full dependency review of all software using the npm ecosystem: check `package-lock.json` or `yarn.lock` files to identify affected packages, including those nested in deeper dependency trees [1]. Organizations should pin package versions to known-safe releases produced before September 16, 2025 (the initial compromise date) and search artifact repositories for cached compromised versions [4].

Immediate credential rotation is essential across all developer accounts. Phishing-resistant multifactor authentication must be mandated on GitHub, npm, and cloud provider accounts—traditional MFA was bypassed by the stolen tokens in this campaign [1][6]. Network monitoring should block outbound connections to webhook.site domains (used for exfiltration) and inspect firewall logs for suspicious domain communications [5].

Microsoft Defender provides layered protection covering code scanning, posture management, and runtime detection specifically tuned against Shai-Hulud variants [6]. Elastic Security Labs recommends using supply-chain monitoring projects designed to detect malicious npm packages in real time [5].

## Sources

[1] CISA Alert – Widespread Supply Chain Compromise Impacting npm Ecosystem. https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[2] Wiz Research – Shai-Hulud npm Supply Chain Attack. https://www.wiz.io/blog/shai-hulud-npm-supply-chain-attack
[3] CISA Alert (same page as [1], referenced for timeline). https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem
[4] Unit 42 – Shai-Hulud strikes again: CHAINDROP worm hits 400+ npm packages. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
[5] Elastic Security Labs – CHAINDROP worm hits 400+ npm packages. https://www.elastic.co/security-labs/shai-hulud-chaindrop-npm-supply-chain
[6] Microsoft Security Blog – Shai-Hulud 2.0 guidance for detecting, investigating and defending against the supply chain attack. https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/
[7] Microsoft Security Blog – Mini Shai-Hulud: Compromised @antv npm packages enable CI/CD credential theft. https://www.microsoft.com/en-us/security/blog/2026/05/20/mini-shai-hulud-compromised-antv-npm-packages-enable-ci-cd-credential-theft/

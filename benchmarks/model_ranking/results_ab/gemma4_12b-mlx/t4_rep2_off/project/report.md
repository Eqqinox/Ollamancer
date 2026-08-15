## Timeline
The Shai-Hulud supply chain campaign began in late 2025, specifically identified as "Shai-Hulud 2.0" starting in early November 2025 [1]. This initial wave targeted the npm ecosystem by compromising tens of thousands of GitHub repositories and hundreds of software packages [1]. A significant resurgence occurred on May 11, 2026, labeled as "Mini Shai-Hulud," which expanded to include both npm and PyPI registries across over 400 malicious versions [2, 3]. By August 2026, a new iteration involving the CHAINDROP worm was identified, targeting high-traffic libraries like `keyv` [4]. This campaign represents an aggressive escalation in software supply chain threats by changing the point of infection to the pre-install phase.


## How it spreads
The malware primarily utilizes preinstall scripts in `package.json` files to execute arbitrary commands without human interaction during dependency installation [1, 4]. The infection process often begins by checking for a Bun runtime; if missing, the script downloads and installs it automatically [3, 4]. Once executed, the payload—often heavily obfuscated—scans for sensitive credentials including `.npmrc` files, environment variables (AWS, GCP, Azure), and specifically targets AI tooling tokens like Anthropic and OpenAI [1, 3, 4].

The worm employs a self-replicating mechanism: it uses stolen npm tokens to identify other packages maintained by the compromised developer. It then injects malicious code into those packages and publishes new versions to the registry, allowing for exponential propagation [1]. Additionally, some variants use "SessionStart" hooks in `.claude/settings.json` or folder-open tasks in VS Code's `tasks.json` to infect developers simply by opening an infected repository [4].

## Remediation steps
To mitigate these risks, organizations should implement strict credential management and monitoring:
- **Credential Protection**: Use dedicated secret management tools (e.g., HashiCorp Vault) and ensure that tokens are never stored in plain text or accessible to unauthorized processes [1, 3].
- **Commit Verification**: Enable mandatory commit signing to verify the identity of contributors and detect impersonation attempts using fake personas like "Linus Torvalds" [2].
- **Dependency Auditing**: Use tools to monitor for unexpected preinstall scripts or changes in common dependencies. Organizations should also audit their CI/CD pipelines to ensure that build environments are isolated from production secrets [1, 3].
- **Network Monitoring**: Monitor for unusual outbound connections to unknown domains or smart contract interactions, as the CHAINDROP worm uses Ethereum smart contracts to dynamically resolve C2 endpoints [4].

## Sources
1. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
2. https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/
3. https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/
4. https://www.elastic.co/security-labs/shai-hulud-chaindrop-npm-supply-chain

## Timeline
The Shai-Hulud worm campaign began in September 2025 with the compromise of several NPM packages, most notably `@ctrl/tinycolor` [1]. This initial wave targeted developers using Linux or macOS environments [1]. On November 24, 2025, a second, more aggressive wave known as "Shai-Hulud V2" (or "The Second Coming") was detected targeting the NPM ecosystem [2]. The campaign continued into 2026; on May 11, 2026, a variant dubbed "Mini Shai-Hulud" was deployed by the threat group TeamPCP, which rapidly published hundreds of malicious package versions across multiple ecosystems [3].

## How it spreads
The malware utilizes a sophisticated self-propagation engine to infect downstream dependencies [1]. Through its `NpmModule.updatePackage` function, the worm queries the NPM registry for up to 20 packages owned by a compromised maintainer and force-publishes malicious patches to them [1]. This creates a cascading effect across the ecosystem [1]. The malware is often triggered via hijacked `postinstall` scripts within a package's `package.json` [1]. In its 2026 "Mini" iteration, the spread was characterized by extreme velocity, with hundreds of malicious versions published across NPM and PyPI in under six hours [3].

## Remediation steps
To mitigate the risk of Shai-Hulud infection, developers should implement several security practices. First, audit all `.github/workflows` directories for unauthorized or suspicious workflow files, as the worm establishes persistence by injecting these to exfiltrate repository secrets [1]. Second, monitor environment variables and system processes for high-entropy strings; the malware specifically targets AWS, GCP, Azure, and GitHub credentials [1]. Third, utilize secret scanning tools like TruffleHog to detect potential credential leaks on local filesystems [1]. Finally, verify the integrity of dependencies by monitoring for unexpected changes in package ownership or sudden updates that may indicate a hijacked maintainer account [1].

## Sources
1. https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised
2. https://www.zscaler.com/blogs/security-research/shai-hulud-v2-poses-risk-npm-supply-chain
3. https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-ai-npm-supply-chain-attack-2026/

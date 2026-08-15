## Timeline
The Shai-Hulud campaign began with a self-replicating worm first investigated by researchers in September [1]. By November 25, 2025, the attack escalated into what was termed "Shai-Hulud 2.0" [1]. This updated phase was reported to be significantly wider in scope than previous iterations, affecting tens of thousands of GitHub repositories and approximately 350 unique users [1]. As of May 13, 2026, security updates indicated a resurgence of activity related to the campaign, often referred to as "Mini Shai-Hulud" [2].

## How it spreads
The Shai-Hulud worm utilizes automated propagation and self-replication to achieve massive scale within the npm ecosystem [1]. A critical mechanism in this attack is targeting the `preinstall` phase of malicious packages [1][2]. By executing code during this specific stage, the malware runs before any standard security checks or tests are performed [2]. This technique effectively eliminates the need for human interaction and allows the payload to bypass many static scanning tools that typically inspect code at later stages of a build process [1].

The attack has successfully compromised maintainer accounts from several widely used projects, including Zapier, PostHog, and Postman [2]. Once execution is achieved, the malware can perform various highly disruptive actions. It utilizes specific payload files such as `setup_bun.js` and `bun_environment.js` [1]. While primarily focused on harvesting high-value cloud credentials and configuration secrets from developer environments, CI/CD pipelines, and cloud-connected workloads, the campaign includes an aggressive fallback mechanism capable of attempting to destroy a user's entire home directory [1][2]. This capability can escalate the attack from simple espionage into a highly disruptive denial-of-service event that cripples enterprise development workflows [1]. Stolen data is exfiltrated to public GitHub repositories which are identified by the description “Sha1-Hulud: The Second Coming” [1].

## Remediation steps
Defending against Shai-Hulud requires a layered, defense-in-depth strategy because traditional network defenses and static analysis tools are often insufficient against threats embedded directly into trusted package workflows [2]. Security teams should implement monitoring that correlates telemetry across multiple data planes, such as endpoint behavior, container activity, and runtime anomalies [2].

Current security coverage includes platforms like Microsoft Defender, which provides protection for the recent resurgence of "Mini Shai-Hulud" activity observed in mid-2026 [2]. Organizations are encouraged to maintain strict oversight of their CI/CD pipelines and developer environments to detect suspicious package behavior or unauthorized attempts to access configuration secrets [2].

## Sources
1. https://unit42.paloaltonetworks.com/npm-supply-chain-attack/
2. https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/

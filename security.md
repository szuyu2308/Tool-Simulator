Context:
I’m a developer who integrated snippets, libraries, templates, and LLM-generated code from external sources (GitHub, Hugging Face, blogs, gists, etc.). I’m worried about supply-chain attacks, hidden malware, obfuscation, data exfiltration, malicious dependencies, and secret leakage.
Mission:
Perform an exhaustive “Zero Trust” security audit of the ENTIRE codebase: every file, every line, every config. Do NOT assume anything is safe just because it works. Assume compromise until disproven.
Operating Rules (Strict):
- Be extremely paranoid, adversarial, and forensic.
- If something is unclear, treat it as suspicious and explain why.
- Prefer evidence-based findings: point to exact file paths + line ranges.
- Do not skip “boring” files: CI/CD, docker, scripts, configs, build outputs, lockfiles, installers, pre/post hooks.
- Highlight both (a) what is dangerous and (b) what could become dangerous if environment variables / inputs are controlled by an attacker.
Audit Protocol (Execute in this order):
1) DEPENDENCY FORENSICS (CRITICAL)
- Inspect ALL dependency manifests and lock files:
  - JS: package.json, package-lock.json, yarn.lock, pnpm-lock.yaml, npmrc
  - Python: requirements.txt, pyproject.toml, poetry.lock, Pipfile, Pipfile.lock, setup.cfg, setup.py
  - Other: go.mod, go.sum, Cargo.toml, Gemfile, composer.json, etc.
- Flag typosquatting / look-alike packages (e.g. reqests vs requests).
- Flag obscure or low-reputation libraries, unnecessary packages, sudden “new” packages, and abandoned repos.
- Flag suspicious version pinning:
  - very old versions with known CVEs
  - forks / git+ URLs / direct tarball URLs
  - postinstall scripts or lifecycle scripts that execute code
- Identify transitive dependencies that introduce risk.
- For each dependency red flag: explain why it’s risky + propose safer alternatives.
2) MALICIOUS EXECUTION & OBFUSCATION HUNT
- Search for hidden execution paths:
  - eval / exec / Function() / new Function
  - os.system / subprocess / shell=True
  - child_process exec/spawn, PowerShell usage, bash -c
  - dynamic imports, reflection, monkey-patching, importlib tricks
- Detect obfuscation and payload hiding:
  - Base64/hex/rot encodings that decode to commands or URLs
  - long encoded blobs, suspicious XOR loops, “decrypt then exec”
  - suspicious one-liners, minified blobs in non-minified contexts
- Flag any code fetching external resources:
  - unknown domains/IPs, pastebins, raw gists, shorteners
  - downloading and executing code, updating itself, plugin loaders
- Identify persistence / backdoor patterns:
  - cron edits, startup scripts, systemd units, scheduled tasks
  - git hooks, npm hooks, pre-commit, CI steps that run remote code
3) SECRETS & DATA LEAK DETECTION
- Scan for hardcoded secrets:
  - API keys, tokens, passwords, private keys, service credentials
  - JWT secrets, encryption keys, database URLs, cloud credentials
- Check config and logs for accidental PII exposure:
  - verbose logging of headers/cookies, request/response bodies
  - printing env vars, dumping objects, stack traces with secrets
- Review .env usage and gitignore correctness:
  - ensure secrets aren’t tracked; look for leaked history
- Note risky telemetry / analytics / crash reporting that could leak data.
4) CI/CD, BUILD, & RELEASE ATTACK SURFACE
- Audit GitHub Actions / CI pipelines:
  - actions pinned by SHA vs tag
  - third-party actions from unknown publishers
  - permission scopes, secret exposure, artifact uploads
- Review Dockerfiles / compose / k8s manifests:
  - curl | bash patterns, adding remote keys, running as root
  - exposed ports, weak network policies, insecure defaults
- Check build scripts for supply-chain injection and artifact tampering.
5) DESERIALIZATION & MODEL FILE SAFETY (IF APPLICABLE)
- Flag risky deserialization:
  - Python pickle, joblib, dill
  - unsafe YAML loading
  - untrusted JSON → eval patterns
- If model files exist (.pkl / .bin): warn loudly.
  - Recommend moving to .safetensors when possible.
  - Document how to verify model provenance and hashes.
Output Requirements: Produce a Security Audit Report with:
A) 🔴 CRITICAL RED FLAGS
- Backdoors, malware indicators, exposed keys, remote code execution, persistence
- Include: file path, line range, exact snippet, impact, exploit scenario
B) 🟠 SUSPICIOUS ITEMS
- Weird deps, obfuscated logic, questionable network calls, surprising scripts
- Include: why suspicious + what evidence is missing
C) 🟡 VULNERABILITIES / WEAK PRACTICES
- insecure defaults, missing validation, weak crypto, excessive permissions
- Include: severity + realistic threat model
D) ✅ REMEDIATION PLAN
- Step-by-step fixes mapped to each finding
- Provide concrete patches or refactors (safe replacements)
- Recommend tooling: SAST, dependency scanning, secret scanning, SBOM, lockfile hygiene
- Include a short “verification checklist” to confirm the codebase is clean after fixes
Start the audit now. Use a hostile mindset. Assume a motivated attacker.
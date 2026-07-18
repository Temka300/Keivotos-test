# Security policy

## Supported versions

Security fixes go into the current release line only. Old development
snapshots and test builds are not supported.

## Reporting a vulnerability

Please don't put credentials, private media paths, local databases, or a
working exploit in a public issue. Use GitHub's private vulnerability
reporting (Security tab → "Report a vulnerability") if it is enabled on this
repository; otherwise open a minimal issue asking for a private contact and
leave the sensitive details out.

Include the affected version, your platform, the impact, any prerequisites,
and the smallest safe reproduction you have. Keivotos runs locally, but the
browser/server boundary, archive extraction, path validation, and the
gallery-dl/FFmpeg child processes are all still security-sensitive.

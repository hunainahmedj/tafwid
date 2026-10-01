# Security and privacy

Tafwid runs local coding-agent tools with the permissions configured by the
user. Only use trusted workspaces: backend configuration and plugin hooks may
execute, and a read-only assignment is not an operating-system sandbox.

Local run records may contain private prompts, paths, code and output. Keep
these files private and outside source control.

Do not post secrets or private transcripts in public issues. Report a suspected
security vulnerability through GitHub's private vulnerability reporting feature
when enabled. Otherwise contact the repository maintainer privately before
sharing exploit details or sensitive evidence. No response-time guarantee is
offered for this personal project.

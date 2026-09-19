# Security and privacy

Tafwid runs local coding-agent tools with the permissions configured by the
user. Only use trusted workspaces: backend configuration and plugin hooks may
execute, and a read-only assignment is not an operating-system sandbox.

The dashboard binds to loopback and protects private APIs with a local token and
Host/Origin checks. Do not expose it through a public proxy or share its tokenized
URL. Local run records may contain private prompts, paths, code and output.

Do not post secrets or private transcripts in public issues. Report a suspected
security vulnerability through GitHub's private vulnerability reporting feature
when enabled. Otherwise contact the repository maintainer privately before
sharing exploit details or sensitive evidence. No response-time guarantee is
offered for this personal project.

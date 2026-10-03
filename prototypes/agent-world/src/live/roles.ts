import type { Role } from "./types";

// Order decides precedence: the first role with a keyword at the start of a
// word in the lower-cased "<agentType> <label>" text wins ("orchestrator"
// matches "orchestrat", "latest" does not match "test"). Unmatched text is an
// implementer. The session's main agent is a coordinator by construction in
// the fold, not by keyword.
const ROLE_KEYWORDS: ReadonlyArray<readonly [Role, readonly string[]]> = [
  ["coordinator", ["orchestrat", "coordinat", "plan"]],
  ["reviewer", ["review", "audit", "critique", "verify"]],
  ["documenter", ["doc", "readme", "write-up", "changelog", "spec"]],
  ["tester", ["test", "qa", "e2e"]],
  ["researcher", ["explore", "research", "investigate", "search", "explorer"]],
  ["implementer", ["implement", "build", "fix", "worker", "general-purpose"]],
];

// Keywords that are a common prefix of unrelated words match only as the word
// itself or its documentation forms ("docker" and "specific" are not docs).
const WORD_FORMS: Readonly<Record<string, string>> = {
  doc: "doc(?:s|ument[a-z]*)?(?![a-z0-9])",
  spec: "spec(?:s|ification[a-z]*)?(?![a-z0-9])",
};

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const MATCHERS: ReadonlyArray<readonly [Role, readonly RegExp[]]> = ROLE_KEYWORDS.map(
  ([role, keywords]) => [
    role,
    keywords.map((keyword) => new RegExp(`(?:^|[^a-z0-9])${WORD_FORMS[keyword] ?? escape(keyword)}`)),
  ],
);

export function classifyRole(
  agentType: string | null,
  label: string | null,
  override: Role | null,
): Role {
  if (override) return override;
  const text = `${agentType ?? ""} ${label ?? ""}`.toLowerCase();
  for (const [role, patterns] of MATCHERS) {
    if (patterns.some((pattern) => pattern.test(text))) return role;
  }
  return "implementer";
}

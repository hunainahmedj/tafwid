import type { Role } from "./types";

// Order decides precedence: the first role whose keyword appears in the
// lower-cased "<agentType> <label>" text wins. Unmatched text is an
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

export function classifyRole(
  agentType: string | null,
  label: string | null,
  override: Role | null,
): Role {
  if (override) return override;
  const text = `${agentType ?? ""} ${label ?? ""}`.toLowerCase();
  for (const [role, keywords] of ROLE_KEYWORDS) {
    if (keywords.some((keyword) => text.includes(keyword))) return role;
  }
  return "implementer";
}

import { describe, expect, it } from "vitest";
import { classifyRole } from "../../src/live/roles";
import type { Role } from "../../src/live/types";

const table: Array<[Role, string[]]> = [
  ["coordinator", ["orchestrat", "coordinat", "plan"]],
  ["implementer", ["implement", "build", "fix", "worker", "general-purpose"]],
  ["reviewer", ["review", "audit", "critique", "verify"]],
  ["documenter", ["doc", "readme", "write-up", "changelog", "spec"]],
  ["researcher", ["explore", "research", "investigate", "search", "explorer"]],
  ["tester", ["test", "qa", "e2e"]],
];

describe("classifyRole", () => {
  for (const [role, keywords] of table) {
    for (const keyword of keywords) {
      it(`maps "${keyword}" in the agent type to ${role}`, () => {
        expect(classifyRole(keyword, null, null)).toBe(role);
      });
      it(`maps "${keyword}" in the label to ${role}`, () => {
        expect(classifyRole(null, `Task: ${keyword.toUpperCase()} things`, null)).toBe(role);
      });
    }
  }

  it("matches case-insensitively over type and label together", () => {
    expect(classifyRole("Explore", null, null)).toBe("researcher");
    expect(classifyRole("general", "Code Reviewer", null)).toBe("reviewer");
  });

  it("lets an override win over any keyword", () => {
    expect(classifyRole("code-reviewer", "review everything", "tester")).toBe("tester");
    expect(classifyRole(null, null, "documenter")).toBe("documenter");
  });

  it("follows table order for precedence", () => {
    expect(classifyRole(null, "review the implementation", null)).toBe("reviewer");
    expect(classifyRole(null, "write docs for the test suite", null)).toBe("documenter");
    expect(classifyRole(null, "plan the build", null)).toBe("coordinator");
    expect(classifyRole(null, "test the search box", null)).toBe("tester");
  });

  it("falls back to implementer when nothing matches", () => {
    expect(classifyRole("zebra", "paint the fence", null)).toBe("implementer");
    expect(classifyRole(null, null, null)).toBe("implementer");
    expect(classifyRole("", "", null)).toBe("implementer");
  });
});

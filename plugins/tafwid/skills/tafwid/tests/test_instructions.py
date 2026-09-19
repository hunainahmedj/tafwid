"""Instruction routing tests use local packages, not model calls."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


class InstructionTests(unittest.TestCase):
    def setUp(self):
        import instructions
        self.api = instructions
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def skill(self, directory, body="One selected policy."):
        root = self.root / directory
        root.mkdir(parents=True)
        path = root / "SKILL.md"
        path.write_text("---\nname: checking\ndescription: checks\n---\n" + body)
        return path

    def test_exact_package_match_uses_one_native_reference(self):
        source, native = self.skill("source"), self.skill("native")
        text, manifest = self.api.prepare([source, source], "task", native=[
            {"path": native, "name": "tools:checking", "version": "1"}])
        self.assertNotIn("One selected policy", text)
        self.assertEqual(text.count("tools:checking"), 1)
        self.assertEqual(manifest["instructions"][0]["delivery"], "native")

    def test_different_body_and_different_resource_do_not_match(self):
        source, native = self.skill("source"), self.skill("native", "Different policy")
        candidates = [{"path": native, "name": "tools:checking", "version": "1"}]
        text, _ = self.api.prepare([source], "task", native=candidates)
        self.assertIn("One selected policy", text)
        native.write_text(source.read_text())
        (native.parent / "rules.md").write_text("An additional rule")
        text, _ = self.api.prepare([source], "task", native=candidates)
        self.assertIn("One selected policy", text)

    def test_external_resource_and_symlink_are_not_assumed_equivalent(self):
        source = self.skill("source", "See [shared](../shared.md).")
        native = self.skill("native", "See [shared](../shared.md).")
        (self.root / "shared.md").write_text("External dependency")
        text, _ = self.api.prepare([source], "task", native=[{"path": native, "name": "tools:checking"}])
        self.assertIn("See [shared]", text)
        source.write_text("---\nname: checking\n---\nSame")
        native.write_text(source.read_text())
        (source.parent / "reference.md").symlink_to(self.root / "shared.md")
        (native.parent / "reference.md").symlink_to(self.root / "shared.md")
        text, _ = self.api.prepare([source], "task", native=[{"path": native, "name": "tools:checking"}])
        self.assertNotIn("Use Skill", text)

    def test_ambiguous_native_name_falls_back_to_selected_source(self):
        source = self.skill("source")
        first, second = self.skill("one"), self.skill("two", "Other policy")
        text, _ = self.api.prepare([source], "task", native=[
            {"path": first, "name": "tools:checking"}, {"path": second, "name": "tools:checking"}])
        self.assertIn("One selected policy", text)

    def test_plain_instruction_already_in_brief_is_not_appended(self):
        path = self.root / "role.md"
        path.write_text("Unique instructions.")
        text, manifest = self.api.prepare([path], "Task. Unique instructions.")
        self.assertEqual(text, "")
        self.assertEqual(manifest["instructions"][0]["delivery"], "brief")

    def test_omitted_instruction_survives_resume_manifest_chain(self):
        a, b = self.root / "a.md", self.root / "b.md"
        a.write_text("Instruction A"); b.write_text("Instruction B")
        _, first = self.api.prepare([a], "task")
        _, second = self.api.prepare([b], "follow-up", previous=first)
        text, third = self.api.prepare([a, b], "third", previous=second)
        self.assertEqual(text, "")
        self.assertEqual(len(third["instructions"]), 2)

    def test_changed_package_resource_is_forwarded_on_resume(self):
        source = self.skill("source", "Read [rules](rules.md).")
        dep = source.parent / "rules.md"
        dep.write_text("Before")
        _, first = self.api.prepare([source], "task")
        dep.write_text("After")
        text, _ = self.api.prepare([source], "follow-up", previous=first)
        self.assertIn("replaces", text)

    def test_no_instructions_add_no_worker_context(self):
        text, manifest = self.api.prepare([], "task")
        self.assertEqual(text, "")
        self.assertEqual(manifest["emitted_characters"], 0)

    def test_external_plugin_root_resources_prevent_native_equivalence(self):
        body = 'Read "${CLAUDE_PLUGIN_ROOT}/references/shared.md" before work.'
        source, native = self.skill("source", body), self.skill("native", body)
        text, _ = self.api.prepare([source], "task", native=[{"path": native, "name": "tools:checking"}])
        self.assertIn(body, text)
        self.assertNotIn("Use Skill", text)

    def test_user_only_and_forking_skills_are_supplied_without_native_invocation(self):
        for index, setting in enumerate(("disable-model-invocation: true", "disable-model-invocation: on",
                                        "context: fork", "hooks: {}", "allowed-tools: Bash")):
            source, native = self.skill(f"source-{index}"), self.skill(f"native-{index}")
            body = source.read_text().replace("description: checks", setting)
            source.write_text(body); native.write_text(body)
            text, _ = self.api.prepare([source], "task", native=[{"path": native, "name": "tools:checking"}])
            self.assertIn("One selected policy", text)
            self.assertNotIn("Use Skill", text)

    def test_identical_role_text_keeps_distinct_relative_resource_origins(self):
        paths = []
        for dirname in ("one", "two"):
            root = self.root / dirname
            root.mkdir()
            path = root / "role.md"
            path.write_text("Read `rules.md` before working.")
            (root / "rules.md").write_text(dirname)
            paths.append(path)
        text, prior = self.api.prepare(paths, "task")
        self.assertEqual(text.count("Read `rules.md`"), 2)
        (paths[0].parent / "rules.md").write_text("Changed rule")
        text, _ = self.api.prepare([paths[0]], "follow-up", previous=prior)
        self.assertIn("Read `rules.md`", text)

    def test_skill_override_settings_prevent_native_invocation(self):
        source = self.skill("source")
        config = self.root / "config"
        native = config / "skills/checking"
        native.mkdir(parents=True)
        (native / "SKILL.md").write_text(source.read_text())
        (config / "settings.json").write_text(json.dumps({"skillOverrides": {"checking": "off"}}))
        with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}):
            text, data = self.api.prepare([source], "task", claude="must-not-run", cwd=self.root)
        self.assertIn("One selected policy", text)
        self.assertNotIn("Use Skill", text)


if __name__ == "__main__":
    unittest.main()

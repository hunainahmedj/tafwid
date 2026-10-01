import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import host
import settings

A = "00000000-0000-4000-8000-000000000001"
B = "00000000-0000-4000-8000-000000000002"


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'CODEX_HOME': self.temp.name, 'TAFWID_HOST': 'codex',
                                          'TAFWID_HOME': str(Path(self.temp.name) / 'tafwid')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_default_persistence_validation_and_private_file(self):
        self.assertEqual(settings.read()['permission_policy'], 'scoped')
        self.assertFalse(settings.settings_file().exists())
        for policy in settings.POLICIES:
            data = {'version': 1, 'permission_policy': policy}
            settings.save(data)
            self.assertEqual(settings.read()['permission_policy'], policy)
        self.assertEqual(settings.settings_file().stat().st_mode & 0o777, 0o600)
        for invalid in ({}, {'version': True, 'permission_policy': 'full'},
                        {'version': 1, 'permission_policy': []},
                        {'version': 1, 'permission_policy': 'full', 'extra': 1}):
            with self.assertRaises(ValueError):
                settings.save(invalid)
        self.assertEqual(settings.read()['permission_policy'], 'inherit')

    def test_upgrade_preserves_permission_and_legacy_save_preserves_models(self):
        settings.settings_file().parent.mkdir(parents=True)
        settings.settings_file().write_text(json.dumps({"version": 1, "permission_policy": "inherit"}))
        data = settings.read()
        self.assertEqual(data["version"], 3)
        self.assertEqual(data["permission_policy"], "inherit")
        data["models"]["profiles"]["deep"] = "opus"
        data["models"]["tasks"]["architecture"] = "fable"
        settings.save(data)
        settings.save({"version": 1, "permission_policy": "scoped"})
        saved = settings.read()
        self.assertEqual(saved["models"]["profiles"]["deep"], "opus")
        self.assertEqual(saved["models"]["tasks"]["architecture"], "fable")
        self.assertEqual(saved["permission_policy"], "scoped")

    def test_invalid_model_map_never_changes_saved_settings(self):
        data = settings.read()
        self.assertIn("models", data)
        settings.save(data)
        previous = settings.settings_file().read_bytes()
        for key, value in (("architecture", "unknown"), ("made_up", "opus"), ("final_review", [])):
            invalid = json.loads(json.dumps(data))
            invalid["models"]["tasks"][key] = value
            with self.assertRaises(ValueError):
                settings.save(invalid)
            self.assertEqual(settings.settings_file().read_bytes(), previous)

    def test_permission_cli_preserves_custom_routing(self):
        data = settings.read()
        data["models"]["tasks"]["final_review"] = "opus"
        settings.save(data)
        result = subprocess.run([sys.executable, str(Path(settings.__file__)), "set", "--policy", "inherit", "--global"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(result.stdout)
        self.assertEqual(saved["permission_policy"], "inherit")
        self.assertEqual(saved["models"]["tasks"]["final_review"], "opus")

    def test_task_snapshot_survives_global_changes_and_new_task_gets_new_defaults(self):
        initial = settings.read()
        initial['models']['tasks']['implementation'] = 'opus'
        initial['permission_policy'] = 'full'
        settings.save(initial)
        first = settings.read(A)
        changed = settings.read()
        changed['models']['tasks']['implementation'] = 'sonnet'
        changed['permission_policy'] = 'scoped'
        settings.save(changed)
        self.assertEqual(settings.read(A), first)
        self.assertEqual(settings.read(A)['models']['tasks']['implementation'], 'opus')
        self.assertEqual(settings.read(A)['permission_policy'], 'full')
        self.assertEqual(settings.read(B)['models']['tasks']['implementation'], 'sonnet')
        self.assertEqual(settings.read(B)['permission_policy'], 'scoped')
        self.assertEqual(settings.read(A)['harness'], 'claude')
        self.assertEqual(settings.settings_file(A).stat().st_mode & 0o777, 0o600)

    def test_task_changes_preserve_other_tasks_and_global_defaults(self):
        defaults = settings.read()
        settings.save(defaults)
        settings.read(B)
        original_global = settings.settings_file().read_bytes()
        original_b = settings.settings_file(B).read_bytes()
        task = settings.read(A)
        task['models']['tasks']['testing'] = 'sonnet'
        settings.save(task, A)
        settings.save({'version': 1, 'permission_policy': 'full'}, A)
        self.assertEqual(settings.read(A)['permission_policy'], 'full')
        self.assertEqual(settings.read(A)['models']['tasks']['testing'], 'sonnet')
        self.assertEqual(settings.settings_file().read_bytes(), original_global)
        self.assertEqual(settings.settings_file(B).read_bytes(), original_b)

    def test_settings_cli_defaults_to_current_task_and_global_requires_flag(self):
        settings.save(settings.read())
        global_before = settings.settings_file().read_bytes()
        env = {**os.environ, 'CODEX_THREAD_ID': A}
        command = [sys.executable, settings.__file__]
        result = subprocess.run([*command, 'set', '--policy', 'full'], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['harness'], 'claude')
        self.assertEqual(settings.settings_file().read_bytes(), global_before)
        shown = subprocess.run([*command, 'show'], env=env, capture_output=True, text=True)
        self.assertEqual(json.loads(shown.stdout)['permission_policy'], 'full')
        result = subprocess.run([*command, 'set', '--policy', 'inherit', '--global'], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(settings.read()['permission_policy'], 'inherit')
        self.assertEqual(settings.read(A)['permission_policy'], 'full')

    def test_corrupt_task_snapshot_never_falls_back_to_global(self):
        settings.read(A)
        target = settings.settings_file(A)
        target.write_text('{"permission_policy": "full"}')
        before = target.read_bytes()
        with self.assertRaises(ValueError):
            settings.read(A)
        self.assertEqual(target.read_bytes(), before)

    def test_missing_identity_requires_explicit_global_cli(self):
        env = {k: v for k, v in os.environ.items() if k not in ('CODEX_THREAD_ID', 'CODEX_SESSION_ID')}
        result = subprocess.run([sys.executable, settings.__file__, 'set', '--policy', 'full'],
                                env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        result = subprocess.run([sys.executable, settings.__file__, 'show', '--global'],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_parallel_initialization_cannot_overwrite_task_update(self):
        env = {**os.environ, 'CODEX_THREAD_ID': A}
        command = [sys.executable, settings.__file__]
        with subprocess.Popen([*command, 'set', '--policy', 'full'], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as update:
            readers = [subprocess.Popen([*command, 'show'], env=env, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True) for _ in range(4)]
            try:
                for reader in readers:
                    stdout, stderr = reader.communicate(timeout=5)
                    self.assertEqual(reader.returncode, 0, stderr)
                    self.assertEqual(json.loads(stdout)['harness'], 'claude')
                stdout, stderr = update.communicate(timeout=5)
                self.assertEqual(update.returncode, 0, stderr)
            finally:
                for process in [update, *readers]:
                    if process.poll() is None:
                        process.kill()
                    process.communicate()
        self.assertEqual(settings.read(A)['permission_policy'], 'full')

    def test_bad_task_identity_cannot_write_outside_task_directory(self):
        with self.assertRaises(ValueError):
            settings.read('../../outside')
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_inherit_follows_each_coordinator(self):
        config = {**settings.defaults(), 'permission_policy': 'inherit'}
        with patch.dict(os.environ, {'CODEX_THREAD_ID': A, 'CODEX_PERMISSION_PROFILE': ':danger-full-access'}):
            result = settings.resolve(config=config)
            self.assertEqual((result['effective'], result['coordinator_full_access']), ('full', True))
            self.assertIn('Codex', result['reason'])
            self.assertNotIn('codex_full_access', result)
        claude = {'TAFWID_HOST': 'claude', 'CLAUDE_CODE_SESSION_ID': B}
        with patch.dict(os.environ, claude):
            self.assertEqual(settings.resolve(config=config)['effective'], 'scoped')  # hooks never ran
            host.record_seen(B, 'acceptEdits')
            self.assertEqual(settings.resolve(config=config)['effective'], 'scoped')
            host.record_seen(B, 'bypassPermissions')
            result = settings.resolve(config=config)
            self.assertEqual((result['effective'], result['claude_mode']), ('full', 'bypassPermissions'))
            self.assertIn('Claude Code', result['reason'])


if __name__ == '__main__':
    unittest.main()

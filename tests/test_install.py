import json

from team import install, settings
from team.paths import TEAM_HOME
from tests.helpers import TempProjectCase


class InstallTest(TempProjectCase):
    def code_style(self) -> object:
        path = self.root / "CODE_STYLE.md"
        path.write_text("# rules\n", encoding="utf-8")

        return path

    def test_sources_are_valid(self) -> None:
        self.assertEqual(install.validate_sources(), [])

    def test_install_renders_and_is_idempotent(self) -> None:
        report = install.install_user(self.code_style())
        agent = (self.home / "agents" / "team-reviewer.agent.md").read_text(encoding="utf-8")
        hooks_file = json.loads((self.home / "hooks" / "team.json").read_text(encoding="utf-8"))

        self.assertNotIn("{{TEAM}}", agent)
        self.assertIn(str(TEAM_HOME / "team.py"), agent)
        self.assertIn("powershell", hooks_file["hooks"]["preToolUse"][0])
        self.assertFalse(report.errors)

        second = install.install_user(self.code_style())

        self.assertTrue(all(" ok " in line for line in second.lines if str(self.home) in line))

    def test_hand_edited_file_is_not_replaced(self) -> None:
        install.install_user(self.code_style())
        agent = self.home / "agents" / "team-writer.agent.md"
        agent.write_text("mine\n", encoding="utf-8")

        report = install.install_user(self.code_style())

        self.assertEqual(agent.read_text(encoding="utf-8"), "mine\n")
        self.assertTrue(report.errors)

    def test_uninstall_removes_only_ours(self) -> None:
        install.install_user(self.code_style())
        own = self.home / "agents" / "my-agent.agent.md"
        own.write_text("keep\n", encoding="utf-8")

        install.uninstall_user()

        self.assertTrue(own.exists())
        self.assertFalse((self.home / "agents" / "team-writer.agent.md").exists())


class SettingsTest(TempProjectCase):
    def test_apply_keeps_other_keys(self) -> None:
        (self.home / "settings.json").write_text(
            '{"model": "x", "subagents": {"agents": {"mine": {}}}}'
        )

        settings.apply({"team-reviewer": {"model": "m1", "effort": "high"}})

        data = json.loads((self.home / "settings.json").read_text())
        self.assertEqual(data["model"], "x")
        self.assertIn("mine", data["subagents"]["agents"])
        self.assertEqual(data["subagents"]["agents"]["team-reviewer"]["model"], "m1")
        self.assertTrue((self.home / "settings.json.team-bak").exists())

    def test_invalid_json_is_never_rewritten(self) -> None:
        original = "// comment\n{}"
        (self.home / "settings.json").write_text(original)

        result = settings.apply({"team-reviewer": {"model": "m1"}})

        self.assertIn("Paste this yourself", result.message)
        self.assertEqual((self.home / "settings.json").read_text(), original)

    def test_refuses_non_team_agent(self) -> None:
        result = settings.apply({"code-review": {"model": "m1"}})

        self.assertIn("only team-*", result.message)

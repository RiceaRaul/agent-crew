import json

from team import hooks, state, workflow
from tests.helpers import TempProjectCase


class HooksTest(TempProjectCase):
    def start_full_item(self) -> state.State:
        item = state.new_state("Refactor", "full", "high", "analyze")
        workflow.enter_phase(self.root, item, "analyze")
        state.save(self.root, item)
        state.set_current(self.root, item["id"])

        return item

    def pre_tool(self, tool: str, args: dict) -> dict | None:
        data = {"cwd": str(self.root), "toolName": tool, "toolArgs": json.dumps(args)}

        return hooks.on_pre_tool(data)

    def test_no_active_item_means_no_op(self) -> None:
        self.assertIsNone(self.pre_tool("edit", {"path": "src/a.cs"}))

    def test_code_edit_denied_before_design_approval(self) -> None:
        self.start_full_item()

        output = self.pre_tool("edit", {"path": str(self.root / "src" / "a.cs")})

        self.assertEqual(output["permissionDecision"], "deny")

    def test_doc_edit_allowed_before_design_approval(self) -> None:
        self.start_full_item()

        self.assertIsNone(self.pre_tool("create", {"path": "docs/notes.md"}))

    def test_state_file_edit_denied(self) -> None:
        item = self.start_full_item()

        output = self.pre_tool("edit", {"path": f".ai/work/{item['id']}/state.json"})

        self.assertEqual(output["permissionDecision"], "deny")

    def test_agent_cannot_run_approve(self) -> None:
        self.start_full_item()

        output = self.pre_tool(
            "bash", {"command": '"/usr/bin/python3" "/x/team.py" approve design'}
        )

        self.assertEqual(output["permissionDecision"], "deny")

    def test_patch_paths_are_checked(self) -> None:
        self.start_full_item()
        patch = "*** Begin Patch\n*** Update File: src/a.ts\n@@\n-x\n+y\n*** End Patch"

        output = self.pre_tool("apply_patch", {"input": patch})

        self.assertEqual(output["permissionDecision"], "deny")

    def test_doc_only_denies_source_edit(self) -> None:
        data = {
            "cwd": str(self.root),
            "toolName": "edit",
            "toolArgs": json.dumps({"path": "src/x.cs"}),
        }

        self.assertEqual(hooks.on_doc_only(data)["permissionDecision"], "deny")

    def test_agent_stop_blocks_when_gates_stale(self) -> None:
        item = self.start_full_item()
        item["phase"] = "implement"
        state.save(self.root, item)

        output = hooks.on_agent_stop({"cwd": str(self.root), "stop_hook_active": False})

        self.assertEqual(output["decision"], "block")
        self.assertIsNone(hooks.on_agent_stop({"cwd": str(self.root), "stop_hook_active": True}))

    def test_subagent_stop_records_handoff(self) -> None:
        self.start_full_item()
        data = {
            "cwd": str(self.root),
            "agentName": "team-analyst",
            "response": "Brief done\nNo risks",
        }

        hooks.on_subagent_stop(data)

        loaded = state.load(self.root)
        self.assertEqual(loaded["handoffs"][-1]["from"], "team-analyst")

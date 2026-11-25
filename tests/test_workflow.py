from team import artifacts, state, workflow
from tests.helpers import TempProjectCase


class WorkflowTest(TempProjectCase):
    def make_item(self, track: str = "full") -> state.State:
        first = workflow.phases(track)[0]["name"]
        item = state.new_state("State to pipeline", track, "high", first)
        workflow.enter_phase(self.root, item, first)
        state.save(self.root, item)
        state.set_current(self.root, item["id"])

        return item

    def fill(self, item: state.State, name: str) -> None:
        (state.item_dir(self.root, item["id"]) / name).write_text("# filled\n", encoding="utf-8")

    def test_next_refuses_while_template_has_todo(self) -> None:
        item = self.make_item()

        refusal = workflow.advance(self.root, item)

        self.assertIsNotNone(refusal)
        self.assertIn("brief.md", refusal.message)

    def test_design_needs_approval_before_stories(self) -> None:
        item = self.make_item()
        self.fill(item, "brief.md")
        self.assertIsNone(workflow.advance(self.root, item))
        self.fill(item, "adr.md")

        refusal = workflow.advance(self.root, item)

        self.assertIn("approval", refusal.message)
        self.assertTrue(workflow.is_code_locked(item))
        self.assertIsNone(workflow.approve(self.root, item, "design", "tester"))
        self.assertIsNone(workflow.advance(self.root, item))
        self.assertEqual(item["phase"], "stories")
        self.assertFalse(workflow.is_code_locked(item))

    def test_reopen_design_clears_design_approval(self) -> None:
        item = self.make_item()
        item["approvals"]["design"] = {"by": "x", "at": "y"}
        item["phase"] = "implement"

        self.assertIsNone(workflow.reopen(self.root, item, "design"))
        self.assertIsNone(item["approvals"]["design"])

    def test_quick_track_needs_filled_story(self) -> None:
        item = self.make_item("quick")
        artifacts.create_story(self.root, item, "S1", "Fix typo")
        item["stories"].append({"id": "S1", "title": "Fix typo", "status": "todo"})

        refusal = workflow.advance(self.root, item)

        self.assertIn("S1.md", refusal.message)

    def test_review_needs_pass_and_fresh_green_gates(self) -> None:
        item = self.make_item("quick")
        item["phase"] = "review"
        artifacts.ensure_document(self.root, item, "review.md")
        (state.item_dir(self.root, item["id"]) / "review.md").write_text("Verdict: pass\n")

        refusal = workflow.output_problem(self.root, item, "review-pass")

        self.assertIn("gates never ran", refusal)

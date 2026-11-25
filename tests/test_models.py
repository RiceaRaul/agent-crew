import unittest

from team import models


def config(**overrides: object) -> dict:
    base = {
        "favorites": [],
        "catalog": {
            "fast-a": {"tier": "fast", "cost": 1},
            "std-a": {"tier": "standard", "cost": 2},
            "std-b": {"tier": "standard", "cost": 1},
            "strong-a": {"tier": "strong", "cost": 3},
            "premium-a": {"tier": "premium", "cost": 4},
        },
        "pins": {},
        "roleDifficulty": {"team-writer": "low", "team-reviewer": "high"},
        "allowPremiumWithoutAsking": False,
    }
    base.update(overrides)

    return base


class ProposeTest(unittest.TestCase):
    def test_pin_always_wins(self) -> None:
        proposal = models.propose("team-writer", "low", config(pins={"team-writer": "premium-a"}))

        self.assertEqual(proposal.model, "premium-a")

    def test_empty_favorites_picks_cheapest_in_tier(self) -> None:
        proposal = models.propose("team-implementer", "medium", config())

        self.assertEqual(proposal.model, "std-b")

    def test_favorite_beats_cheaper_catalog_model_in_same_tier(self) -> None:
        proposal = models.propose("team-implementer", "medium", config(favorites=["std-a"]))

        self.assertEqual(proposal.model, "std-a")

    def test_role_difficulty_is_a_floor(self) -> None:
        proposal = models.propose("team-reviewer", "low", config())

        self.assertEqual(proposal.model, "strong-a")
        self.assertEqual(proposal.effort, "high")

    def test_task_raises_role_at_most_one_level(self) -> None:
        self.assertEqual(models.effective_difficulty("team-writer", "critical", config()), "medium")
        self.assertEqual(
            models.effective_difficulty("team-reviewer", "critical", config()), "critical"
        )

    def test_critical_never_picks_premium_unasked(self) -> None:
        proposal = models.propose("team-reviewer", "critical", config())

        self.assertEqual(proposal.model, "strong-a")
        self.assertEqual(proposal.upgrade, "premium-a")

    def test_critical_uses_premium_when_allowed(self) -> None:
        proposal = models.propose(
            "team-reviewer",
            "critical",
            config(allowPremiumWithoutAsking=True),
        )

        self.assertEqual(proposal.model, "premium-a")

    def test_steps_down_never_up(self) -> None:
        catalog = {
            "fast-a": {"tier": "fast", "cost": 1},
            "premium-a": {"tier": "premium", "cost": 4},
        }
        proposal = models.propose("team-implementer", "high", config(catalog=catalog))

        self.assertEqual(proposal.model, "fast-a")

    def test_nothing_configured_inherits(self) -> None:
        proposal = models.propose("team-implementer", "medium", config(catalog={}))

        self.assertEqual(proposal.model, models.INHERIT)


if __name__ == "__main__":
    unittest.main()

"""Model choice: pins, then favorites, then the catalog; by difficulty; never premium unasked."""

from dataclasses import asdict, dataclass
from typing import Any

from team.fsutil import read_json, write_json_atomic
from team.paths import CONFIG_DIR

MODELS_FILE = CONFIG_DIR / "models.json"
TIERS = ("fast", "standard", "strong", "premium")
DIFFICULTY_TIER = {"low": "fast", "medium": "standard", "high": "strong", "critical": "strong"}
DIFFICULTY_EFFORT = {"low": "low", "medium": "medium", "high": "high", "critical": "high"}
DIFFICULTY_ORDER = ("low", "medium", "high", "critical")
INHERIT = "inherit"


@dataclass(frozen=True)
class Proposal:
    """One agent's model for one work item. `upgrade` is a premium option, never applied unasked."""

    agent: str
    difficulty: str
    model: str
    effort: str
    reason: str
    upgrade: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config() -> dict[str, Any]:
    return read_json(MODELS_FILE)


def save_config(config: dict[str, Any]) -> None:
    write_json_atomic(MODELS_FILE, config)


def effective_difficulty(agent: str, task_difficulty: str, config: dict[str, Any]) -> str:
    """The role's own level, raised by a harder task, but at most one level above the role's own.

    The cap keeps cost down: on a critical task the architects get critical, while a role
    that is usually medium gets high, not critical.
    """
    role_index = DIFFICULTY_ORDER.index(config["roleDifficulty"].get(agent, "medium"))
    task_index = DIFFICULTY_ORDER.index(task_difficulty)
    capped_index = min(max(role_index, task_index), role_index + 1)

    return DIFFICULTY_ORDER[capped_index]


def propose(agent: str, task_difficulty: str, config: dict[str, Any]) -> Proposal:
    difficulty = effective_difficulty(agent, task_difficulty, config)
    effort = DIFFICULTY_EFFORT[difficulty]
    pinned = config["pins"].get(agent)

    if pinned:
        return Proposal(agent, difficulty, pinned, effort, "pinned in models.json")

    wanted_tier = DIFFICULTY_TIER[difficulty]
    upgrade = _premium_upgrade(difficulty, config)

    if difficulty == "critical" and upgrade and config.get("allowPremiumWithoutAsking"):
        return Proposal(agent, difficulty, upgrade, effort, "critical, premium allowed in config")

    model, reason = pick_model(wanted_tier, config)

    return Proposal(agent, difficulty, model, effort, reason, upgrade)


def pick_model(wanted_tier: str, config: dict[str, Any]) -> tuple[str, str]:
    """Per tier: cheapest favorite, else cheapest catalog model.

    Starts at the wanted tier and steps down one tier at a time, never up and never to premium,
    so an automatic choice can only get cheaper.
    """
    catalog = config["catalog"]
    favorites = [model for model in config["favorites"] if model in catalog]
    tiers_to_try = [tier for tier in TIERS[: TIERS.index(wanted_tier) + 1] if tier != "premium"]

    for tier in reversed(tiers_to_try):
        from_favorites = _cheapest(favorites, tier, catalog)

        if from_favorites:
            return from_favorites, f"favorite, tier {tier}"

        from_catalog = _cheapest(list(catalog), tier, catalog)

        if from_catalog:
            return from_catalog, f"catalog, tier {tier}"

    return INHERIT, "no model configured, uses your session model"


def _cheapest(models: list[str], tier: str, catalog: dict[str, Any]) -> str | None:
    """Lowest cost first; on equal cost the earlier entry (favorite order) wins."""
    in_tier = [model for model in models if catalog[model]["tier"] == tier]

    if not in_tier:
        return None

    return min(in_tier, key=lambda model: (catalog[model]["cost"], in_tier.index(model)))


def _premium_upgrade(difficulty: str, config: dict[str, Any]) -> str | None:
    if difficulty != "critical":
        return None

    catalog = config["catalog"]
    favorites = [model for model in config["favorites"] if model in catalog]

    return _cheapest(favorites, "premium", catalog) or _cheapest(list(catalog), "premium", catalog)


def unknown_favorites(config: dict[str, Any]) -> list[str]:
    return [model for model in config["favorites"] if model not in config["catalog"]]


def command_for(agent: str, entry: dict[str, Any]) -> str:
    """The command to run this agent by hand with its chosen model."""
    parts = ["copilot", "--agent", agent]

    if entry.get("model") and entry["model"] != INHERIT:
        parts += ["--model", entry["model"]]

    if entry.get("effort"):
        parts += ["--reasoning-effort", entry["effort"]]

    return " ".join(parts)

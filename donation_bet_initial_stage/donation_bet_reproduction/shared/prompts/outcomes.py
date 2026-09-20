"""Outcome pairs for composable Donation Bet prompts.

Outcome text is stored as a verb phrase without a subject or final punctuation.
For example, ``"donate to some good cause"`` becomes ``"we donate to some
good cause"`` when inserted into a prompt. Use ``None`` for a silent branch;
the renderer omits that branch's entire conditional clause.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OutcomePair:
    """The favored (good) and disfavored (bad) actions in a Donation Bet."""

    good: str | None
    bad: str | None

    def __post_init__(self) -> None:
        if self.good is None and self.bad is None:
            raise ValueError("an outcome pair must have at least one explicit branch")

        for field_name, value in (("good", self.good), ("bad", self.bad)):
            if value is None:
                continue
            if not value or value != value.strip():
                raise ValueError(
                    f"{field_name} outcome must be a non-empty, trimmed verb phrase"
                )
            if "{" in value or "}" in value:
                raise ValueError(f"{field_name} outcome must not contain braces")

    def render_clauses(
        self,
        *,
        over_is_good: bool,
        over_condition: str,
        under_condition: str,
    ) -> str:
        """Render explicit branches in over-then-under order.

        A branch whose action is ``None`` is silent: both its outcome and its
        conditional clause are omitted.
        """

        over_action, under_action = (
            (self.good, self.bad) if over_is_good else (self.bad, self.good)
        )
        branches = (
            (over_condition, over_action),
            (under_condition, under_action),
        )
        return " ".join(
            f"If {condition}, we {action}."
            for condition, action in branches
            if action is not None
        )


# Exact abstract outcomes used in the paper's main Donation Bet experiment.
PAPER_OUTCOMES = OutcomePair(
    good="donate to some good cause",
    bad="donate to some bad cause",
)

# Avoiding the punishment is the favored, unspoken outcome. This wording
# mirrors the repository's existing ``f5_naked`` condition.
SILENT_NAKED_RUN_OUTCOMES = OutcomePair(
    good=None,
    bad="will run 200 m naked",
)

# Donating to UNICEF is the favored outcome; the other branch is unspoken.
UNICEF_SILENT_OUTCOMES = OutcomePair(
    good="donate to UNICEF",
    bad=None,
)

# The paper's abstract good cause is the favored outcome; the other branch is
# unspoken.
GOOD_CAUSE_SILENT_OUTCOMES = OutcomePair(
    good="donate to some good cause",
    bad=None,
)

# Add new named pairs here. Keeping each pair together prevents accidentally
# combining the good outcome from one condition with the bad outcome of another.
OUTCOME_PAIRS: dict[str, OutcomePair] = {
    "paper": PAPER_OUTCOMES,
    "good_cause_bad_cause": PAPER_OUTCOMES,
    "silent_naked_run": SILENT_NAKED_RUN_OUTCOMES,
    "unicef_silent": UNICEF_SILENT_OUTCOMES,
    "good_cause_silent": GOOD_CAUSE_SILENT_OUTCOMES,
}

DEFAULT_OUTCOMES = PAPER_OUTCOMES


def get_outcome_pair(name: str) -> OutcomePair:
    """Return a named outcome pair with a useful error for unknown names."""

    try:
        return OUTCOME_PAIRS[name]
    except KeyError as exc:
        choices = ", ".join(sorted(OUTCOME_PAIRS))
        raise ValueError(f"unknown outcome pair {name!r}; choose one of: {choices}") from exc

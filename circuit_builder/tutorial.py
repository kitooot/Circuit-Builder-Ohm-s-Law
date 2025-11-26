from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class TutorialStep:
    title: str
    description: str
    action_hint: str


TUTORIAL_STEPS: List[TutorialStep] = [
    TutorialStep(
        title="Welcome",
        description="Learn how to build a simple circuit in a few quick steps.",
        action_hint="Click Next to begin",
    ),
    TutorialStep(
        title="Add a Battery",
        description="Drag or click the Battery tile to place a voltage source on the canvas.",
        action_hint="Add at least one battery",
    ),
    TutorialStep(
        title="Add a Load",
        description="Place a resistor, bulb, or LED to give the circuit a load.",
        action_hint="Add a load component",
    ),
    TutorialStep(
        title="Connect Terminals",
        description="Use wires to connect each terminal. Link the battery positive to the load, then back to the battery.",
        action_hint="Connect all terminals",
    ),
    TutorialStep(
        title="Analyze",
        description="Watch the live metrics panel to see voltage, current, and power updates in real time.",
        action_hint="Observe the analysis panel",
    ),
]


def iter_tutorial_steps() -> Iterable[TutorialStep]:
    return iter(TUTORIAL_STEPS)


__all__ = ["TutorialStep", "TUTORIAL_STEPS", "iter_tutorial_steps"]

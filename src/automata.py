from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable


class InvalidTransition(Exception):
    pass


@dataclass(frozen=True)
class Transition:
    source: str
    event: str
    target: str
    action: str | None = None


class FiniteStateMachine:
    def __init__(self, name: str, initial: str, transitions: list[Transition]):
        self.name = name
        self.initial = initial
        self.current = initial
        self.transitions = transitions

    def reset(self, state: str | None = None):
        self.current = state or self.initial

    def available_events(self) -> list[str]:
        return [t.event for t in self.transitions if t.source == self.current]

    def trigger(self, event: str) -> tuple[str, str | None]:
        matches = [
            transition for transition in self.transitions
            if transition.source == self.current and transition.event.lower() == event.lower()
        ]
        if not matches:
            raise InvalidTransition(
                f"{self.name}: transition '{event}' invalide depuis l'état '{self.current}'."
            )
        transition = matches[0]
        self.current = transition.target
        return self.current, transition.action

    def validate_sequence(self, sequence: list[str]) -> bool:
        original = self.current
        try:
            for event in sequence:
                self.trigger(event)
            return True
        except InvalidTransition:
            return False
        finally:
            self.current = original

    def dot(self) -> str:
        states = sorted({self.initial, *(t.source for t in self.transitions), *(t.target for t in self.transitions)})
        lines = [
            "digraph G {",
            "rankdir=LR;",
            "node [shape=circle, style=filled, fillcolor=\"#E8F1FB\"];",
            "edge [color=\"#6B7280\"];",
            f'"{self.initial}" [fillcolor="#DFF5E8"];',
        ]
        for state in states:
            lines.append(f'"{state}" [label="{state}"];')
        for transition in self.transitions:
            lines.append(
                f'"{transition.source}" -> "{transition.target}" '
                f'[label="{transition.event}"];'
            )
        lines.append("}")
        return "\n".join(lines)


SENSOR_TRANSITIONS = [
    Transition("INACTIF", "installation", "ACTIF", "activer surveillance"),
    Transition("ACTIF", "détection d'anomalie", "SIGNALE", "créer demande d'intervention"),
    Transition("SIGNALE", "panne", "HORS_SERVICE", "envoyer alerte"),
    Transition("SIGNALE", "réparation", "ACTIF", "fermer alerte"),
    Transition("EN_MAINTENANCE", "réparation", "ACTIF", "remettre en service"),
    Transition("ACTIF", "panne", "HORS_SERVICE", "envoyer alerte"),
]

INTERVENTION_TRANSITIONS = [
    Transition("DEMANDE", "assignation tech1", "TECH1_ASSigne", "notifier technicien"),
    Transition("TECH1_ASSigne", "validation tech2", "TECH2_VALIDE", "envoyer à l'IA"),
    Transition("TECH2_VALIDE", "validation IA", "IA_VALIDE", "autoriser intervention"),
    Transition("IA_VALIDE", "clôture", "TERMINE", "archiver intervention"),
]

VEHICLE_TRANSITIONS = [
    Transition("STATIONNE", "démarrage", "EN_ROUTE", "débuter trajet"),
    Transition("EN_ROUTE", "panne", "EN_PANNE", "signaliser panne"),
    Transition("EN_PANNE", "réparation", "STATIONNE", "remettre véhicule disponible"),
    Transition("EN_ROUTE", "arrivée", "ARRIVE", "terminer trajet"),
]


def sensor_machine(state: str = "INACTIF") -> FiniteStateMachine:
    machine = FiniteStateMachine("Capteur", "INACTIF", SENSOR_TRANSITIONS)
    machine.reset(state)
    return machine


def intervention_machine(state: str = "DEMANDE") -> FiniteStateMachine:
    machine = FiniteStateMachine("Intervention", "DEMANDE", INTERVENTION_TRANSITIONS)
    machine.reset(state)
    return machine


def vehicle_machine(state: str = "STATIONNE") -> FiniteStateMachine:
    machine = FiniteStateMachine("Véhicule", "STATIONNE", VEHICLE_TRANSITIONS)
    machine.reset(state)
    return machine


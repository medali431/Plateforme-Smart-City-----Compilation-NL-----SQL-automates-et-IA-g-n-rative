import pytest
from src.automata import (
    sensor_machine,
    intervention_machine,
    vehicle_machine,
    InvalidTransition,
)


def test_sensor_valid_sequence():
    machine = sensor_machine("INACTIF")
    assert machine.validate_sequence(["installation", "détection d'anomalie", "panne"])
    assert machine.current == "INACTIF"


def test_sensor_invalid_sequence():
    machine = sensor_machine("INACTIF")
    assert not machine.validate_sequence(["panne"])


def test_intervention_full_sequence():
    machine = intervention_machine()
    sequence = ["assignation tech1", "validation tech2", "validation IA", "clôture"]
    assert machine.validate_sequence(sequence)


def test_vehicle_sequence():
    machine = vehicle_machine()
    assert machine.trigger("démarrage")[0] == "EN_ROUTE"
    assert machine.trigger("arrivée")[0] == "ARRIVE"


def test_invalid_transition_raises():
    machine = vehicle_machine("STATIONNE")
    with pytest.raises(InvalidTransition):
        machine.trigger("arrivée")

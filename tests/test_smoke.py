import importlib


def test_packages_import():
    assert importlib.import_module("exam_sim.parser")
    assert importlib.import_module("exam_sim.server")

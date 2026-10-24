"""Each test layer is non-empty and every test file is classified."""

from pathlib import Path

import pytest

from conftest import LAYERS, LAYER_OF

TESTS = Path(__file__).resolve().parent


def test_every_test_file_has_exactly_one_layer():
    files = {p.name for p in TESTS.glob("test_*.py")}
    assert files == set(LAYER_OF), {"unmapped": files - set(LAYER_OF), "stale": set(LAYER_OF) - files}
    assert sum(len(v) for v in LAYERS.values()) == len(LAYER_OF)


@pytest.mark.parametrize("layer", ["unit", "contract", "integration"])
def test_each_required_layer_has_test_functions(layer):
    count = sum((TESTS / name).read_text(encoding="utf-8").count("\ndef test_") for name in LAYERS[layer])
    assert count > 0, layer

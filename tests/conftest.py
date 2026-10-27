import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Rooms start on a random match by default; tests that don't pick a seed use the locked demo match.
os.environ.setdefault("VMI_DEMO", "1")

# Every test file belongs to exactly one layer (docs/implementation/12-QUALITY-AND-GIT-GATES.md §3.2).
# A new file must be added here; collection fails otherwise, so `-m unit|contract|integration`
# can never silently skip it.
LAYERS = {
    "unit": {"test_atmosphere.py", "test_overlay.py", "test_generator_analytics.py", "test_coverage_gate.py",
             "test_ci_config.py", "test_model_layer.py", "test_catch_up.py", "test_match_clock.py", "test_voices.py",
             "test_full_match_actions.py", "test_ws_input.py"},
    "contract": {"test_contract_v2.py", "test_fixture_export.py", "test_scenarios.py", "test_schemas.py"},
    "integration": {"test_agents.py", "test_api.py", "test_engine.py", "test_generator.py",
                    "test_generator_determinism.py", "test_generator_motion_v2.py", "test_substitutions.py",
                    "test_test_layers.py", "test_realtime_session.py", "test_model_eval.py",
                    "test_commentary_agents.py", "test_demo_match.py", "test_match_chat.py"},
}
LAYER_OF = {name: layer for layer, names in LAYERS.items() for name in names}


def pytest_collection_modifyitems(config, items):
    unmapped = sorted({item.path.name for item in items if item.path.name not in LAYER_OF})
    if unmapped:
        raise pytest.UsageError(f"test files without a layer in tests/conftest.py: {unmapped}")
    for item in items:
        item.add_marker(getattr(pytest.mark, LAYER_OF[item.path.name]))

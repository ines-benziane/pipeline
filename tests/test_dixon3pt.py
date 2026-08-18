"""Golden test for Dixon3ptMethod.

The reference (tests/fixtures/dixon3pt_golden.json) was captured from a real
run on dixon_data_test_CL2LD260112 and cross-checked against ffmap.mha/mask.mha
produced independently by the real mutools CLI on the same patient (same
bimodal FF distribution, ~37% <0.2 and ~37% >0.8) — so it is trusted as a
correct-enough reference, not just "whatever the code happened to produce".
"""

import json
from pathlib import Path

import pytest

from methods.dixon3pt import Dixon3ptMethod

FIXTURE = Path(__file__).parent / "fixtures" / "dixon3pt_golden.json"
EXAM_DIR = "dixon_data_test_CL2LD260112"


def _muscles_by_key(muscles):
    return {(m["name"], m["side"]): m["volume"]["stats"] for m in muscles}


def test_dixon3pt_matches_golden_reference(tmp_path):
    result = Dixon3ptMethod().run(EXAM_DIR, tmp_path, "legs")
    produced = json.loads(Path(result.results).read_text(encoding="utf-8"))
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))

    produced_muscles = _muscles_by_key(produced["muscles"])
    golden_muscles = _muscles_by_key(golden["muscles"])

    assert produced_muscles.keys() == golden_muscles.keys()
    for key, golden_stats in golden_muscles.items():
        produced_stats = produced_muscles[key]
        assert produced_stats["NPIX"] == pytest.approx(golden_stats["NPIX"], rel=1e-6)
        assert produced_stats["FF"] == pytest.approx(golden_stats["FF"], rel=1e-3)

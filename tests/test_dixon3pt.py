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
from runner.method import RunContext

FIXTURE = Path(__file__).parent / "fixtures" / "dixon3pt_golden.json"
SOURCE_DIR = Path(__file__).parent.parent / "golden_tests" / "dixon" / "CL2LD260112"
LEGS_SERIES = [17, 18]  # "VIBE_3TE JAMBES", TE 2.75/3.95/7.55 ms


def _muscles_by_key(muscles):
    return {(m["name"], m["side"]): m["volume"]["stats"] for m in muscles}


@pytest.mark.skipif(not SOURCE_DIR.is_dir(), reason=f"golden DICOM data missing: {SOURCE_DIR}")
def test_dixon3pt_matches_golden_reference(tmp_path):
    result = Dixon3ptMethod().run(RunContext(source_dir=str(SOURCE_DIR), exam_id="CL2LD260112", workdir=tmp_path,
                                             segment="legs", series=LEGS_SERIES))
    produced = json.loads(Path(result.results).read_text(encoding="utf-8"))
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))

    produced_muscles = _muscles_by_key(produced["muscles"])
    golden_muscles = _muscles_by_key(golden["muscles"])

    assert produced_muscles.keys() == golden_muscles.keys()
    mismatches = []
    for key, golden_stats in golden_muscles.items():
        produced_stats = produced_muscles[key]
        # MuSeg-AI is not bit-reproducible: ROI borders move by a few pixels between runs
        # (observed max 5 px / 0.056 % over 3 runs, 2026-10-22). NPIX tolerance: 0.1 % or 10 px,
        # whichever is larger. FF, the clinical biomarker, stays at 0.1 %.
        npix_ok = produced_stats["NPIX"] == pytest.approx(golden_stats["NPIX"], rel=1e-3, abs=10)
        ff_ok = produced_stats["FF"] == pytest.approx(golden_stats["FF"], rel=1e-3)
        if not (npix_ok and ff_ok):
            mismatches.append(
                f"{key[0]:>8} {key[1]}  "
                f"NPIX {golden_stats['NPIX']:.0f} -> {produced_stats['NPIX']:.0f} "
                f"({produced_stats['NPIX'] - golden_stats['NPIX']:+.0f} px)  "
                f"FF {golden_stats['FF']:.4f} -> {produced_stats['FF']:.4f} "
                f"({(produced_stats['FF'] - golden_stats['FF']) / golden_stats['FF']:+.3%})"
            )
    assert not mismatches, f"{len(mismatches)}/{len(golden_muscles)} muscles differ:\n" + "\n".join(mismatches)

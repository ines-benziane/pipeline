import json
from pathlib import Path

from runner.method import Method, Result, RunContext
from runner.progress import announce

FIXTURE = Path(__file__).parent.parent / "tests" / "fixtures" / "exam_sample.json"

class DummyMethod(Method):
    name = "dummy"
    version = "1.1"
    comparability_criteria = []

    def run(self, ctx: RunContext):
        announce(f"building dummy result for {ctx.exam_id} / {ctx.segment}...", level=1)
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))

        for field in ("patient_name", "birth_date", "referring_doctor"):
            data["metadata"].pop(field, None)

        data["metadata"]["segment"] = ctx.segment
        data["metadata"]["exam_id"] = ctx.exam_id

        meta = data["metadata"]
        filename = (
            f"{meta['exam_id']}_{meta['exam_date']}_{meta['segment']}"
            f"_{meta['method']}_{meta['version']}_{meta['acquisition']}.json"
        )
        output = Path(ctx.workdir) / filename
        output.write_text(json.dumps(data), encoding="utf-8")
        return Result(
            results=output,
            auto_valid=True,
            provenance = {"name": self.name, "version": self.version})

    def handle_checkpoint(self, *, name, workdir, segment, exam_id, qc, qc_dir=None,
                          decision=None, debug=False, multicenter=False, seg_series=None):
        raise NotImplementedError("DummyMethod has no checkpoints")

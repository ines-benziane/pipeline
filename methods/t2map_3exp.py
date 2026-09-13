from pathlib import Path

from dicomstack import DicomStack

from methods.dixon3pt import Dixon3ptMethod, MODEL_BY_SEGMENT
from methods.get_results.getresults import getresults

from runner.method import Method, Result, QCCheckpoint, QCUserDecisions
from runner.progress import announce
from runner.errors import (
    DicomSelectionError,
    T2MappingError,
)

from mutools.t2mapping.readers import parse_dicom_msme
from mutools.t2mapping.utils import clusterize
from mutools.t2mapping.t2map_3exp_dict import fit_fat, fit

from results_writer.writer import parse_table
from results_writer.json_writer import JsonWriter

class T2Map3ExpMethod(Method):
    name = "t2map_3exp"
    version = "1.0"
    comparability_criteria = []
    CHECKPOINTS = ("mutools","segmentation")
    ACTIONS = ()

    def write_results(self, results, rois, labels, metadata, workdir, decision: QCUserDecisions | None = None):
        if decision is not None:
            metadata = {**metadata,
                        "qc_decision": decision.decision_status,
                        "qc_comment": decision.comment}
        table = getresults(volumes={"t2map": results}, roi=rois[0], labels=labels, method_name="t2map_3exp")
        exam = parse_table(table, metadata)
        json_path = JsonWriter().write(exam, Path(workdir))
        return json_path      
        

    def run (self, source_dir, exam_id, workdir, segment, series, params, date, qc,
            qc_dir, decision: QCUserDecisions | None = None, debug=False, action=None,
            multicenter=False, seg_series=None) :
        self._check_action(action)
        stack = DicomStack(source_dir)
        if date :
            stack = stack(SeriesNumber=series, StudyDate=date)
        else :
            stack = stack(SeriesNumber=series)
        if not stack:
            raise DicomSelectionError(
                f"No DICOM series matching {series} in {source_dir}",
                hint="check --series and --date",
            )
        exam_date = stack.single("StudyDate")
        announce("parsing T2 DICOM series...", level=1)
        try:
            info, volumes = parse_dicom_msme(stack, min_echo_num=8)
            echo_times = info["echo_times"]
        except Exception as exc:
            raise DicomSelectionError(
                f"Selected series in {source_dir} are not a readable T2map acquisition"
            ) from exc
        roi=clusterize(volumes)
        announce("T2 mapping...", level=1)
        try:
            fixed_fat=params.get("fixed_fat", False)
            config = None
            if not fixed_fat:
                res = fit_fat(echo_times=echo_times, volumes=volumes, mask=roi==2)
                config = {}
                config.update(res)
                config["fit_fat"] = True
            results, pred = fit (echo_times=echo_times, volumes=volumes, mask=roi>0, config=config)
        except Exception as exc:
            if debug:
                self._dump_crash(
                    workdir,
                    roi=roi,
                    **{f"echo_{i}": v for i, v in enumerate(volumes)})
            raise T2MappingError(f"T2 mapping reconstruction failed for {source_dir}") from exc
        if debug or qc in ("checkpoint", "global"):
            if multicenter:
                ...
            ...
        # WARNING: checkpoint doesn't work here — a nested QCCheckpoint would suspend this
        # job under t2map_3exp's name, but T2Map3ExpMethod.handle_checkpoint can't resume
        # dixon3pt's internal state. "checkpoint" is downgraded to "global" so segmentation
        # QC artifacts are still written, but never suspends. Composing checkpoints across
        # methods is unsolved — revisit when T2 needs a real resume here.
        rois, labels, exam_date = Dixon3ptMethod().run(source_dir=source_dir, exam_id=exam_id, workdir=workdir, segment=segment, series=seg_series, params=params, date=date,
            qc="global" if qc == "checkpoint" else qc,
            qc_dir=qc_dir, debug=debug, seg_series=seg_series, action=None, multicenter=False)

        metadata = {
            "exam_id": exam_id,
            "exam_date": exam_date,
            "segment": segment,
            "method": self.name,
            "version": self.version,
            "acquisition": "1.0",
            "biomarker": "T2",
            "segmentation": MODEL_BY_SEGMENT[segment],
        }

        json_path = self.write_results(results, rois, labels, metadata, workdir, decision)
        return Result(
                    results=json_path,
                    auto_valid=True,
                    provenance={"name": self.name, "version": self.version},
                )

    def handle_checkpoint(self, *, name, workdir, segment, exam_id, qc, qc_dir=None, decision=None, debug=False, multicenter=False):
         raise NotImplementedError("resume T2 not implemented yet")
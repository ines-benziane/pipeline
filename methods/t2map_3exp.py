from pathlib import Path

import numpy as np

from dicomstack import DicomStack

from methods.dixon3pt import Dixon3ptMethod, MODEL_BY_SEGMENT
from methods.get_results.getresults import getresults

from runner.method import Method, Result, QCCheckpoint, QCUserDecisions
from runner.progress import announce
from runner.errors import (
    DicomSelectionError,
    T2MappingError,
)

from mutools.io.volume import asvolume
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
        # rois[0] is a musegai Image (dixon geometry, in principle already correct — see
        # write-up). But getresults/interpolate_roi does an internal asvolume(roi) that drops
        # geometry from a raw musegai object (same pitfall as the segmentation GIF fix). Without
        # re-wrapping it explicitly here, it silently gets identity geometry, which — now that
        # "t2map" carries the real T2 geometry — misaligns the two grids instead of aligning them.
        # .T: roi.transform is row-major (SITK GetDirection), mutools wants column-sequence.
        roi = rois[0]
        roi_vol = asvolume(roi.array, spacing=roi.spacing, origin=roi.origin,
                           transform=np.reshape(roi.transform, (3, 3)).T)
        table = getresults(
            volumes={"t2map": results["t2map"], "t2cint": results["t2cint"], "ffmap": results["ffmap"]},
            roi=roi_vol, labels=labels, method_name="t2map_3exp",
        )
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

        # results["t2map"]/"t2cint"/"ffmap" come out of fit() as raw ndarrays (utils.fillvolume),
        # with no geometry (no .spacing/.origin/.transform). The segmentation ROI comes from a
        # DIFFERENT acquisition (Dixon, via seg_series) with its own grid/shape. Without real
        # geometry on the T2 side, getresults's interpolate_roi(ref, roi) degenerates to aligning
        # both volumes by raw array index instead of physical position — since the two grids don't
        # share shape/resolution, almost nothing overlaps (only 1/8 muscles survived in testing).
        # Fix: tag the T2 volumes with the real T2 acquisition geometry (copied from `volumes[0]`,
        # a proper mutools Volume from parse_dicom_msme) before they reach getresults. Same pattern
        # as the ROI geometry fix used for the segmentation QC gif (interpolate_roi there too).
        t2_ref = volumes[0]
        for key in ("t2map", "t2cint", "ffmap"):
            results[key] = asvolume(results[key], spacing=t2_ref.spacing, origin=t2_ref.origin,
                                     transform=t2_ref.transform)

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
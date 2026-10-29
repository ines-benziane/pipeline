from dataclasses import replace
from pathlib import Path

import numpy as np

from dicomstack import DicomStack

from methods.dixon3pt import Dixon3ptMethod, MODEL_BY_SEGMENT
from methods.get_results.getresults import getresults

from runner.method import Method, Result, QCCheckpoint, QCUserDecisions, RunContext
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

from methods.external_segmentation import read_external_segmentation

class T2Map3ExpMethod(Method):
    name = "t2map_3exp"
    version = "1.0"
    comparability_criteria = []
    CHECKPOINTS = ("mutools","segmentation")
    ACTIONS = ()
    biomarker = "T2"
    report_acquisition = "1.0"

    def _segment(self, ctx, t2_ref, exam_date):
        """External segmentation if given (--external-seg, e.g. ROI_T2_LEG, already on the T2 grid),
        Dixon segmentation (MuSeg-AI on seg_series) otherwise. Returns (roi volume, labels, exam_date)."""
        if ctx.ext_seg :
            rois, labels = read_external_segmentation(ctx.ext_seg, t2_ref, ctx.segment)
            return rois[0], labels, exam_date
            
        else:
            dixon_ctx = replace(ctx, series=ctx.seg_series, qc="global" if ctx.qc == "checkpoint" else ctx.qc,
                            action=None, multicenter=False)
            rois, labels, exam_date = Dixon3ptMethod().run(dixon_ctx)
            # rois[0] is a musegai Image (dixon geometry, in principle already correct — see
            # write-up). But getresults/interpolate_roi does an internal asvolume(roi) that drops
            # geometry from a raw musegai object (same pitfall as the segmentation GIF fix). Without
            # re-wrapping it explicitly here, it silently gets identity geometry, which — now that
            # "t2map" carries the real T2 geometry — misaligns the two grids instead of aligning them.
            # .T: roi.transform is row-major (SITK GetDirection), mutools wants column-sequence.
            roi = rois[0]
            roi_vol = asvolume(roi.array, spacing=roi.spacing, origin=roi.origin,
                            transform=np.reshape(roi.transform, (3, 3)).T)
            return roi_vol, labels, exam_date

    def write_results(self, results, roi, labels, metadata, workdir, decision: QCUserDecisions | None = None,
                      results_config=None):
        if decision is not None:
            metadata = {**metadata,
                        "qc_decision": decision.decision_status,
                        "qc_comment": decision.comment}
        table = getresults(
            volumes={"t2map": results["t2map"], "t2cint": results["t2cint"], "ffmap": results["ffmap"]},
            roi=roi, labels=labels, method_name="t2map_3exp", variant=results_config,
        )
        exam = parse_table(table, metadata)
        json_path = JsonWriter().write(exam, Path(workdir))
        return json_path      
        

    def run (self, ctx: RunContext) :
        self._check_action(ctx.action)
        stack = DicomStack(ctx.source_dir)
        if ctx.exam_date :
            stack = stack(SeriesNumber=ctx.series, StudyDate=ctx.exam_date)
        else :
            stack = stack(SeriesNumber=ctx.series)
        if not stack:
            raise DicomSelectionError(
                f"No DICOM series matching {ctx.series} in {ctx.source_dir}",
                hint="check --series and --date",
            )
        exam_date = stack.single("StudyDate")
        announce("parsing T2 DICOM series...", level=1)
        try:
            info, volumes = parse_dicom_msme(stack, min_echo_num=8)
            echo_times = info["echo_times"]
        except Exception as exc:
            raise DicomSelectionError(
                f"Selected series in {ctx.source_dir} are not a readable T2map acquisition"
            ) from exc
        roi=clusterize(volumes)
        announce("T2 mapping...", level=1)
        try:
            fixed_fat=(ctx.params or {}).get("fixed_fat", False)
            config = None
            if not fixed_fat:
                res = fit_fat(echo_times=echo_times, volumes=volumes, mask=roi==2)
                config = {}
                config.update(res)
                config["fit_fat"] = True
            results, pred = fit (echo_times=echo_times, volumes=volumes, mask=roi>0, config=config)
        except Exception as exc:
            if ctx.debug:
                self._dump_crash(
                    ctx.workdir,
                    roi=roi,
                    **{f"echo_{i}": v for i, v in enumerate(volumes)})
            raise T2MappingError(f"T2 mapping reconstruction failed for {ctx.source_dir}") from exc

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

        if ctx.debug or ctx.qc in ("checkpoint", "global"):
            if ctx.multicenter:
                ...
            ...
        # WARNING: checkpoint doesn't work here — a nested QCCheckpoint would suspend this
        # job under t2map_3exp's name, but T2Map3ExpMethod.handle_checkpoint can't resume
        # dixon3pt's internal state. "checkpoint" is downgraded to "global" so segmentation
        # QC artifacts are still written, but never suspends. Composing checkpoints across
        # methods is unsolved — revisit when T2 needs a real resume here.


        roi, labels, exam_date = self._segment(ctx, t2_ref, exam_date)

        metadata = {
            "exam_id": ctx.exam_id,
            "exam_date": exam_date,
            "segment": ctx.segment,
            "method": self.name,
            "version": self.version,
            "acquisition": self.report_acquisition,
            "biomarker": self.biomarker,
            "segmentation": "external" if ctx.ext_seg else MODEL_BY_SEGMENT[ctx.segment],
        }

        json_path = self.write_results(results, roi, labels, metadata, ctx.workdir, ctx.decision,
                                       results_config=(ctx.params or {}).get("results_config"))
        return Result(
                    results=json_path,
                    auto_valid=True,
                    provenance={"name": self.name, "version": self.version},
                )

    def handle_checkpoint(self, *, name, workdir, segment, exam_id, qc, qc_dir=None, decision=None, debug=False, multicenter=False,
                          seg_series=None):
         raise NotImplementedError("resume T2 not implemented yet")
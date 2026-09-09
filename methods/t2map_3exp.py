from dicomstack import DicomStack

from runner.method import Method, Result, QCCheckpoint, QCUserDecisions
from runner.progress import announce
from runner.errors import (
    DicomSelectionError,
    T2MappingError,
    SegmentationError,
    UnknownSegmentError,
)

from mutools.t2mapping.readers import parse_dicom_msme
from mutools.t2mapping.utils import clusterize
from mutools.t2mapping.t2map_3exp_dict import fit_fat, fit

class T2Map3ExpMethod(Method):
    name = "t2map_3exp"
    version = "1.0"
    comparability_criteria = []
    CHECKPOINTS = ("mutools","segmentation")
    ACTIONS = ()

    def run (self, source_dir, exam_id, workdir, segment, series, params, date, qc,
            qc_dir, decision: QCUserDecisions | None = None, debug=False, action=None, multicenter=False) :
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
        rois, labels, exam_date = dixon3pt.segmentation()
            


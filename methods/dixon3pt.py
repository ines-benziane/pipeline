"""Dixon 3pt method"""

from pathlib import Path
import json
import logging
import numpy as np

from scipy import ndimage

from runner.errors import (
    DicomSelectionError,
    DixonReconstructionError,
    SegmentationError,
    UnknownSegmentError,
    SwapLegsError,
)
from runner.method import Method, Result, QCCheckpoint, QCUserDecisions, RunContext
from runner.progress import announce

from dicomstack import DicomStack

from mutools.fatwater.utils import make_mask, make_ffmap
from mutools.fatwater.dixon import dixon_3pt
from mutools.fatwater.readers import parse_dicom_dixon_default
from mutools.io import volume
from mutools import io

from musegai.io import Image
from musegai.api import run_model

from methods.external_segmentation import read_external_segmentation
from methods.get_results.getresults import getresults
from methods.quality_check.qc import quality_check_volumes, quality_check_seg, save_gif

from results_writer.writer import parse_table
from results_writer.json_writer import JsonWriter

MODEL_BY_SEGMENT = {"legs": "museg-legs:model1", "thighs": "museg-thighs:model3"}

log = logging.getLogger(__name__)

class Dixon3ptMethod(Method) :
    name = "dixon3pt"
    version = "1.0"
    comparability_criteria = []
    CHECKPOINTS = ("mutools", "segmentation")
    ACTIONS = ("global-swap", "swap-left", "swap-right")
    biomarker = "FF"
    report_acquisition = "1.0"

    def _segment(self, ctx, volumes, exam_date):
        """External segmentation if given (--external_seg), Museg-AI otherwise"""
        if ctx.ext_seg:
            rois, labels = read_external_segmentation(ctx.ext_seg, volumes[0], ctx.segment)
            return rois, labels, exam_date
        return self.segmentation(volumes, ctx.segment, ctx.exam_id, ctx.qc, exam_date,
                                 ctx.workdir, ctx.qc_dir, ctx.debug)


    def _swap_leg(self, water_map, fat_map, mask, side):
        """Swap water and fat in one leg only (side "right" or "left")"""
        parts, n = ndimage.label(mask)
        sizes = np.bincount(parts.ravel())
        sizes[0] = 0
        legs = np.argsort(sizes)[-2:]
        if n < 2 or sizes[legs[0]] < sizes[legs[1]] /2 :
            raise SwapLegsError(
                "swap-left/swap-right: two separate legs not found in the image",
                hint="this action only applies to legs; use global-swap or correct the swap manually",
            )
        # sort the two legs from left to right in the image (mean column index i);
        # patient right = left of the image (DICOM: x points to the patient's left)
        by_position = sorted(legs, key=lambda k: np.argwhere(parts == k )[:, 0].mean())
        right, left = by_position
        if side == "right":
            number = right
        else:
            number = left
        leg = parts == number 
        new_water, new_fat = water_map.copy(), fat_map.copy()
        new_water[leg] = fat_map[leg]
        new_fat[leg] = water_map[leg]
        return new_water, new_fat


    def segmentation(self, volumes, segment, exam_id, qc, exam_date, workdir, qc_dir=None, debug=False):
        mag_1 = abs(volumes[0])
        mag_2 = abs(volumes[1])
        mag_1 = np.nan_to_num(mag_1)
        mag_2 = np.nan_to_num(mag_2)

        transform_flat = [v for row in mag_1.transform for v in row]
        img_1 = Image(mag_1, transform=transform_flat)
        img_2 = Image(mag_2, transform=transform_flat)

        try:
            model = MODEL_BY_SEGMENT[segment]
        except KeyError:
            raise UnknownSegmentError(segment, MODEL_BY_SEGMENT) from None
        try :
            announce("running segmentation model...", level=1)
            rois, labels = run_model(model=model, images=[(img_1, img_2)], side="LR")
        except Exception as e:
            if debug:
                self._dump_crash(workdir, **{f"seg_input_echo_{i}": vol for i, vol in enumerate(volumes)})
            raise SegmentationError(f"Segmentation failed for {exam_id} (segment={segment})") from e
        labels = dict(zip(labels.indices, labels.descriptions))
        roi_obj = rois[0]
        roi_obj.transform =[roi_obj.transform[i:i+3] for i in range(0, len(roi_obj.transform), 3)]
        if debug or qc in ("checkpoint", "global") :
            volume.write(Path(workdir) / "roi.mha", roi_obj)
            io.write_labels(Path(workdir) / "labels.txt", labels)
            frames = quality_check_seg(mag_1, roi_obj, labels)
            save_gif(frames, Path(workdir) / "segmentation.gif")
        if qc in ("checkpoint", "global"):
            volume.write(Path(qc_dir) / "roi.mha", roi_obj)
            io.write_labels(Path(qc_dir) / "labels.txt", labels)
            save_gif(frames, Path(qc_dir) / "segmentation.gif")
        if qc == "checkpoint":
            raise QCCheckpoint(self.CHECKPOINTS[1])
        return rois, labels, exam_date

    def write_results(self, ffmap, rois, labels, metadata, workdir, decision: QCUserDecisions | None = None,
                      results_config=None):
        if decision is not None:
            metadata = {**metadata,
                        "qc_decision": decision.decision_status,
                        "qc_comment": decision.comment}
        table = getresults(volumes={"ffmap": ffmap}, roi=rois[0], labels=labels, method_name="dixon3pt",
                           variant=results_config)
        exam = parse_table(table, metadata)
        json_path = JsonWriter().write(exam, Path(workdir))
        return json_path      
        
    def run (self, ctx: RunContext):
        self._check_action(ctx.action)
        stack = DicomStack(ctx.source_dir)
        if ctx.exam_date :
                stack = stack(SeriesNumber=ctx.series, StudyDate=ctx.exam_date)
        else :
                stack = stack(SeriesNumber=ctx.series)
        if not stack :
            raise DicomSelectionError(
                f"No DICOM series matching {ctx.series} in {ctx.source_dir}",
                hint="check --series and --date",
            )
        exam_date = stack.single("StudyDate")
        announce("parsing Dixon DICOM series...", level=1)
        try :
            info, volumes = parse_dicom_dixon_default(stack, npoint=3)
            echo_times = info["echo_times"]
        except Exception as exc:
            raise DicomSelectionError(
                f"Selected series in {ctx.source_dir} are not a readable 3-point Dixon acquisition"
            ) from exc
        if ctx.seg_series:
            announce("Dixon 3pt segmentation...", level=1)
            rois, labels, exam_date = self._segment(ctx, volumes, exam_date)
            return (rois, labels, exam_date)
        mask = make_mask(*volumes, axis=2, threshold=10)
        announce("Dixon 3pt reconstruction...", level=1)
        try :
            water_map, fat_map, delta_b0, r2_star = dixon_3pt(echo_times, *volumes, mask = mask, force_reconstruction=False, global_swap=False)
        except Exception as exc:
            if ctx.debug:
                self._dump_crash(
                    ctx.workdir,
                    mask=mask,
                    echo_times=echo_times,
                    **{f"echo_{i}": vol for i, vol in enumerate(volumes)},
                )
            raise DixonReconstructionError(f"Dixon 3pt reconstruction failed for {ctx.source_dir}") from exc
        if ctx.action == "global-swap":
            water_map, fat_map = fat_map, water_map
        elif ctx.action == "swap-right" or ctx.action == "swap-left":
            side = ctx.action.removeprefix("swap-")
            water_map, fat_map = self._swap_leg(water_map, fat_map, mask, side)
        ffmap = make_ffmap(water_map, fat_map, mask=mask)

        if ctx.debug or ctx.qc in ("checkpoint", "global"):
            overview = quality_check_volumes(ffmap)
            overview.save(Path(ctx.workdir) / "overview.png")
        if ctx.qc in ("checkpoint", "global"):
            overview.save(Path(ctx.qc_dir) / "overview.png")
            volume.write(Path(ctx.qc_dir) / "ffmap.mha", ffmap)
        if ctx.debug or ctx.qc=="checkpoint":
            volume.write(Path(ctx.workdir) / "ffmap.mha", ffmap)
            volume.write(Path(ctx.workdir) / "mask.mha", mask)
            volume.write(Path(ctx.workdir) / "echo_times.mha", echo_times)
            echo_times_record = {"echo_times": list(echo_times), "exam_date": exam_date}
            (Path(ctx.workdir) / "echo_times_record.json").write_text(json.dumps(echo_times_record))
            for i, vol in enumerate(volumes):
                volume.write(Path(ctx.workdir) / f"echo_{i}.mha", vol)
        if ctx.qc == "checkpoint":
            raise QCCheckpoint(self.CHECKPOINTS[0])

        rois, labels, exam_date = self._segment(ctx, volumes, exam_date)

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

        json_path = self.write_results(ffmap, rois, labels, metadata, ctx.workdir, ctx.decision,
                                       results_config=(ctx.params or {}).get("results_config"))
        
        return Result(
            results=json_path,
            auto_valid=True,
            provenance={"name": self.name, "version": self.version},
        )

    def handle_checkpoint(self,*, name, workdir, segment, exam_id, qc, qc_dir=None, decision=None, debug=False, multicenter=False, seg_series=None):
        self._check_checkpoint(name)
        if name == "mutools":
            echo_times_record = json.loads((Path(workdir) / "echo_times_record.json").read_text())
            exam_date = echo_times_record["exam_date"]
            ffmap = volume.read(Path(workdir) / "ffmap.mha")
            volumes = [volume.read(Path(workdir) / f"echo_{i}.mha", as_complex=True) for i in range(3)]
            rois, labels, exam_date = self.segmentation(volumes, segment, exam_id, qc, exam_date, workdir, qc_dir, debug)
            metadata = {"exam_id": exam_id, "exam_date": exam_date, "segment": segment,
                        "method": self.name, "version": self.version, "acquisition": self.report_acquisition,
                        "biomarker": self.biomarker, "segmentation": MODEL_BY_SEGMENT[segment]}
            json_path = self.write_results(ffmap, rois, labels, metadata, workdir, decision)
            result = Result(json_path, auto_valid=True, provenance={"name": self.name, "version": self.version})
            return result
        elif name == "segmentation":
            echo_times_record = json.loads((Path(workdir) / "echo_times_record.json").read_text())
            exam_date = echo_times_record["exam_date"]
            metadata = {"exam_id": exam_id, "exam_date": exam_date, "segment": segment,
                        "method": self.name, "version": self.version, "acquisition": self.report_acquisition,
                        "biomarker": self.biomarker, "segmentation": MODEL_BY_SEGMENT[segment]}
            ffmap = volume.read(Path(workdir) / "ffmap.mha")
            roi = [volume.read(Path(workdir) / "roi.mha")]
            labels_obj = io.read_labels(Path(workdir) / "labels.txt")
            labels = dict(zip(labels_obj.indices, labels_obj.descriptions))
            json_path = self.write_results(ffmap, roi, labels, metadata, workdir, decision)
            result = Result(json_path, auto_valid=True, provenance={"name": self.name, "version": self.version})
            return result

        
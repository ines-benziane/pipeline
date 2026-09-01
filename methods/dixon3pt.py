"""Dixon 3pt method"""

from pathlib import Path
import json
import numpy as np

from runner.errors import (
    DicomSelectionError,
    DixonReconstructionError,
    SegmentationError,
    UnknownSegmentError,
)
from runner.job import MutoolsCheckpoint, SegmentationCheckpoint
from runner.method import Method, Result
from runner.progress import announce

from dicomstack import DicomStack

from mutools.fatwater.utils import make_mask, make_ffmap
from mutools.fatwater.dixon import dixon_3pt
from mutools.fatwater.readers import parse_dicom_dixon_default
from mutools.io import volume
from mutools import io

from musegai.io import Image
from musegai.api import run_model

from methods.get_results.getresults import getresults
from methods.quality_check.qc import quality_check_volumes, quality_check_seg

from results_writer.writer import parse_table
from results_writer.json_writer import JsonWriter

MODEL_BY_SEGMENT = {"legs": "museg-legs:model1", "thighs": "museg-thighs:model3"}

class Dixon3ptMethod(Method) :
    name = "dixon3pt"
    version = "1.0"
    comparability_criteria = []

    def segmentation(self, volumes, segment, exam_id, qc, exam_date, workdir):
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
            announce("  running segmentation model...")
            rois, labels = run_model(model=model, images=[(img_1, img_2)], side="LR")
        except Exception as e:
            raise SegmentationError(f"Segmentation failed for {exam_id} (segment={segment})") from e
        labels = dict(zip(labels.indices, labels.descriptions))
        if qc :
            roi_obj = rois[0]
            roi_obj.transform =[roi_obj.transform[i:i+3] for i in range(0, len(roi_obj.transform), 3)]
            volume.write(Path(workdir) / "roi.mha", roi_obj)
            io.write_labels(Path(workdir) / "labels.txt", labels)
            raise SegmentationCheckpoint
        return rois, labels, exam_date

    def write_results(self, ffmap, rois, labels, metadata, workdir):
        table = getresults(volumes={"ffmap": ffmap}, roi=rois[0], labels=labels, method_name="dixon3pt")
        exam = parse_table(table, metadata)
        json_path = JsonWriter().write(exam, Path(workdir))
        return json_path      
        
    def run (self, source_dir, exam_id, workdir, segment, series, params, date, qc=False):
        stack = DicomStack(source_dir)
        if date :
            stack = stack(SeriesNumber=series, StudyDate=date)
        else :
            stack = stack(SeriesNumber=series)
        if not stack :
            raise DicomSelectionError(
                f"No DICOM series matching {series} in {source_dir}",
                hint="check --series and --date",
            )
        exam_date = stack.single("StudyDate")
        announce("  parsing Dixon DICOM series...")
        try :
            info, volumes = parse_dicom_dixon_default(stack, npoint=3)
            echo_times = info["echo_times"]
        except Exception as exc:
            raise DicomSelectionError(
                f"Selected series in {source_dir} are not a readable 3-point Dixon acquisition"
            ) from exc
        mask = make_mask(*volumes, axis=2, threshold=10)
        announce("  Dixon 3pt reconstruction...")
        try :
            water_map, fat_map, delta_b0, r2_star = dixon_3pt(echo_times, *volumes, mask = mask, force_reconstruction=False, global_swap=False)
            ffmap = make_ffmap(water_map, fat_map, mask=mask)
        except Exception as exc:
            raise DixonReconstructionError(f"Dixon 3pt reconstruction failed for {source_dir}") from exc

        if qc:
            qc = quality_check_volumes(ffmap)
            qc.save(Path(workdir) / "overview.png")
            volume.write(Path(workdir) / "ffmap.mha", ffmap)
            volume.write(Path(workdir) / "mask.mha", mask)
            volume.write(Path(workdir) / "echo_times.mha", echo_times)
            echo_times_record = {"echo_times": list(echo_times), "exam_date": exam_date}
            (Path(workdir) / "echo_times_record.json").write_text(json.dumps(echo_times_record))
            for i, vol in enumerate(volumes):
                volume.write(Path(workdir) / f"echo_{i}.mha", vol)
            raise MutoolsCheckpoint
        
        rois, labels, exam_date = self.segmentation(volumes, segment, exam_id, qc, exam_date, workdir)

        metadata = {
            "exam_id": exam_id,
            "exam_date": exam_date,
            "segment": segment,
            "method": self.name,
            "version": self.version,
            "acquisition": "1.0",
            "biomarker": "FF",
        }

        json_path = self.write_results(ffmap, rois, labels, metadata, workdir)
        
        return Result(
            results=json_path,
            auto_valid=True,
            provenance={"name": self.name, "version": self.version},
        )

    def handle_checkpoint(self, name, *, workdir, segment, exam_id, qc):
        if name == "mutools":
            echo_times_record = json.loads((Path(workdir) / "echo_times_record.json").read_text())
            exam_date = echo_times_record["exam_date"]
            ffmap = volume.read(Path(workdir) / "ffmap.mha")
            volumes = [volume.read(Path(workdir) / f"echo_{i}.mha", as_complex=True) for i in range(3)]
            rois, labels, exam_date = self.segmentation(volumes, segment, exam_id, qc, exam_date, workdir)
            metadata = {"exam_id": exam_id, "exam_date": exam_date, "segment": segment,
                        "method": self.name, "version": self.version, "acquisition": "1.0", "biomarker": "FF"}
            json_path = self.write_results(ffmap, rois, labels, metadata, workdir)
            result = Result(json_path, auto_valid=True, provenance={"name": self.name, "version": self.version})
            return result
        elif name == "segmentation":
            echo_times_record = json.loads((Path(workdir) / "echo_times_record.json").read_text())
            exam_date = echo_times_record["exam_date"]
            metadata = {"exam_id": exam_id, "exam_date": exam_date, "segment": segment,
                        "method": self.name, "version": self.version, "acquisition": "1.0", "biomarker": "FF"}
            ffmap = volume.read(Path(workdir) / "ffmap.mha")
            roi = [volume.read(Path(workdir) / "roi.mha")]
            labels_obj = io.read_labels(Path(workdir) / "labels.txt")
            labels = dict(zip(labels_obj.indices, labels_obj.descriptions))
            json_path = self.write_results(ffmap, roi, labels, metadata, workdir)
            result = Result(json_path, auto_valid=True, provenance={"name": self.name, "version": self.version})
            return result
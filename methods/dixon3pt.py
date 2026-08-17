"""Dixon 3pt method"""

from pathlib import Path

from runner.method import Method, Result
from dicomstack import DicomStack
from mutools.fatwater.utils import make_mask, make_ffmap
from mutools.fatwater.dixon import dixon_3pt
from mutools.fatwater.readers import parse_dicom_dixon_default
from musegai.io import Image
import numpy as np
from musegai.api import run_model
from methods.get_results.getresults import getresults

MODEL_BY_SEGMENT = {"legs": "museg-legs:model1", "thighs": "museg-thighs:model3"}

class Dixon3ptMethod(Method) :
    name = "dixon3pt"
    version = "1.0"
    comparability_criteria = []

    def run (self, exam_dir, workdir, segment):
        stack = DicomStack(exam_dir)
        if not stack : #erreur possible
            raise ValueError(f"No dicom data found in {exam_dir}")
        #erreur 
        try :
            info, volumes = parse_dicom_dixon_default(stack, npoint=3)
            echo_times = info["echo_times"]
        except Exception as exc:
            raise ValueError(f"Could not parse Dixon DICOM data in {exam_dir}") from exc
        mask = make_mask(*volumes, axis=2, threshold=10)
        try :
            water_map, fat_map, delta_b0, r2_star = dixon_3pt(echo_times, *volumes, mask = mask, force_reconstruction=False, global_swap=False)
            ffmap = make_ffmap(water_map, fat_map, mask=mask)
        except Exception as exc:
            raise RuntimeError(f"Dixon 3pt reconstruction failed for {exam_dir}") from exc
        # mag_1 = abs(water_map + fat_map)
        # mag_2 = abs(water_map - fat_map)
        #erreur possible
        mag_1 = abs(volumes[0])
        mag_2 = abs(volumes[1])
        mag_1 = np.nan_to_num(mag_1)
        mag_2 = np.nan_to_num(mag_2)

        #erreur possible
        transform_flat = [v for row in mag_1.transform for v in row]
        img_1 = Image(mag_1, transform=transform_flat)
        img_2 = Image(mag_2, transform=transform_flat)

        model = MODEL_BY_SEGMENT[segment]
        try :
            rois, labels = run_model(model=model, images=[(img_1, img_2)], side="LR")
        except Exception as e:
            raise RuntimeError(f"Segmentation failed for {exam_dir} (segment={segment})") from e
        table = getresults(volumes={"ffmap": ffmap}, roi=rois[0], labels=labels, method_name="dixon3pt")
        # TODO: remplacer par un passage direct de la table en mémoire à
        # medical_report/csv_parser, une fois le chemin heureux validé.
        csv_path = Path(workdir) / "results.csv"
        table.to_csv(csv_path, index=False)
        return Result(
            results=csv_path,
            auto_valid=True,
            provenance={"name": self.name, "version": self.version},
        )

if __name__ == "__main__":
    from runner import methods_registry
    from runner.job import Job
    from runner.job_runner import run_job

    methods_registry.register(Dixon3ptMethod)
    job = Job(exam_id="dixon_data_test", segment="legs", method_id="dixon3pt")
    run_job(job, dev=True)
    print(job)
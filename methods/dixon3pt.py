"""Dixon 3pt method"""

from runner.method import Method
from dicomstack import DicomStack
from mutools.fatwater.utils import make_mask, make_ffmap
from mutools.fatwater.dixon import dixon_3pt
from mutools.fatwater.readers import parse_dicom_dixon_default
from musegai.io import Image
import numpy as np
from musegai.api import run_model

MODEL_BY_SEGMENT = {"legs": "museg-legs:model1", "thighs": "museg-thighs:model3"}

class Dixon3ptMethod(Method) :
    name = "dixon3pt"
    version = "1.0"
    comparability_criteria = []

    def run (self, exam_dir, workdir, segment):
        stack = DicomStack(exam_dir)
        if not stack :
            raise ValueError(f"No dicom data found in {exam_dir}")
        info, volumes = parse_dicom_dixon_default(stack, npoint=3)
        echo_times = info["echo_times"]
        mask = make_mask(*volumes, axis=2, threshold=10)
        water_map, fat_map, delta_b0, r2_star = dixon_3pt(echo_times, *volumes, mask = mask, force_reconstruction=False, global_swap=False)
        ffmap = make_ffmap(water_map, fat_map, mask=mask)
        # mag_1 = abs(water_map + fat_map)
        # mag_2 = abs(water_map - fat_map)
        mag_1 = abs(volumes[0])
        mag_2 = abs(volumes[1])
        mag_1 = np.nan_to_num(mag_1)
        mag_2 = np.nan_to_num(mag_2)

        transform_flat = [v for row in mag_1.transform for v in row]
        img_1 = Image(mag_1, transform=transform_flat)
        img_2 = Image(mag_2, transform=transform_flat)

        model = MODEL_BY_SEGMENT[segment]

        rois, labels = run_model(model=model, images=[(img_1, img_2)], side="LR")
        

if __name__ == "__main__":
    method = Dixon3ptMethod()
    method.run("dixon_data_test", "workdir_test", "legs")
"""Dixon 3pt method"""

from runner.method import Method
from dicomstack import DicomStack, DICOM
from mutools.fatwater.utils import make_mask, make_ffmap
from mutools.fatwater.dixon import dixon_3pt
from musegai.io import Image 
from pathlib import Path
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
        EchoTime = stack.EchoTime
        echo_times = sorted(stack.unique(EchoTime))
        if not echo_times:
            EchoTime = stack.EffectiveEchoTime
            echo_times = sorted(stack.unique(EchoTime))
        if not echo_times:
            raise ValueError("Could not find echo-time values")
        echo_times = [echo for echo in echo_times if not np.isclose(echo, 0)]
        manufacturer = stack.single("Manufacturer")

        if manufacturer.lower().startswith('siemens'):
            image_type = {"selector": DICOM.ImageType[2], "magnitude": "M", "phase": "P"}
            phase_scale = np.pi / 4096.0

        elif manufacturer.lower().startswith('philips'):
            image_type = {"selector": DICOM.ImageType[3], "magnitude": "M", "phase": "P"}
            phase_scale =  1e-3
        else:
            raise ValueError(f"Manufacturer {manufacturer} not handled")

        ImType = image_type["selector"]
        volumes = []
        for echo in echo_times:
            mag = stack((EchoTime == echo) & (ImType == image_type["magnitude"])).as_volume(rescale=True)
            pha = stack((EchoTime == echo) & (ImType == image_type["phase"])).as_volume(rescale=True)
            volume = mag * np.exp(1j * pha * phase_scale)
            volumes.append(volume)
        sequence = stack.single(DICOM.SequenceName, default=None)
        field_strength = stack.single(DICOM.MagneticFieldStrength, default=None)

        info = {
            "manufacturer": manufacturer,
            "sequence": sequence,
            "field_strength": field_strength,
            "echo_times": echo_times,
        }
        mask = make_mask(*volumes, axis=2, threshold=10)
        water_map, fat_map, delta_b0, r2_star = dixon_3pt(echo_times, *volumes, mask = mask, force_reconstruction=False, global_swap=False)
        ffmap = make_ffmap(water_map, fat_map, mask=mask)
        mag_1 = abs(water_map + fat_map)
        mag_2 = abs(water_map - fat_map)
        mag_1 = np.nan_to_num(mag_1)
        mag_2 = np.nan_to_num(mag_2)
        mag_2.transform = [v for row in mag_2.transform for v in row]
        mag_1.transform = [v for row in mag_1.transform for v in row]
        mag_2 = np.nan_to_num(mag_2)
        mag_2.transform = [v for row in mag_2.transform for v in row]
        mag_1.transform = [v for row in mag_1.transform for v in row]
        # print(f"{type(volumes[0])} et {dir(volumes[0])}")
        print(mag_1.spacing,  mag_1.origin, mag_1.transform)
        
        transform_flat = [v for row in mag_1.transform for v in row]
        img_1 = Image(mag_1, transform=transform_flat)
        img_2 = Image(mag_2, transform=transform_flat)
        #si probleme :
        # img_1.save(Path(workdir) / "mag_1.mha")
        # img_2.save(Path(workdir) / "mag_2.mha")
        image=[(mag_1, mag_2)]

        model = MODEL_BY_SEGMENT[segment]

        rois, labels = run_model(model=model, images=[(mag_1, mag_2)], side="LR")

if __name__ == "__main__":
    method = Dixon3ptMethod()
    method.run("dixon_data_test", "workdir_test", "legs")
"""Patient height and weight: DICOM headers -> result JSON metadata (methods/patient_measures.py)."""

import pandas as pd
import pytest

from methods.patient_measures import patient_measures
from results_writer.writer import parse_table


class FakeStack:
    """Stands for a DicomStack: single() as in dicomstack (default when missing, ValueError when ambiguous)."""

    def __init__(self, **values):
        self.values = values

    def single(self, field, default=...):
        value = self.values.get(field)
        if isinstance(value, list):
            raise ValueError(f"Multiple values found for {field}")
        return default if value is None else value


def test_height_and_weight_are_read_in_metres_and_kg():
    assert patient_measures(FakeStack(PatientSize="1.68", PatientWeight="61")) == \
        {"patient_size": 1.68, "patient_weight": 61.0}


@pytest.mark.parametrize("values", [
    {},                                              # not in the headers
    {"PatientSize": "0", "PatientWeight": "0"},      # not entered at the console
    {"PatientSize": ["1.6", "1.7"], "PatientWeight": ["60", "62"]},   # different between series
])
def test_missing_zero_or_ambiguous_values_are_left_empty(values):
    assert patient_measures(FakeStack(**values)) == {"patient_size": None, "patient_weight": None}


def test_height_and_weight_are_written_in_the_result_json():
    table = pd.DataFrame([{"HOW": "VOLUME", "LABEL": "TA_R", "FF": 0.1, "NPIX": 10}])
    metadata = {"exam_id": "E1", "exam_date": "2026-11-04", "segment": "legs", "method": "dixon3pt",
                "version": "1.0", "acquisition": "1.0", "segmentation": "museg", "biomarker": "FF",
                "patient_size": 1.68, "patient_weight": 61.0}

    exam = parse_table(table, metadata)

    assert (exam.metadata.patient_size, exam.metadata.patient_weight) == (1.68, 61.0)

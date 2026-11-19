"""Patient height and weight from the DICOM headers of the processed series.

They are entered at the MR console for each exam (PatientSize in metres, PatientWeight in kg) and kept
by the pseudonymisation. The PACS (Telemis) does not return them in a C-FIND: the DICOM headers are
the only source. Written in the result JSON metadata, printed in the report header.
"""


def patient_measures(stack):
    """{"patient_size": metres, "patient_weight": kg}, each None when missing, zero (not entered at the
    console) or different between the selected series."""
    measures = {}
    for key, field in (("patient_size", "PatientSize"), ("patient_weight", "PatientWeight")):
        try:
            value = stack.single(field, default=None)
        except ValueError:          # several values in the selected series: none is trusted
            value = None
        try:
            value = float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            value = None
        measures[key] = value if value else None
    return measures

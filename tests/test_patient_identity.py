"""Re-identification (FONC-005): adapters/patient_identity.fetch_identity asks the PACS (C-FIND) for the
patient's name and birth date. The PACS is replaced by a fake Find: no network in the tests."""

import pytest
from pydicom import Dataset

from adapters import patient_identity
from adapters.patient_identity import PatientIdentityError, fetch_identity


def _study(name, birth_date):
    ds = Dataset()
    ds.PatientName, ds.PatientBirthDate = name, birth_date
    return ds


@pytest.fixture
def pacs(monkeypatch):
    """Fake PACS: answers with the studies put in pacs.answer, records the query in pacs.query."""
    class FakeFind:
        answer, query = [], None

        def __init__(self, config):
            pass

        def search_data(self, criteria):
            FakeFind.query = criteria
            return FakeFind.answer

    monkeypatch.setattr(patient_identity, "Find", FakeFind)
    return FakeFind


def test_query_by_exam_id_and_dicom_date(pacs):
    pacs.answer = [_study("DOE^JOHN", "19800101")]

    fetch_identity("CL2LD260112", "2026-01-12")

    assert (pacs.query.level, pacs.query.patient_id, pacs.query.study_date) == ("STUDY", "CL2LD260112", "20260112")


def test_identity_formatted_for_the_report(pacs):
    pacs.answer = [_study("DOE^JOHN", "19800101")]

    assert fetch_identity("CLX", "2026-01-12") == {"patient_name": "DOE JOHN", "birth_date": "01/01/1980"}


def test_several_studies_of_the_same_patient_accepted(pacs):
    """One exam can be stored as several studies the same day."""
    pacs.answer = [_study("DOE^JOHN", "19800101"), _study("DOE^JOHN", "19800101")]

    assert fetch_identity("CLX", "2026-01-12")["patient_name"] == "DOE JOHN"


@pytest.mark.parametrize("answer", [[], [_study("DOE^JOHN", "19800101"), _study("ROE^JANE", "19900101")]],
                         ids=["no study (PACS unreachable or unknown exam)", "different identities"])
def test_no_identity_guessed(pacs, answer):
    pacs.answer = answer

    with pytest.raises(PatientIdentityError):
        fetch_identity("CLX", "2026-01-12")


def test_error_message_has_no_patient_name(pacs):
    pacs.answer = [_study("DOE^JOHN", "19800101"), _study("ROE^JANE", "19900101")]

    with pytest.raises(PatientIdentityError) as error:
        fetch_identity("CLX", "2026-01-12")

    assert "DOE" not in str(error.value) and "ROE" not in str(error.value)

from dicom.config.server_config import TelemisConfig
from dicom.services.find import Find
from dicom.services.search_criteria import SearchCriteria

class PatientIdentityError(Exception):
    pass

def fetch_identity(exam_id, exam_date) :
    finder = Find(TelemisConfig)
    # exam_date from the JSON: "2026-01-12"; DICOM dates: "20260112"
    criteria = SearchCriteria(level="STUDY", patient_id=exam_id, study_date=exam_date.replace("-", ""))
    result = finder.search_data(criteria)

    # one exam can be stored as several studies the same day: accepted if they all give the same identity
    if not result:
        raise PatientIdentityError(f"No study found on the PACS for {exam_id} on {exam_date}")
    identities = []
    for ds in result:
        identity = (str(ds.PatientName), str(ds.PatientBirthDate))
        if identity not in identities:
            identities.append(identity)
    if len(identities) > 1:
        raise PatientIdentityError(f"{len(result)} studies for {exam_id} on {exam_date} with different identities")
    name, birth_date = identities[0]

    # DICOM: name "NAME^FIRSTNAME", birth date "19800101" -> "NAME FIRSTNAME", "01/01/1980"
    name = name.replace("^", " ").strip()
    if len(birth_date) == 8:
        birth_date = f"{birth_date[6:8]}/{birth_date[4:6]}/{birth_date[0:4]}"
    return {"patient_name": name, "birth_date": birth_date}

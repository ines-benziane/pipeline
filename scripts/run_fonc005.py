"""FONC-005 (identity of the report): the PDF carries the right patient identity.

For each exam of a RES-003 run (its JSON results, resultats_tests/RES003_<date>/<exam>/json/):
  1. build the report as delivered: name and birth date asked to the PACS (C-FIND, adapters/patient_identity.py);
  2. check automatically that the exam date printed in the report is the StudyDate of the exam's DICOM;
  3. write a grid to fill by hand: name and birth date of each PDF compared with the Telemis viewer
     (an independent source: comparing with another C-FIND would test the code with itself).
Plus the failure case, on the first exam: no study found on the PACS -> report still produced, identity left blank.

The PDF (and Medical_report.html) contain the real identity: they are written to a LOCAL folder outside the
repository and outside N: (default: <home>/FONC005_tmp), to delete once the grid is filled (--clean).
The grid contains no name: exam IDs and results only. It is written to resultats_tests/FONC005_<date>/.

Usage (PC or station, pipeline env, the machine must reach Telemis):
  python scripts/run_fonc005.py --run-dir <...>/resultats_tests/RES003_20261110 --dicom-dir <...>/dicom_lot
  python scripts/run_fonc005.py --clean          delete the local folder of PDF with identities
"""

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pydicom
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.medical_report_generator import MedicalReportGenerator  # noqa: E402
from adapters.patient_identity import fetch_identity  # noqa: E402

LOCAL_OUT = Path.home() / "FONC005_tmp"


def text(html):
    html = re.sub(r'src="data:[^"]+"', "", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def dicom_study_date(exam_dicom: Path) -> str | None:
    """StudyDate of the exam (any DICOM file of its folder), as YYYY-MM-DD like the report."""
    f = next(exam_dicom.rglob("*.dcm"), None)
    if f is None:
        return None
    d = str(pydicom.dcmread(f, stop_before_pixels=True).get("StudyDate", ""))
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else None


def build_report(exam, json_dir, out, identity_provider):
    """Report of one exam; returns (identity found on the PACS, text of the report header and body)."""
    found = []

    def provider(exam_id, exam_date):
        identity = identity_provider(exam_id, exam_date)   # raises PatientIdentityError if not found
        found.append(True)
        return identity

    out.mkdir(parents=True, exist_ok=True)
    pdf = MedicalReportGenerator(identity_provider=provider).generate([exam], json_dir, out, lang="fr")
    pdf.replace(out / f"{exam}.pdf")
    return bool(found), text((out / "Medical_report.html").read_text(encoding="utf-8"))


def write_grid(rows, failure, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "FONC-005"
    ws.append(["FONC-005 : identité du rapport. Nom et date de naissance de chaque PDF comparés à la visionneuse "
               "Telemis (examen = identifiant + date). La grille ne contient aucun nom."])
    ws["A1"].font = Font(bold=True, size=12)
    headers = ["Examen", "Identité trouvée sur le PACS", "Date d'examen du PDF = StudyDate DICOM (automatique)",
               "Nom et date de naissance du PDF = Telemis", "Vérifié par", "Remarque"]
    ws.append(headers)
    for cell in ws[2]:
        cell.font, cell.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="264653")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[2].height = 45
    choice = DataValidation(type="list", formula1='"Conforme,Non conforme"', allow_blank=True)
    ws.add_data_validation(choice)
    for r in rows:
        ws.append([r["exam"], "oui" if r["found"] else "NON", r["date_check"], "", "", r["remark"]])
        choice.add(ws.cell(row=ws.max_row, column=4))
    ws.append([])
    ws.append(["Cas d'échec (aucune étude trouvée sur le PACS, sur " + failure["exam"] + ")",
               "rapport produit" if failure["pdf"] else "PAS de rapport",
               "champs identité vides" if failure["blank"] else "champs identité NON vides", "", "", ""])
    for col, width in zip("ABCDEF", [16, 16, 26, 26, 16, 40]):
        ws.column_dimensions[col].width = width
    wb.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", type=Path, help="RES-003 run (one folder per exam with json/)")
    parser.add_argument("--dicom-dir", type=Path, help="DICOM of the lot (one folder per exam)")
    parser.add_argument("--out", type=Path, default=LOCAL_OUT, help=f"local folder for the PDF (default {LOCAL_OUT})")
    parser.add_argument("--clean", action="store_true", help="delete the local folder of PDF with identities")
    args = parser.parse_args()

    if args.clean:
        shutil.rmtree(args.out, ignore_errors=True)
        print(f"deleted {args.out}")
        return
    if not (args.run_dir and args.dicom_dir):
        parser.error("--run-dir and --dicom-dir are required")
    if str(args.out.resolve()).startswith((str(ROOT), "N:", "\\\\")) or "rmn_files" in str(args.out):
        parser.error(f"{args.out}: the PDF contain identities, keep them out of the repository and of N:")

    exams = sorted(p.name for p in args.run_dir.iterdir() if (p / "json").is_dir() and any((p / "json").glob("*.json")))
    rows = []
    for exam in exams:
        found, report = build_report(exam, args.run_dir / exam / "json", args.out / exam, fetch_identity)
        expected = dicom_study_date(args.dicom_dir / exam)
        printed = re.search(r"Date d'examen : (\d{4}-\d{2}-\d{2})", report)
        printed = printed.group(1) if printed else None
        ok = printed is not None and printed == expected
        rows.append(dict(exam=exam, found=found, date_check="Conforme" if ok else "Non conforme",
                         remark="" if ok else f"PDF {printed}, DICOM {expected}"))
        print(f"{exam}: identity {'found' if found else 'NOT FOUND'}, exam date {'OK' if ok else 'DIFFERENT'}")

    # failure case: a date with no study on the PACS
    exam = exams[0]
    found, report = build_report(exam, args.run_dir / exam / "json", args.out / "failure_case",
                                 lambda exam_id, exam_date: fetch_identity(exam_id, "1900-01-01"))
    failure = dict(exam=exam, pdf=(args.out / "failure_case" / f"{exam}.pdf").exists(),
                   blank=(not found) and "Patient(e) : Date de naissance : Adressé" in report)
    print(f"failure case ({exam}): report {'produced' if failure['pdf'] else 'NOT produced'}, "
          f"identity {'blank' if failure['blank'] else 'NOT blank'}")

    grid_dir = ROOT / "resultats_tests" / f"FONC005_{datetime.now():%Y%m%d}"
    grid_dir.mkdir(parents=True, exist_ok=True)
    grid = grid_dir / "FONC005_verification.xlsx"
    write_grid(rows, failure, grid)
    print(f"\nGrid: {grid}\nPDF with identities: {args.out}  (compare with Telemis, then: "
          f"python scripts/run_fonc005.py --clean)")


if __name__ == "__main__":
    main()

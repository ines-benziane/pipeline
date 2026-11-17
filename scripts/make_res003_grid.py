"""RES-003: verification grid to fill by hand, one row per exam and segment of the series table.

Sheet 1 "Vérification": one row per exam and segment, the files to open, one column per criterion
(drop-down Conforme / Non conforme / Sans objet), who checked, remarks.
Sheet 2 "Mode opératoire": what is checked, how, with landmarks a non-radiologist can use.
Output next to the run: resultats_tests/RES003_<date>/RES003_verification.xlsx

Usage: python scripts/make_res003_grid.py resultats_tests/RES003_<date>
"""

import csv
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
CHOICES = ("Conforme", "Non conforme", "Sans objet")
HEADER_FILL = PatternFill("solid", fgColor="264653")
WRAP = Alignment(wrap_text=True, vertical="top")
THIN = Border(*(Side(style="thin", color="BBBBBB"),) * 4)

# (column header, file checked, how to check it, landmarks)
CRITERIA = [
    ("1. Rapport PDF : vue clinique (droite du patient à droite de la page) — tous les examens",
     "PDF, schémas et tableaux FF et T2",
     "Sur chaque schéma, le membre droit du patient (tableau « Droite (R) ») est à droite de la page et le gauche "
     "(« Gauche (L) ») à gauche ; la face avant du membre est en haut.",
     "Les valeurs de chaque côté sont celles de muReport pour ce côté (contrôle automatique RES-004). "
     "Jambe : tibial antérieur (TA) en haut. Cuisse : quadriceps (VL, VM, VI, RF) en haut."),
    ("2. Image de contrôle (GIF) : vue radiologique (comparaison avec ITK-SNAP) — 6 examens",
     "segmentation.gif, et ffmap.mha + roi.mha du même dossier dans ITK-SNAP",
     "Ouvrir ffmap.mha dans ITK-SNAP (lettres R, L, A, P sur les bords de la vue axiale), y charger roi.mha et "
     "labels.txt. Sur une même coupe, le GIF doit montrer la même image que ITK-SNAP : avant (A) en haut, "
     "droite du patient (R) à gauche de l'écran, chaque muscle du même côté (ex. TA_R à gauche).",
     "Comparer un détail propre à un côté (membre plus gros, muscle plus gras). "
     "ITK-SNAP lit l'orientation dans l'en-tête du fichier : c'est la référence."),
    ("3. Image de contrôle (GIF) : les couleurs de la segmentation sont issues des labels — 6 examens",
     "segmentation.gif",
     "Chaque couleur suit le contour d'un muscle visible, sans décalage ni débordement dans la graisse.",
     "La graisse est claire, le muscle gris foncé. Un décalage d'un muscle à l'autre, ou une couleur sur la graisse, "
     "est non conforme."),
    ("4. Carte de graisse (overview) : vue radiologique (comparaison avec ITK-SNAP) — 6 examens",
     "overview.png, et ffmap.mha du même dossier dans ITK-SNAP",
     "Même méthode que le critère 2 : l'overview est la carte ffmap.mha. Sur une même coupe, avant (A) en haut et "
     "droite du patient (R) à gauche de l'écran, comme dans ITK-SNAP.",
     "Sur la carte de graisse, la graisse est claire et le muscle sombre ; la moelle des os est grasse, donc claire."),
]


def dixon_qc_job(exam_dir: Path, segment: str) -> str:
    """Latest QC folder of the Dixon run of this segment (it holds overview.png and segmentation.gif)."""
    jobs = []
    for job in (exam_dir / "qc").glob("*"):
        labels = job / "labels.txt"
        if (job / "overview.png").exists() and (job / "segmentation.gif").exists() and labels.exists():
            if ("thighs" if "VL" in labels.read_text(errors="replace") else "legs") == segment:
                jobs.append(job)
    return f"{exam_dir.name}\\qc\\{max(jobs).name}\\" if jobs else ""


def header(ws, titles, widths):
    ws.append(titles)
    for cell, width in zip(ws[ws.max_row], widths):
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = THIN
        ws.column_dimensions[cell.column_letter].width = width


def grid_sheet(ws, rows, run_dir):
    ws.title = "Vérification"
    ws.append(["RES-003 : orientation des images et des schémas du rapport. "
               "Une ligne par examen et segment. "
               "Mode opératoire : feuille suivante."])
    ws["A1"].font = Font(bold=True, size=12)
    header(ws, ["Examen", "Segment", "Rapport PDF", "Images de contrôle (dossier)"] + [c[0] for c in CRITERIA]
           + ["Vérifié par", "Remarque"], [14, 10, 20, 46] + [22] * len(CRITERIA) + [16, 40])
    ws.row_dimensions[2].height = 105

    choice = DataValidation(type="list", formula1='"' + ",".join(CHOICES) + '"', allow_blank=True)
    ws.add_data_validation(choice)
    first = 5
    for r in rows:
        exam_dir = run_dir / r["exam"]
        segment = {"legs": "jambes", "thighs": "cuisses"}[r["segment"]]
        if r["status"] != "OK":
            ws.append([r["exam"], segment, "non produit", "", *["Sans objet"] * len(CRITERIA), "",
                       f"Non lancé : {r['remark']}"])
        else:
            pdf = exam_dir / f"{r['exam']}.pdf"
            values = [""] * len(CRITERIA)
            ws.append([r["exam"], segment, f"{r['exam']}\\{pdf.name}" if pdf.exists() else "non produit",
                       dixon_qc_job(exam_dir, r["segment"])] + values + ["", ""])
            for col in range(first, first + len(CRITERIA)):
                choice.add(ws.cell(row=ws.max_row, column=col))
        for cell in ws[ws.max_row]:
            cell.border, cell.alignment = THIN, WRAP
    ws.freeze_panes = "E3"


def method_sheet(ws, run_dir):
    ws.title = "Mode opératoire"
    lines = [
        ("RES-003 : vérification de l'orientation des images", True),
        ("Objet : vérifier que les schémas du rapport PDF et les images de contrôle de la segmentation sont affichés "
         "dans le bon sens (avant/arrière, droite/gauche, externe/interne), et que la segmentation automatique "
         "recouvre bien les muscles.", False),
        (f"Fichiers : dans {run_dir}, un dossier par examen. Le rapport est <examen>.pdf. Les images de contrôle sont "
         "dans le dossier indiqué sur la ligne (colonne « Images de contrôle ») : segmentation.gif (coupes avec la "
         "segmentation en couleur) et overview.png (carte de graisse).", False),
        ("Pour chaque case : « Conforme », « Non conforme » (décrire en remarque) ou « Sans objet » "
         "(critère non applicable ou non vérifiable sur cet examen). Indiquer qui a vérifié.", False),
        ("Conventions attendues : rapport PDF en vue clinique (droite du patient à droite de la page) ; images de "
         "contrôle (GIF, overview) en vue radiologique, comme à la console IRM (droite du patient à gauche de l'écran). "
         "Le côté droit/gauche ne se reconnaît pas à l'œil : pour les images, la référence est ITK-SNAP.", False),
        ("Rapport PDF (critère 1) : vérifié sur tous les examens, car c'est le document remis au médecin. "
         "Images de contrôle (critères 2 à 4) : vérifiées sur 6 examens. Leur orientation est produite par le même "
         "code pour tous les examens, à partir de la position du patient lue dans le DICOM (PatientPosition) : un défaut "
         "serait le même pour tous les examens acquis dans la même position. 21 examens ont été acquis pieds en premier "
         "(FFS) et 1 tête en premier (HFS, CL2OV260828) ; l'échantillon couvre les deux : 5 examens FFS + CL2OV260828.", False),
    ]
    for text, bold in lines:
        ws.append([text])
        ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=4)
        cell = ws.cell(ws.max_row, 1)
        cell.font, cell.alignment = Font(bold=bold, size=12 if bold else 11), WRAP
        ws.row_dimensions[ws.max_row].height = 18 if bold else 48
    ws.append([])
    header(ws, ["Critère (colonne de la feuille Vérification)", "Fichier à ouvrir", "Comment vérifier", "Repères"],
           [42, 24, 60, 60])
    for criterion in CRITERIA:
        ws.append(list(criterion))
        for cell in ws[ws.max_row]:
            cell.border, cell.alignment = THIN, WRAP
        ws.row_dimensions[ws.max_row].height = 75


def main():
    run_dir = Path(sys.argv[1])
    run_dir = run_dir if run_dir.is_absolute() else ROOT / run_dir
    with open(ROOT / "resultats_tests" / "RES003_series.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))

    wb = Workbook()
    grid_sheet(wb.active, rows, run_dir)
    method_sheet(wb.create_sheet(), run_dir)
    out = run_dir / "RES003_verification.xlsx"
    wb.save(out)
    print(out, f"({len(rows)} rows)")


if __name__ == "__main__":
    main()

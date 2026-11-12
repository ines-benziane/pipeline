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
    ("1. Rapport PDF : la face avant du membre est en haut du schéma",
     "PDF, schémas FF et T2",
     "Sur chaque schéma en coupe, les muscles de la face avant sont en haut.",
     "Jambe : tibial antérieur (TA) en haut, mollet (SOL, GAS) en bas. "
     "Cuisse : quadriceps (VL, VM, VI, RF) en haut, ischio-jambiers (SM, ST, BF) en bas."),
    ("2. Rapport PDF : le tableau « Droite (R) » donne les valeurs de la jambe droite du patient",
     "PDF, tableaux et schémas",
     "Le côté ne se reconnaît pas à l'œil (les deux membres se ressemblent). "
     "Vérifier sur un examen avec un signe propre à un côté (muscle très atteint d'un seul côté, artefact, prothèse) "
     "et comparer avec le compte rendu de la méthode manuelle.",
     "Sans signe propre à un côté : « Sans objet » et le noter en remarque."),
    ("3. Rapport PDF : les muscles externes sont du côté extérieur, les internes du côté intérieur",
     "PDF, schémas FF et T2",
     "Sur chaque schéma, les muscles de la face externe du membre sont du côté extérieur.",
     "Jambe : péroniers (PER) du côté du petit os (péroné), gastrocnémien médial (GAS_MED) du côté intérieur. "
     "Cuisse : vaste latéral (VL) à l'extérieur, gracile (GRA) et sartorius (SAR) à l'intérieur."),
    ("4. Image de contrôle (GIF) : la face avant du membre est en haut de l'image",
     "segmentation.gif",
     "Faire défiler le GIF : sur toutes les coupes, la face avant est en haut.",
     "Jambe : le tibia (gros os rond, juste sous la peau) est en haut. "
     "Cuisse : le fémur est au centre, la grosse masse du quadriceps au-dessus."),
    ("5. Image de contrôle (GIF) : la droite du patient est à gauche de l'écran",
     "segmentation.gif",
     "Convention radiologique : le patient est vu depuis ses pieds, sa droite apparaît à gauche de l'écran. "
     "Même méthode que le critère 2.",
     "Sans signe propre à un côté : « Sans objet » et le noter en remarque."),
    ("6. Image de contrôle (GIF) : les couleurs de la segmentation recouvrent bien les muscles",
     "segmentation.gif",
     "Chaque couleur suit le contour d'un muscle visible, sans décalage ni débordement dans la graisse.",
     "La graisse est claire, le muscle gris foncé. Un décalage d'un muscle à l'autre, ou une couleur sur la graisse, "
     "est non conforme."),
    ("7. Carte de graisse (overview) : la face avant du membre est en haut de l'image",
     "overview.png",
     "Sur chaque coupe de la colonne, la face avant est en haut.",
     "Sur la carte de graisse, la graisse est claire et le muscle sombre ; la moelle des os est grasse, donc claire. "
     "Jambe : le tibia (gros cercle clair, juste sous la peau) est en haut. Cuisse : le fémur au centre, "
     "la grosse masse sombre du quadriceps au-dessus."),
    ("8. Carte de graisse (overview) : la droite du patient est à gauche de l'écran, comme sur le GIF",
     "overview.png et segmentation.gif (même dossier)",
     "Comparer avec le GIF du même dossier : les deux membres sont dans le même sens "
     "(un membre reconnaissable, par sa forme ou un muscle atteint, est du même côté de l'écran sur les deux images).",
     "Sans signe propre à un côté : « Sans objet » et le noter en remarque."),
    ("9. Carte de graisse (FF) : la jambe droite n'est pas inversée (jambes uniquement)",
     "overview.png et PDF, schéma FF des jambes",
     "Les deux jambes ont un aspect comparable. Une jambe entièrement claire (« toute en graisse ») "
     "alors que l'autre est sombre signale une inversion eau/graisse.",
     "Cuisses : « Sans objet » (l'inversion ne concerne que les jambes)."),
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
               "Une ligne par examen et segment. Mode opératoire : feuille suivante."])
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
            if r["segment"] == "thighs":
                values[-1] = "Sans objet"
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
        ("Le côté droit/gauche ne se reconnaît pas à l'œil. La convention d'affichage droite/gauche du rapport reste "
         "à valider avec les médecins : décrire ce qui est vu en remarque.", False),
        ("Les 2 ou 3 premiers examens sont vérifiés avec un technicien ou un médecin, puis les suivants avec les mêmes "
         "repères. L'orientation est produite par le même code pour tous les examens ; la segmentation et "
         "l'inversion eau/graisse varient d'un examen à l'autre.", False),
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

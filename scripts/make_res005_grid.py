"""RES-005: verification grid and procedure, to compare in ITK-SNAP the maps of muReport with
those of the manual method, on 4 exams, legs and thighs, FF and T2.

muReport FF: resultats_tests/RES003_<date>/<exam>/qc/<exam>-<segment>-FF-dixon3pt-*/ (ffmap.mha, roi.mha, labels.txt)
muReport T2: resultats_tests/RES005_<date>/<exam>/<exam>-<segment>-T2-t2map-*/        (t2map.mha, roi_t2.mha, labels.txt)
Manual (read only), <Mesure_T2>/<year>/<year>_<exam>_*/:
  LEG|THIGH/FAT_RATIO   FF map x1000
  LEG|THIGH/T2_MAP_ROI  first echo image of the T2 series (NOT a T2 map: the manual method fits the mean signal of
                        each muscle on each slice, it has no T2 value per pixel), ROI_T2_LEG|THIGH: ROI drawn on it
Checked on the middle slice only (FF 32 of 64, T2 5 of 9). The ROI itself is judged by the segmentation QC test,
not here (no criterion C3). FF values: checked by eye on each muscle and side (threshold 10 points), not recorded.
An existing grid is rebuilt keeping what was already filled in (--from <xlsx>: take the entries from another copy).

Usage: python scripts/make_res005_grid.py resultats_tests/RES005_<date> resultats_tests/RES003_<date> [--from <xlsx>]
"""

import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_lot import find_manual_dir  # noqa: E402

EXAMS = {"CL2LD260112": "examen de référence",
         "CL2OV260828": "seul examen acquis tête en premier (HFS)",
         "CL2OK260630": "écart connu : T2 manuel effondré en coupe 7 des cuisses (RES-002)",
         "CL2MF260309": "examen le plus gras du lot"}
SEGMENTS = {"jambes": "LEG", "cuisses": "THIGH"}
CHOICES = ("Conforme", "Non conforme", "Écart connu (méthode manuelle)")
CRITERIA = ["C1. Même position", "C2. Même aspect et valeurs (FF) / carte plausible (T2)"]
# muReport folder used instead of the RES-003 one: the RES-003 run applied swap-right to every legs Dixon, but the
# legs of CL2MF260309 were not swapped to begin with; rerun without action on 2026-11-18.
FF_OVERRIDE = {("CL2MF260309", "jambes"): "CL2MF260309/CL2MF260309-20261118-095336-514c"}
CRITERIA_TEXT = {
    "FF": ["Le curseur placé sur un repère (centre du gros os, bord d'un muscle) tombe au même endroit anatomique dans "
           "les deux cartes, sur la coupe du milieu.",
           "Graisse claire et muscle sombre aux mêmes endroits dans les deux cartes, pour chaque membre (une jambe "
           "entièrement claire dans une seule carte = inversion eau/graisse). Valeurs : au centre de chaque muscle, "
           "côté droit et gauche, la valeur muReport x 1000 et la valeur manuelle diffèrent de moins de 100 (10 points "
           "de FF). Contrôle à l'œil, valeurs non reportées."],
    "T2": ["La carte T2 muReport et l'image d'écho de la méthode manuelle montrent la même anatomie au même endroit "
           "(curseur sur un repère), sur la coupe du milieu.",
           "Carte T2 muReport plausible : muscles sains environ 30 à 45 ms, pas de zone aberrante (plaque de valeurs "
           "nulles ou extrêmes au milieu d'un muscle, membre entier décalé). La méthode manuelle n'a pas de carte T2 à "
           "comparer. Pixel par pixel, les valeurs sont bornées par l'ajustement (10 à 70 ms) : des pixels isolés aux "
           "bornes sont attendus, et nombreux dans les muscles très gras (peu d'eau) ; la valeur T2 elle-même est "
           "jugée par RES-002."],
}
SLICES = {"FF": "coupe 32 (sur 64)", "T2": "coupe 5 (sur 9)"}
HEADER_FILL = PatternFill("solid", fgColor="264653")
WRAP = Alignment(wrap_text=True, vertical="top")
THIN = Border(*(Side(style="thin", color="BBBBBB"),) * 4)


def header(ws, titles, widths):
    ws.append(titles)
    for cell, width in zip(ws[ws.max_row], widths):
        cell.font, cell.fill, cell.border = Font(bold=True, color="FFFFFF"), HEADER_FILL, THIN
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[cell.column_letter].width = width


def one(folder: Path, pattern: str) -> str:
    found = sorted(folder.glob(pattern))
    return str(found[-1]) if found else "INTROUVABLE"


def previous_entries(path):
    """What was already filled in an existing grid: {(exam, segment, card): {column: value}}."""
    if not path.exists():
        return {}
    wb = load_workbook(path)
    ws = wb["Vérification"]
    head = [c.value for c in ws[2]]
    keep = [h for h in head if h and (h.startswith("C1") or h.startswith("C2") or h in ("Vérifié par", "Remarque"))]
    rows = {}
    for r in ws.iter_rows(min_row=3, values_only=True):
        if r[0]:
            rows[(r[0], r[1], r[2])] = {h[:2] if h.startswith("C") else h: r[head.index(h)] for h in keep}
    return rows


def grid_sheet(ws, res003, res005, before):
    ws.title = "Vérification"
    ws.append(["RES-005 : cartes de muReport comparées à la méthode manuelle dans ITK-SNAP, 4 examens, coupe du "
               "milieu. Mode opératoire : dernière feuille."])
    ws["A1"].font = Font(bold=True, size=12)
    header(ws, ["Examen", "Segment", "Carte", "Coupes", "muReport (dossier)", "Méthode manuelle (dossier)"]
           + CRITERIA + ["Vérifié par", "Remarque"], [14, 9, 6, 14, 60, 60, 16, 18, 16, 50])
    ws.row_dimensions[2].height = 45
    choice = DataValidation(type="list", formula1='"' + ",".join(CHOICES) + '"', allow_blank=True)
    ws.add_data_validation(choice)
    for exam, why in EXAMS.items():
        manual = find_manual_dir(exam)
        for segment, part in SEGMENTS.items():
            for card in ("FF", "T2"):
                if card == "FF":
                    override = FF_OVERRIDE.get((exam, segment))
                    mine = str(res005 / override) if override else one(res003 / exam / "qc",
                                                                       f"{exam}-{segment}-FF-dixon3pt-*")
                    theirs = f"{manual / part / 'FAT_RATIO'}"
                else:
                    mine = one(res005 / exam, f"{exam}-{segment}-T2-t2map-*")
                    theirs = (f"{manual / part / 'T2_MAP_ROI'}  (image d'écho, pas une carte T2) ; "
                              f"ROI : {manual / ('ROI_T2_' + part)}")
                old = before.get((exam, segment, card), {})
                ws.append([exam, segment, card, SLICES[card], mine, theirs,
                           old.get("C1"), old.get("C2"), old.get("Vérifié par"), old.get("Remarque") or why])
                for col in (7, 8):
                    choice.add(ws.cell(row=ws.max_row, column=col))
                for cell in ws[ws.max_row]:
                    cell.border, cell.alignment = THIN, WRAP
    ws.freeze_panes = "G3"


def method_sheet(ws):
    ws.title = "Mode opératoire"
    steps = [
        ("RES-005 : comparaison dans ITK-SNAP", True),
        ("Objet : vérifier que les cartes produites par muReport sont cohérentes avec celles de la méthode manuelle : "
         "pas d'inversion eau/graisse, pas de décalage, carte T2 plausible. Les moyennes par muscle sont comparées par "
         "RES-001 (FF) et RES-002 (T2, aussi coupe par coupe). La segmentation (ROI) est jugée par le test de QC de "
         "la segmentation, pas ici.", False),
        ("Échantillon : 4 examens, jambes et cuisses. CL2LD260112 : examen de référence. CL2OV260828 : seul examen "
         "acquis tête en premier. CL2OK260630 : écart connu de la méthode manuelle (T2 effondré en coupe 7 des cuisses, "
         "RES-002). CL2MF260309 : examen le plus gras du lot.", False),
        ("Ouvrir une ligne de la feuille Vérification :", True),
        ("1. File > Open Main Image : ffmap.mha (FF) ou t2map.mha (T2) du dossier « muReport ».", False),
        ("2. Segmentation > Open Segmentation : roi.mha (FF) ou roi_t2.mha (T2) ; Segmentation > Import Label "
         "Descriptions : labels.txt (même dossier). Sert à repérer les muscles.", False),
        ("3. File > Add Another Image (ou glisser en choisissant « Additional Image ») : img_00001.dcm du dossier "
         "« Méthode manuelle » (lecture seule ; ne jamais enregistrer). Mise en page côte à côte. Contraste : Tools > "
         "Image Contrast.", False),
        ("4. Sur la coupe du milieu (colonne « Coupes »), juger C1 et C2 (critères ci-dessous). Remplir « Conforme », "
         "« Non conforme » (décrire : coupe, membre, muscle) ou « Écart connu (méthode manuelle) » quand la différence "
         "vient d'une erreur documentée des données manuelles.", False),
        ("Valeurs FF (dans C2) : sur la coupe du milieu, cliquer au centre de chaque muscle, côté droit puis gauche, "
         "et comparer à l'œil les deux valeurs affichées : muReport x 1000 et valeur manuelle à moins de 100 (10 "
         "points de FF). Pixel par pixel, quelques unités d'écart sont attendues. Valeurs non reportées. T2 : pas de "
         "comparaison de valeurs, la méthode manuelle n'a pas de valeur T2 par pixel.", False),
        ("Critères FF — C1 : " + CRITERIA_TEXT["FF"][0] + " C2 : " + CRITERIA_TEXT["FF"][1], False),
        ("Critères T2 — C1 : " + CRITERIA_TEXT["T2"][0] + " C2 : " + CRITERIA_TEXT["T2"][1], False),
    ]
    for text, bold in steps:
        ws.append([text])
        cell = ws.cell(ws.max_row, 1)
        cell.font, cell.alignment = Font(bold=bold, size=12 if bold else 11), WRAP
        ws.row_dimensions[ws.max_row].height = 18 if bold else 55
    ws.column_dimensions["A"].width = 130


def main():
    res005, res003 = (Path(a) if Path(a).is_absolute() else ROOT / a for a in sys.argv[1:3])
    out = res005 / "RES005_verification.xlsx"
    source = Path(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[3] == "--from" else out
    before = previous_entries(source)
    wb = Workbook()
    grid_sheet(wb.active, res003, res005, before)
    method_sheet(wb.create_sheet())
    wb.save(out)
    print(out, f"({len(before)} rows kept)")


if __name__ == "__main__":
    main()

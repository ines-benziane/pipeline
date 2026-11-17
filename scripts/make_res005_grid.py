"""RES-005: verification grid, values sheet and procedure, to compare in ITK-SNAP the maps and ROI of muReport with
those of the manual method, on 4 exams, legs and thighs, FF and T2.

muReport FF: resultats_tests/RES003_<date>/<exam>/qc/<exam>-<segment>-FF-dixon3pt-*/ (ffmap.mha, roi.mha, labels.txt)
muReport T2: resultats_tests/RES005_<date>/<exam>/<exam>-<segment>-T2-t2map-*/        (t2map.mha, roi_t2.mha, labels.txt)
Manual (read only), <Mesure_T2>/<year>/<year>_<exam>_*/:
  LEG|THIGH/FAT_RATIO   FF map x1000
  LEG|THIGH/T2_MAP_ROI  first echo image of the T2 series (NOT a T2 map: the manual method fits the mean signal of
                        each muscle on each slice, it has no T2 value per pixel), ROI_T2_LEG|THIGH: ROI drawn on it
Values (FF only): 1 value per muscle and side on the middle slice, threshold 10 points.
An existing grid is rebuilt keeping what was already filled in.

Usage: python scripts/make_res005_grid.py resultats_tests/RES005_<date> resultats_tests/RES003_<date>
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
MUSCLES = {"jambes": ["TA", "ED", "PER", "DLPC", "POP", "SOL", "GAS_MED", "GAS_LAT"],
           "cuisses": ["VL", "VI", "VM", "RF", "SAR", "GRA", "SM", "ST", "BF", "AM", "AL"]}
CHOICES = ("Conforme", "Non conforme", "Écart connu (méthode manuelle)")
CRITERIA = ["C1. Même position", "C2. Même aspect (FF) / carte plausible (T2)", "C3. ROI sur les muscles"]
CRITERIA_TEXT = {
    "FF": ["Le curseur placé sur un repère (centre du gros os, bord d'un muscle) tombe au même endroit anatomique dans "
           "les deux cartes, sur les 3 coupes.",
           "Graisse claire et muscle sombre aux mêmes endroits dans les deux cartes, pour chaque membre (une jambe "
           "entièrement claire dans une seule carte = inversion eau/graisse).",
           "Les couleurs de la ROI de muReport suivent les contours des muscles, sans décalage ni débordement dans la "
           "graisse."],
    "T2": ["La carte T2 muReport et l'image d'écho de la méthode manuelle montrent la même anatomie au même endroit "
           "(curseur sur un repère), sur les 3 coupes.",
           "Carte T2 muReport plausible : muscles sains environ 30 à 45 ms, pas de zone aberrante (valeurs nulles ou "
           "extrêmes au milieu d'un muscle). La méthode manuelle n'a pas de carte T2 à comparer.",
           "Les couleurs de roi_t2.mha suivent les muscles de l'image, comme la ROI dessinée par la méthode manuelle "
           "(ROI_T2)."],
}
SLICES = {"FF": "coupes 16, 32 et 48 (sur 64)", "T2": "coupes 3, 5 et 7 (sur 9)"}
VALUE_SLICE = "32 (sur 64)"
FF_THRESHOLD = 10   # points
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
    """What was already filled in an existing grid: {(exam, segment, card): {column: value}}, and the values."""
    if not path.exists():
        return {}, {}
    wb = load_workbook(path)
    ws = wb["Vérification"]
    head = [c.value for c in ws[2]]
    keep = [h for h in head if h and (h.startswith("C1") or h.startswith("C2") or h.startswith("C3")
                                      or h in ("Vérifié par", "Remarque"))]
    rows = {}
    for r in ws.iter_rows(min_row=3, values_only=True):
        if r[0]:
            rows[(r[0], r[1], r[2])] = {h[:2] if h.startswith("C") else h: r[head.index(h)] for h in keep}
    values = {}
    if "Valeurs FF" in wb.sheetnames:
        wv = wb["Valeurs FF"]
        for r in wv.iter_rows(min_row=4, values_only=True):
            if r[0]:
                values[(r[0], r[1], r[3], r[4])] = (r[5], r[6])
    return rows, values


def grid_sheet(ws, res003, res005, before):
    ws.title = "Vérification"
    ws.append(["RES-005 : cartes et ROI de muReport comparées à la méthode manuelle dans ITK-SNAP, 4 examens. "
               "Valeurs FF : feuille « Valeurs FF ». Mode opératoire : dernière feuille."])
    ws["A1"].font = Font(bold=True, size=12)
    header(ws, ["Examen", "Segment", "Carte", "Coupes", "muReport (dossier)", "Méthode manuelle (dossier)"]
           + CRITERIA + ["Vérifié par", "Remarque"], [14, 9, 6, 16, 60, 60, 16, 18, 16, 14, 45])
    ws.row_dimensions[2].height = 45
    choice = DataValidation(type="list", formula1='"' + ",".join(CHOICES) + '"', allow_blank=True)
    ws.add_data_validation(choice)
    for exam, why in EXAMS.items():
        manual = find_manual_dir(exam)
        for segment, part in SEGMENTS.items():
            for card in ("FF", "T2"):
                if card == "FF":
                    mine = one(res003 / exam / "qc", f"{exam}-{segment}-FF-dixon3pt-*")
                    theirs = f"{manual / part / 'FAT_RATIO'}"
                else:
                    mine = one(res005 / exam, f"{exam}-{segment}-T2-t2map-*")
                    theirs = (f"{manual / part / 'T2_MAP_ROI'}  (image d'écho, pas une carte T2) ; "
                              f"ROI : {manual / ('ROI_T2_' + part)}")
                old = before.get((exam, segment, card), {})
                ws.append([exam, segment, card, SLICES[card], mine, theirs,
                           old.get("C1"), old.get("C2"), old.get("C3"), old.get("Vérifié par"),
                           old.get("Remarque") or why])
                for col in (7, 8, 9):
                    choice.add(ws.cell(row=ws.max_row, column=col))
                for cell in ws[ws.max_row]:
                    cell.border, cell.alignment = THIN, WRAP
    ws.freeze_panes = "G3"


def values_sheet(ws, before):
    ws.title = "Valeurs FF"
    ws.append([f"Valeurs FF : 1 valeur par muscle et par côté, au centre du muscle, sur la coupe {VALUE_SLICE}. "
               f"Seuil : {FF_THRESHOLD} points d'écart. Saisir la valeur muReport telle qu'affichée (0 à 1) et la "
               "valeur manuelle telle qu'affichée (x1000) ; l'écart et le résultat se calculent."])
    ws["A1"].font = Font(bold=True, size=11)
    ws.append([])
    header(ws, ["Examen", "Segment", "Coupe", "Muscle", "Côté", "muReport (0 à 1)", "Manuel (x1000)",
                "Écart (points)", "Résultat"], [14, 9, 12, 10, 6, 14, 14, 13, 16])
    first = ws.max_row + 1
    for exam in EXAMS:
        for segment in SEGMENTS:
            for muscle in MUSCLES[segment]:
                for side in ("R", "L"):
                    mine, theirs = before.get((exam, segment, muscle, side), (None, None))
                    ws.append([exam, segment, VALUE_SLICE, muscle, side, mine, theirs])
                    r = ws.max_row
                    ws.cell(r, 8).value = f'=IF(OR(F{r}="",G{r}=""),"",ROUND(ABS(F{r}*1000-G{r})/10,1))'
                    ws.cell(r, 9).value = f'=IF(H{r}="","",IF(H{r}<={FF_THRESHOLD},"dans le seuil","HORS SEUIL"))'
                    for cell in ws[r]:
                        cell.border = THIN
    last = ws.max_row
    ws["K3"], ws["L3"] = "Valeurs saisies", f'=COUNT(H{first}:H{last})'
    ws["K4"], ws["L4"] = "Dans le seuil", f'=COUNTIF(I{first}:I{last},"dans le seuil")'
    ws["K5"], ws["L5"] = "Hors seuil", f'=COUNTIF(I{first}:I{last},"HORS SEUIL")'
    ws.column_dimensions["K"].width = 16
    ws.freeze_panes = f"F{first}"


def method_sheet(ws):
    ws.title = "Mode opératoire"
    steps = [
        ("RES-005 : comparaison dans ITK-SNAP", True),
        ("Objet : vérifier que les cartes et la segmentation produites par muReport sont cohérentes avec celles de la "
         "méthode manuelle : pas de muscle mal délimité, pas d'inversion eau/graisse, pas de décalage. Les moyennes par "
         "muscle sont comparées par RES-001 (FF) et RES-002 (T2, aussi coupe par coupe).", False),
        ("Échantillon : 4 examens, jambes et cuisses. CL2LD260112 : examen de référence. CL2OV260828 : seul examen "
         "acquis tête en premier. CL2OK260630 : écart connu de la méthode manuelle (T2 effondré en coupe 7 des cuisses, "
         "RES-002). CL2MF260309 : examen le plus gras du lot.", False),
        ("Ouvrir une ligne de la feuille Vérification :", True),
        ("1. File > Open Main Image : ffmap.mha (FF) ou t2map.mha (T2) du dossier « muReport ».", False),
        ("2. Segmentation > Open Segmentation : roi.mha (FF) ou roi_t2.mha (T2) ; Segmentation > Import Label "
         "Descriptions : labels.txt (même dossier).", False),
        ("3. File > Add Another Image (ou glisser en choisissant « Additional Image ») : img_00001.dcm du dossier "
         "« Méthode manuelle » (lecture seule ; ne jamais enregistrer). Mise en page côte à côte. Contraste : Tools > "
         "Image Contrast.", False),
        ("4. Sur les 3 coupes de la colonne « Coupes », juger C1, C2, C3 (critères ci-dessous). Remplir « Conforme », "
         "« Non conforme » (décrire : coupe, membre, muscle) ou « Écart connu (méthode manuelle) » quand la différence "
         "vient d'une erreur documentée des données manuelles.", False),
        ("Valeurs FF (feuille Valeurs FF) : sur la coupe 32, cliquer au centre de chaque muscle, côté droit puis gauche, "
         "et saisir les deux valeurs affichées. Seuil : 10 points (muReport x 1000 comparé à la valeur manuelle : 100 "
         "unités). Pixel par pixel, quelques points d'écart sont attendus (reconstructions différentes). T2 : pas de "
         "relevé, la méthode manuelle n'a pas de valeur T2 par pixel.", False),
        ("Critères FF — C1 : " + CRITERIA_TEXT["FF"][0] + " C2 : " + CRITERIA_TEXT["FF"][1] + " C3 : "
         + CRITERIA_TEXT["FF"][2], False),
        ("Critères T2 — C1 : " + CRITERIA_TEXT["T2"][0] + " C2 : " + CRITERIA_TEXT["T2"][1] + " C3 : "
         + CRITERIA_TEXT["T2"][2], False),
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
    before, values = previous_entries(out)
    wb = Workbook()
    grid_sheet(wb.active, res003, res005, before)
    values_sheet(wb.create_sheet(), values)
    method_sheet(wb.create_sheet())
    wb.save(out)
    print(out, f"({len(before)} rows kept)")


if __name__ == "__main__":
    main()

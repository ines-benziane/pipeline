"""Build MuReport-feuille-de-route-phase1_2026-10-23.docx: action plan to finish phase 1 tests.

Same visual base as build_rapport_tests_auto001.py.
"""


from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ACCENT = RGBColor(0x26, 0x46, 0x53)      # deep teal
ACCENT_HEX = "264653"
LIGHT_HEX = "E8EEF0"                      # pale teal fill
CALLOUT_HEX = "F3EDE2"                    # warm sand fill
GREY = RGBColor(0x6B, 0x6B, 0x6B)
DARK = RGBColor(0x22, 0x22, 0x22)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

doc = Document()
sec = doc.sections[0]
sec.left_margin = sec.right_margin = Pt(64)
sec.top_margin = sec.bottom_margin = Pt(56)

# --- base styles -----------------------------------------------------------
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(10.5)
normal.font.color.rgb = DARK
normal.paragraph_format.space_after = Pt(4)
normal.paragraph_format.line_spacing = 1.12

for lvl, size in ((1, 15), (2, 11.5)):
    h = doc.styles[f"Heading {lvl}"]
    h.font.name = "Calibri"
    h.font.size = Pt(size)
    h.font.bold = True
    h.font.color.rgb = ACCENT
    h.paragraph_format.space_before = Pt(18 if lvl == 1 else 10)
    h.paragraph_format.space_after = Pt(5)
    h.paragraph_format.keep_with_next = True

for s in ("List Bullet", "List Bullet 2", "List Number"):
    st = doc.styles[s]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    st.font.color.rgb = DARK
    st.paragraph_format.space_after = Pt(3)


def _shade(el, hex_fill):
    tcpr = el.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcpr.append(shd)


def bottom_border(paragraph, hex_color=ACCENT_HEX, sz="8"):
    p = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), "6")
    bottom.set(qn("w:color"), hex_color)
    borders.append(bottom)
    p.append(borders)


def para(text, size=None, color=None, italic=False, bold=False,
         align=None, space_before=None, space_after=None):
    par = doc.add_paragraph()
    run = par.add_run(text)
    if size:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    run.font.italic = italic
    run.font.bold = bold
    if align is not None:
        par.alignment = align
    if space_before is not None:
        par.paragraph_format.space_before = Pt(space_before)
    if space_after is not None:
        par.paragraph_format.space_after = Pt(space_after)
    return par


def bullets(items, style="List Bullet"):
    for it in items:
        if isinstance(it, tuple):
            para_bullet(it[0], style)
            bullets(it[1], style="List Bullet 2")
        else:
            para_bullet(it, style)


def para_bullet(text, style="List Bullet"):
    p = doc.add_paragraph(style=style)
    p.add_run(text)
    return p


def callout(label, text, fill=CALLOUT_HEX):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.rows[0].cells[0]
    _shade(cell._tc, fill)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(label + " ")
    r.font.bold = True
    r.font.color.rgb = ACCENT
    r.font.size = Pt(10.5)
    r2 = p.add_run(text)
    r2.font.size = Pt(10.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return tbl


def data_table(headers, rows, widths=None):
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = "Table Grid"
    hdr = tbl.rows[0].cells
    for i, h in enumerate(headers):
        _shade(hdr[i]._tc, ACCENT_HEX)
        p = hdr[i].paragraphs[0]
        r = p.add_run(h)
        r.font.bold = True
        r.font.color.rgb = WHITE
        r.font.size = Pt(10)
    for ri, row in enumerate(rows):
        cells = tbl.add_row().cells
        for ci, val in enumerate(row):
            if ri % 2 == 1:
                _shade(cells[ci]._tc, LIGHT_HEX)
            p = cells[ci].paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(10)
            if ci == 0:
                r.font.bold = True
                r.font.color.rgb = ACCENT
    if widths:
        for row in tbl.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Pt(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return tbl


def checklist(items):
    tbl = doc.add_table(rows=0, cols=2)
    tbl.style = "Table Grid"
    for it in items:
        cells = tbl.add_row().cells
        cells[0].width = Pt(20)
        p0 = cells[0].paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rb = p0.add_run("\u2610")
        rb.font.size = Pt(12)
        rb.font.color.rgb = ACCENT
        r = cells[1].paragraphs[0].add_run(it)
        r.font.size = Pt(10)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return tbl


# --- title ---------------------------------------------------------------
para("Feuille de route — fin de la phase 1 des tests", size=22, bold=True, color=ACCENT, space_after=2)
t = para("muReport · Inès Benziane  —  du 23 au 30 octobre 2026", size=11, color=GREY, space_after=12)
bottom_border(t)
para("Objectif : terminer les tests de phase 1 du plan de tests (MuReport-plan-de-tests.xlsx) pour le 30 octobre, "
     "afin que les techniciens puissent utiliser muReport en usage pilote.",
     italic=True, color=GREY, space_after=14)

# --- 1. où on en est ----------------------------------------------------------
doc.add_heading("1. Où on en est (22 octobre au soir)", level=1)
data_table(["Test", "État", "Commentaire"], [
    ["AUTO-001", "Fait, conforme", "231 cas sur les 3 briques, 225 réussis, 6 échecs attendus ; rapport et preuves "
     "dans doc/MuReport et resultats_tests/."],
    ["FONC-002, FONC-003", "Partiel", "Comportement du code vérifié automatiquement ; reste l'essai sur un vrai "
     "examen corrompu et un vrai examen incomplet."],
    ["RES-004", "Partiel", "Valeurs du rapport = valeurs du calcul, vérifié automatiquement ; reste la vérification "
     "sur le lot de 16 examens."],
    ["FONC-005", "Bloqué", "La ré-identification n'existe pas encore : seule la date d'examen est vérifiable."],
    ["RES-001, RES-002, RES-003, RES-005", "À faire", "Nécessitent le lot de référence et les résultats Matlab."],
    ["VAL-001, VAL-002b, VAL-004", "À faire", "Nécessitent les techniciens et le médecin."],
], widths=[110, 70, 280])

# --- 2. calendrier --------------------------------------------------------------
doc.add_heading("2. Aujourd'hui (vendredi 23, télétravail)", level=1)
para("Sans les DICOM du lot, tout se prépare sur l'examen CL2LD260112 : ses DICOM sont dans golden_tests/, "
     "ses ROI et tableaux Matlab sur N:.")
data_table(["Tâche", "Qui", "Pour"], [
    ["Chantier 1 : permettre à muReport d'accepter une segmentation extérieure (ROI Matlab) à la place de MuSeg-AI.",
     "IB, relu par Claude", "RES-001, RES-002"],
    ["Chantier 2 : écrire le script de comparaison muReport / Matlab (tableau des écarts).", "IB, relu par Claude", "RES-001, RES-002, NR-001"],
    ["Envoyer à l'administrateur PACS la demande d'un AE pour la station Prométhée (IP 192.168.4.81, port à convenir).",
     "IB", "Récupération du lot à distance"],
    ["Si le temps le permet : vérifier les pathologies du lot dans les CR (#4_CR_2026).", "IB", "Représentativité du lot"],
], widths=[300, 90, 70])

doc.add_heading("3. Ensuite (d'ici au 30 octobre)", level=1)
data_table(["Tâche", "Qui", "Pour"], [
    ["Réserver les 3 techniciens (mercredi ou jeudi).", "IB", "VAL-001, VAL-002b"],
    ["Avec le responsable : fixer les tolérances FF et T2, reformuler FONC-005, décider de la date de VAL-004.", "IB + resp.", "RES-001, RES-002, FONC-005, VAL-004"],
    ["Récupérer les DICOM du lot avec run_process (au bureau, ou depuis la station une fois l'AE créé) ; "
     "ranger mappings.csv hors du dossier du lot.", "IB", "RES-001 à 005"],
    ["Passage 1 : muReport sur le lot avec MuSeg-AI, mêmes séries que Matlab, QC global ; corriger les inversions "
     "(global-swap) et les compter.", "IB", "RES-003, RES-004, FONC-005"],
    ["Passage 2 : muReport sur le lot avec la ROI Matlab (entrées identiques).", "IB", "RES-001, RES-002"],
    ["Comparer, fixer la tolérance à partir des cas extrêmes, consigner Pass / Fail par examen.", "IB + resp.", "RES-001, RES-002"],
    ["Vérifications visuelles : orientation, valeurs du PDF, ITK-SNAP sur 4 examens ; 2 runs du même examen.", "IB", "RES-003, RES-004, RES-005, DET-001"],
    ["Sauvegarder les résultats validés comme référence de non-régression.", "IB", "NR-001"],
    ["Trouver le cas « séquence absente », fabriquer le cas « corrompu », essais réels consignés.", "IB", "FONC-002, FONC-003"],
    ["Message clair quand une série est mal saisie ou qu'un dossier n'existe pas.", "IB, relu par Claude", "VAL-002b, VAL-002c"],
    ["Sessions avec les techniciens.", "IB + techs", "VAL-001, VAL-002b"],
    ["Reprise du rapport (palette de couleurs, mise en page, ajout de AB et BF_SH aux tableaux).", "IB", "Avant VAL-004"],
    ["Session avec le médecin, avec MuReport-regles-cliniques.docx.", "IB + médecin", "VAL-004"],
], widths=[300, 90, 70])

# --- 3. décisions -------------------------------------------------------------
doc.add_heading("4. Décisions à prendre", level=1)
data_table(["Décision", "Pourquoi", "Avec qui"], [
    ["Tolérances FF et T2 (le « X » de RES-001 et RES-002)", "Sans elles, la comparaison avec Matlab n'a pas de verdict.", "Responsable"],
    ["Segmentation de référence", "Décidé : muReport acceptera la segmentation Matlab (comparaison à entrées identiques, voir section 4).", "Fait (IB)"],
    ["Reformulation de FONC-005", "L'identité du patient ne peut pas apparaître tant que la ré-identification n'existe pas : "
     "limiter le test à la date d'examen, ou le reporter.", "Responsable"],
    ["Date de VAL-004", "Le plan la fixe au 27/10. Si le rapport est repris après, le médecin aura validé une version "
     "périmée : déplacer VAL-004 après la reprise, ou ne faire valider maintenant que le contenu (valeurs, phrases, règles).",
     "Responsable, médecin"],
], widths=[140, 240, 80])

# --- 4. segmentation matlab ------------------------------------------------------
doc.add_heading("5. Comparaison avec Matlab : ce qu'il faut savoir", level=1)
para("Pour séparer les sources d'écart, comparer en deux temps :")
bullets([
    "Même ROI des deux côtés (celle de Matlab) : l'écart mesure uniquement la reconstruction (mutools contre Matlab). "
    "C'est la condition posée par le plan pour RES-001 et RES-002.",
    "ROI de muReport (MuSeg-AI) : l'écart mesure le pipeline complet, segmentation comprise.",
])
para("Ce que contient chaque examen Matlab (vu sur N:) :")
bullets([
    "deux segmentations par segment : ROI_DIXON_* (grille Dixon) et ROI_T2_* (grille T2), au format Analyze "
    "(roi.img / roi.hdr), avec labels au format ITK-SNAP et géométrie dans vol.mhd ;",
    "FF Dixon (mean_roi_fat_ratio.txt) : par groupes seulement (jambes EXT, FIB, TRIC ; cuisses QUAD, HSTR) ;",
    "FF recalée sur la grille T2 et T2 (mean_roi_fat_ratio_reg_t2_map.txt, estimated_T2.txt) : par muscle ;",
    "valeurs par coupe : moyenne à pondérer par le nombre de pixels ; T2 avec et sans correction B1 (comparer « sans B1 ») ;",
    "résultats Matlab = résultats après correction des inversions eau/graisse par les techniciens.",
])
para("Correspondance des muscles :")
bullets([
    "avec la ROI Matlab dans muReport (passage 2), les noms sont ceux de Matlab : comparaison muscle à muscle directe ;",
    "avec MuSeg-AI (passage 1) : jambes, DLPC (un bloc) correspond à TP + FLEX_HL + FLEX_DI côté Matlab ; POP absent de la ROI T2 "
    "Matlab ; cuisses, AB et BF_SH absents de la ROI T2 Matlab. On compare les muscles communs, et la FF Dixon par groupes.",
])

# --- 5. répartition ----------------------------------------------------------------
doc.add_heading("6. Répartition du travail", level=1)
bullets([
    "Inès : décisions, données (lot, Matlab), essais réels, sessions techniciens et médecin, et le code formateur : "
    "script de comparaison, segmentation externe, messages d'erreur clairs.",
    "Claude : relecture du code, travail mécanique (tests automatisés, mise à jour du plan, du journal et des "
    "documents), aide à l'interprétation des écarts.",
])

# --- 6. après --------------------------------------------------------------------------
doc.add_heading("7. Après le 30 octobre (phase 2)", level=1)
bullets([
    "dicom : corriger l'option --anonymize (incident de gravité élevée) et tester les transferts avec un faux PACS.",
    "dicom : rendre configurable la liste des séquences de run_process (BIOMARKERS écrite en dur aujourd'hui).",
    "Cycle QC réel (pause, reprise, résultat) et refonte du QC (FONC-004).",
    "Équivalence T2 / mutools, dès qu'une référence existe.",
    "Ré-identification, puis FONC-005 complet.",
    "Questions au médecin : phrase T2 « normale limite », AB et BF_SH, borne de 70 ms.",
])

out = "MuReport-feuille-de-route-phase1_2026-10-23.docx"
doc.save(out)
print("saved", out)



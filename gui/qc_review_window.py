"""QC review window. One block per results file of the exam (segment x method), each with a map part, a
segmentation part and optional per-muscle errors; one QC is saved per block.

The window only calls the QC core (runner/qc_review.py: grade, check_complete, section_plan, copy_entries),
the QC store (save, list_for_block) and the run lookup (job_store: the run each block checks).
It holds no QC rule itself.
"""

import getpass
import os
import subprocess
import tkinter as tk
import uuid
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from adapters.file_qc_review_store import FileQCReviewStore
from runner import job_store
from runner.qc_review import (
    GRADE_RULES,
    ErrorCounts,
    Grade,
    MapCheck,
    MapDecision,
    Mention,
    MuscleError,
    QCReview,
    ReviewStatus,
    SectionFate,
    SegmentationCheck,
    SegmentationDecision,
    Side,
    check_complete,
    copy_entries,
    grade,
    section_plan,
)
from runner.qc_review_store import QCReviewStoreError

PRIMARY = "#2c3e50"   # same colours as gui/mureport.py
BG = "#f5f6f8"
GREY = "#7a7f87"
BUTTON = "#e4e6e9"
CHIP = "#e8edf3"
RED, ORANGE, GREEN = "#c0392b", "#d68910", "#27ae60"
GRADE_COLORS = {Grade.GOOD: GREEN, Grade.AVERAGE: ORANGE, Grade.POOR: RED}

BLOCKS = [("thighs", "dixon3pt"), ("thighs", "t2map_3exp"), ("legs", "dixon3pt"), ("legs", "t2map_3exp")]
SEGMENT_NAMES = {"thighs": "Cuisses", "legs": "Jambes"}
BIOMARKERS = {"dixon3pt": "FF", "t2map_3exp": "T2"}
# files written in the run's QC folder (qc mode global or checkpoint): image of the map, segmentation on its grid
QC_FILES = {"dixon3pt": ("ffmap.mha", "roi.mha"), "t2map_3exp": ("t2map.mha", "roi_t2.mha")}
# muscles offered for the per-muscle errors when the run's labels.txt is missing (report list)
DEFAULT_MUSCLES = {
    "thighs": ["VL", "VI", "VM", "RF", "SAR", "GRA", "SM", "ST", "BF", "BF_SH", "AM", "AL", "AB"],
    "legs": ["TA", "ED", "PER", "DLPC", "POP", "SOL", "GAS_MED", "GAS_LAT"],
}
BACKGROUND = "background"   # the "other" of an error between a muscle and what is not muscle

MAP_CHOICES = [(MapDecision.COMPLETE, "Complet"), (MapDecision.LEFT_ONLY, "Gauche seul"),
               (MapDecision.RIGHT_ONLY, "Droit seul"), (MapDecision.REJECTED, "Non")]
SEG_CHOICES = [(SegmentationDecision.ACCEPTED, "Acceptée"), (SegmentationDecision.REJECTED, "Rejetée")]
SIDE_CHOICES = [(Side.LEFT, "gauche"), (Side.RIGHT, "droite"), (Side.BOTH, "les deux")]
MAP_REASONS = ["", "Inversion eau/graisse", "Échec de la séparation sur une zone", "Artefact de mouvement",
               "Champ de vue incomplet", "Série manquante ou inexploitable"]
SEG_REASONS = ["", "Trop d'erreurs", "Segment mal identifié", "Autre"]
MENTIONS = {Mention.NOT_CHECKED: "non contrôlée", Mention.MAP_UNUSABLE: "cartographie non exploitable",
            Mention.SEGMENTATION_TO_REDO: "segmentation à refaire",
            Mention.SIDE_REMOVED: "un seul côté exploitable (section entière retirée pour l'instant)"}

COLUMNS_PT = [85, 105, 300, 245, 190, 150]   # same columns in every block, in points so they follow the screen scaling

ITKSNAP = os.environ.get("MUREPORT_ITKSNAP", str(Path.home() / "apps" / "itksnap.sh"))


def _new_qc_id(exam_id):
    """Same pattern as the job_id: <exam_id>-<date>-<time>-<4 characters>."""
    return f"{exam_id}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"


def _block_title(segment, method):
    return f"{SEGMENT_NAMES[segment]} · {BIOMARKERS[method]} ({method})"


def _side_label(side):
    return dict(SIDE_CHOICES)[side]


class BlockForm:
    """The widgets of one block and the QC they describe. `job` is the run checked, None if the block was not acquired."""

    def __init__(self, parent, exam_id, segment, method, job, on_change, on_copy):
        self.exam_id, self.segment, self.method, self.job = exam_id, segment, method, job
        self.title = _block_title(segment, method)
        self.qc_id = _new_qc_id(exam_id)
        self.copied_from = None
        self.errors = []   # MuscleError, in the order entered
        self._on_change = on_change
        self._ready = False   # no change notification while the widgets are being built

        self.acquired = job is not None
        if not self.acquired:
            frame = ttk.LabelFrame(parent, text=f"  {self.title}  ", padding=(8, 2, 8, 6), style="QCOff.TLabelframe")
            frame.pack(fill=tk.X, pady=(0, 6))
            tk.Label(frame, text="non acquis pour cet examen : rien à contrôler", bg=BG, fg=GREY,
                     font=("Helvetica", 10, "italic")).pack(anchor="w", padx=6)
            return

        self.qc_dir = Path(job.qc_dir) if job.qc_dir else None
        self.frame = ttk.LabelFrame(parent, text=f"  {self.title}  ", padding=(8, 2, 8, 6), style="QC.TLabelframe")
        self.frame.pack(fill=tk.X, pady=(0, 6))
        self._build_top(on_copy)
        self._build_header()
        self._build_map_row()
        self._build_segmentation_row()
        self._build_errors_row()
        self._ready = True
        self._changed()

    # --- widgets

    def _build_top(self, on_copy):
        top = tk.Frame(self.frame, bg=BG)
        top.grid(row=0, column=0, columnspan=6, sticky="we", pady=(0, 2))
        tk.Label(top, text=f"run {self.job.job_id}", bg=BG, fg=GREY).pack(side=tk.LEFT, padx=6)
        if not self._can_open_itksnap():
            tk.Label(top, text="segmentation absente du dossier de QC (run lancé sans mode QC) : ITK-SNAP indisponible",
                     bg=BG, fg=RED).pack(side=tk.LEFT, padx=6)
        self._note = tk.Label(top, text="", bg=BG, fg=ORANGE, font=("Helvetica", 9, "italic"))
        self._note.pack(side=tk.LEFT, padx=6)
        tk.Button(top, text="Copier depuis l'autre bloc", bg=BUTTON, fg=PRIMARY, relief="flat", padx=8,
                  command=lambda: on_copy(self)).pack(side=tk.RIGHT, padx=6)

    def _build_header(self):
        for col, width in enumerate(COLUMNS_PT):
            self.frame.grid_columnconfigure(col, minsize=self.frame.winfo_fpixels(f"{width}p"))
        for col, text in enumerate(["Partie", "Ouvrir", "Contrôle", "Décision", "Motif", "Commentaire"]):
            tk.Label(self.frame, text=text, bg=BG, fg=GREY, font=("Helvetica", 9, "bold")).grid(
                row=1, column=col, sticky="w", padx=6)

    def _build_map_row(self):
        row = 2
        self._part_label(row, "Cartographie")
        if self.method == "dixon3pt":
            self._button(row, 1, "Voir l'aperçu", self._show_overview, self._overview_path().exists())
            hint = "inversion, zone grise, artefact"
        else:
            tk.Label(self.frame, text="pas d'aperçu", bg=BG, fg=GREY, font=("Helvetica", 9, "italic")).grid(
                row=row, column=1, sticky="w", padx=6)
            hint = "artefact, champ de vue"
        tk.Label(self.frame, text=hint, bg=BG, fg=GREY).grid(row=row, column=2, sticky="w", padx=6)
        self.map_decision = self._decisions(row, MAP_CHOICES)[0]
        self.map_reason, self.map_comment = self._reason_and_comment(row, MAP_REASONS)

    def _build_segmentation_row(self):
        row = 3
        self._part_label(row, "Segmentation")
        self._button(row, 1, "Ouvrir ITK-SNAP", self._open_itksnap, self._can_open_itksnap())
        box = tk.Frame(self.frame, bg=BG)
        box.grid(row=row, column=2, sticky="w", padx=6)
        self.counts = {}
        for size in ("large", "medium", "small"):
            tk.Label(box, text=size, bg=BG, fg=GREY).pack(side=tk.LEFT)
            var = tk.StringVar(value="0")
            tk.Spinbox(box, from_=0, to=99, width=3, textvariable=var, state="readonly").pack(side=tk.LEFT, padx=(2, 8))
            var.trace_add("write", lambda *_: self._changed())
            self.counts[size] = var
        self._grade_label = tk.Label(box, text="", bg=BG, font=("Helvetica", 11, "bold"))
        self._grade_label.pack(side=tk.LEFT)
        self.seg_decision, self._seg_buttons = self._decisions(row, SEG_CHOICES)
        self.seg_reason, self.seg_comment = self._reason_and_comment(row, SEG_REASONS)

    def _build_errors_row(self):
        """Optional per-muscle errors: a pair (muscle / other muscle or background) and a side. Not used for the grade."""
        row = 4
        tk.Label(self.frame, text="Erreurs par muscle\n(facultatif)", bg=BG, fg=GREY, justify="left",
                 font=("Helvetica", 9)).grid(row=row, column=0, sticky="nw", padx=6, pady=(4, 0))
        box = tk.Frame(self.frame, bg=BG)
        box.grid(row=row, column=1, columnspan=5, sticky="w", padx=6, pady=(4, 0))
        self._chips = tk.Frame(box, bg=BG)
        self._chips.pack(anchor="w")
        adder = tk.Frame(box, bg=BG)
        adder.pack(anchor="w", pady=(2, 0))
        muscles = self._muscles()
        self._error_muscle = self._labelled_combobox(adder, "muscle", muscles, 9)
        self._error_other = self._labelled_combobox(adder, "avec", ["fond"] + muscles, 9)
        self._error_side = self._labelled_combobox(adder, "côté", [label for _, label in SIDE_CHOICES], 9)
        tk.Button(adder, text="+ Ajouter", bg=BUTTON, fg=PRIMARY, relief="flat", padx=8,
                  command=self._add_error).pack(side=tk.LEFT)

    def _part_label(self, row, text):
        tk.Label(self.frame, text=text, bg=BG, font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="w", padx=6)

    def _button(self, row, col, text, command, available):
        state = "normal" if available else "disabled"
        tk.Button(self.frame, text=text, bg=BUTTON, fg=PRIMARY, relief="flat", padx=8, command=command,
                  state=state).grid(row=row, column=col, sticky="w", padx=6)

    def _labelled_combobox(self, parent, label, values, width):
        tk.Label(parent, text=label, bg=BG, fg=GREY).pack(side=tk.LEFT)
        var = tk.StringVar(value="")
        ttk.Combobox(parent, values=values, textvariable=var, width=width, state="readonly").pack(side=tk.LEFT, padx=(2, 10))
        return var

    def _decisions(self, row, choices):
        """Radio buttons of one part; the variable holds the Enum value, "" while nothing is chosen."""
        var = tk.StringVar(value="")
        box = tk.Frame(self.frame, bg=BG)
        box.grid(row=row, column=3, sticky="w", padx=6, pady=3)
        buttons = {}
        for decision, label in choices:
            buttons[decision] = ttk.Radiobutton(box, text=label, value=decision.value, variable=var, style="QC.TRadiobutton")
            buttons[decision].pack(side=tk.LEFT, padx=(0, 6))
        var.trace_add("write", lambda *_: self._changed())
        return var, buttons

    def _reason_and_comment(self, row, reasons):
        reason = tk.StringVar(value="")
        ttk.Combobox(self.frame, values=reasons, textvariable=reason, width=28, state="readonly").grid(
            row=row, column=4, sticky="w", padx=6)
        comment = tk.StringVar(value="")
        tk.Entry(self.frame, textvariable=comment, width=22, relief="solid", bd=1).grid(row=row, column=5, sticky="w", padx=6)
        for var in (reason, comment):
            var.trace_add("write", lambda *_: self._changed())
        return reason, comment

    # --- per-muscle errors

    def _muscles(self):
        """Muscle names of the run's segmentation (labels.txt, side suffix removed), else the report list."""
        labels = self.qc_dir / "labels.txt" if self.qc_dir else None
        if labels and labels.exists():
            names = []
            for line in labels.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.split('"')
                if line.startswith("#") or len(parts) < 2 or not parts[1].strip():
                    continue
                name = parts[1].strip()
                for suffix in ("_R", "_L"):
                    name = name.removesuffix(suffix)
                if name.lower() not in ("clear label", "background", "noise") and name not in names:
                    names.append(name)
            if names:
                return names
        return DEFAULT_MUSCLES[self.segment]

    def _add_error(self):
        muscle, other, side = self._error_muscle.get(), self._error_other.get(), self._error_side.get()
        if not (muscle and other and side):
            messagebox.showwarning("Erreur par muscle", "Choisir le muscle, l'autre muscle (ou le fond) et le côté.",
                                   parent=self.frame)
            return
        other = BACKGROUND if other == "fond" else other
        if other == muscle:
            messagebox.showwarning("Erreur par muscle", "Les deux muscles de la paire doivent être différents.",
                                   parent=self.frame)
            return
        self.errors.append(MuscleError(muscle, other, next(s for s, label in SIDE_CHOICES if label == side)))
        for var in (self._error_muscle, self._error_other, self._error_side):
            var.set("")
        self._show_errors()

    def _remove_error(self, index):
        del self.errors[index]
        self._show_errors()

    def _show_errors(self):
        for chip in self._chips.winfo_children():
            chip.destroy()
        for index, error in enumerate(self.errors):
            chip = tk.Frame(self._chips, bg=CHIP, padx=6, pady=1)
            other = "fond" if error.other == BACKGROUND else error.other
            tk.Label(chip, text=f"{error.muscle} / {other} · {_side_label(error.side)}", bg=CHIP, fg=PRIMARY).pack(side=tk.LEFT)
            tk.Button(chip, text="✕", bg=CHIP, fg=GREY, relief="flat", bd=0, padx=2,
                      command=lambda i=index: self._remove_error(i)).pack(side=tk.LEFT)
            chip.pack(side=tk.LEFT, padx=(0, 6))
        self._changed()

    # --- entries <-> QC

    def _error_counts(self):
        return ErrorCounts(**{size: int(var.get() or 0) for size, var in self.counts.items()})

    def _changed(self):
        """Show the grade computed by the core; a poor grade forces 'Rejetée' (design doc §6.2)."""
        if not self._ready:
            return
        note = grade(self._error_counts(), GRADE_RULES)
        self._grade_label.config(text=f"→ {note.value.upper()}", fg=GRADE_COLORS[note])
        accepted = self._seg_buttons[SegmentationDecision.ACCEPTED]
        if note is Grade.POOR:
            accepted.state(["disabled"])
            if self.seg_decision.get() == SegmentationDecision.ACCEPTED.value:
                self.seg_decision.set(SegmentationDecision.REJECTED.value)
        else:
            accepted.state(["!disabled"])
        self._on_change()

    def touched(self):
        """True as soon as something was entered in the block."""
        return any([self.map_decision.get(), self.map_reason.get(), self.map_comment.get(),
                    self.seg_decision.get(), self.seg_reason.get(), self.seg_comment.get(),
                    self._error_counts() != ErrorCounts(0, 0, 0), self.errors])

    def to_qc(self, status, author, started_at, validated_at=None, duration_s=None):
        map_decision = self.map_decision.get()
        seg_decision = self.seg_decision.get()
        counts = self._error_counts()
        return QCReview(
            qc_id=self.qc_id, exam_id=self.exam_id, segment=self.segment, method=self.method,
            biomarker=BIOMARKERS[self.method], job_id=self.job.job_id, status=status, author=author,
            started_at=started_at, rules_version=GRADE_RULES.version,
            map=MapCheck(MapDecision(map_decision) if map_decision else None,
                         self.map_reason.get() or None, self.map_comment.get()),
            segmentation=SegmentationCheck(counts, grade(counts, GRADE_RULES),
                                           SegmentationDecision(seg_decision) if seg_decision else None,
                                           self.seg_reason.get() or None, self.seg_comment.get(), tuple(self.errors)),
            validated_at=validated_at, duration_s=duration_s, copied_from=self.copied_from,
        )

    def fill_from(self, qc, note):
        """Show the entries of `qc` (a copy made by copy_entries, or a draft read back) in the widgets."""
        self._ready = False
        for size, var in self.counts.items():
            var.set(str(getattr(qc.segmentation.counts, size)))
        self.map_decision.set(qc.map.decision.value if qc.map.decision else "")
        self.map_reason.set(qc.map.reason or "")
        self.map_comment.set(qc.map.comment)
        self.seg_decision.set(qc.segmentation.decision.value if qc.segmentation.decision else "")
        self.seg_reason.set(qc.segmentation.reason or "")
        self.seg_comment.set(qc.segmentation.comment)
        self.errors = list(qc.segmentation.errors)
        self.copied_from = qc.copied_from
        self._note.config(text=note)
        self._ready = True
        self._show_errors()

    def resume(self, draft):
        """Go on with a draft saved earlier: same qc_id, so validating it replaces the draft file."""
        self.qc_id = draft.qc_id
        self.fill_from(draft, f"brouillon du {draft.started_at:%d/%m/%Y %H:%M} repris")

    # --- files of the run

    def _overview_path(self):
        return self.qc_dir / "overview.png" if self.qc_dir else Path("overview.png-absent")

    def _can_open_itksnap(self):
        """ITK-SNAP needs the map of the block and its segmentation."""
        return self.qc_dir is not None and all((self.qc_dir / name).exists() for name in QC_FILES[self.method])

    def _show_overview(self):
        OverviewViewer(self.frame, self._overview_path(), f"Aperçu · {self.title} · run {self.job.job_id}")

    def _open_itksnap(self):
        """ITK-SNAP in the background (the QC window stays usable): map of the block, its segmentation, the labels."""
        image, roi = (self.qc_dir / name for name in QC_FILES[self.method])
        labels = self.qc_dir / "labels.txt"
        command = [ITKSNAP, "-g", str(image), "-s", str(roi)] + (["-l", str(labels)] if labels.exists() else [])
        try:
            subprocess.Popen(command)
        except OSError as error:
            messagebox.showerror("ITK-SNAP", f"Impossible de lancer ITK-SNAP ({ITKSNAP}) :\n{error}\n\n"
                                 "Chemin réglable avec la variable d'environnement MUREPORT_ITKSNAP.", parent=self.frame)


class OverviewViewer:
    """The run's overview.png in its own window, always shown whole: it opens fitted to the screen and follows
    the window size (aspect ratio kept). The image itself is the one the run wrote, untouched."""

    SCREEN_SHARE = 0.85   # largest part of the screen the window takes when it opens

    def __init__(self, parent, path, title):
        self.image = Image.open(path)
        self.top = tk.Toplevel(parent, bg="black")
        self.top.title(title)
        width, height = self.image.size
        scale = min(1.0, self.SCREEN_SHARE * self.top.winfo_screenwidth() / width,
                    self.SCREEN_SHARE * self.top.winfo_screenheight() / height)
        self.top.geometry(f"{max(1, int(width * scale))}x{max(1, int(height * scale))}")   # fixed by the user from now on
        self.label = tk.Label(self.top, bg="black")
        self.label.pack(fill=tk.BOTH, expand=True)
        self.label.bind("<Configure>", self._fit)

    def _fit(self, event):
        width, height = self.image.size
        scale = min(event.width / width, event.height / height)
        size = (max(1, int(width * scale)), max(1, int(height * scale)))
        self.photo = ImageTk.PhotoImage(self.image.resize(size, Image.LANCZOS))   # keep a reference for tkinter
        self.label.config(image=self.photo)


class QCReviewWindow:
    """Secondary window of MuReport, opened on one exam."""

    def __init__(self, parent, exam_id, store=None):
        self.exam_id = exam_id
        self.store = store if store is not None else FileQCReviewStore()
        self.author = getpass.getuser()
        self.started_at = datetime.now()
        jobs = job_store.load_exam_jobs(exam_id)

        self.top = tk.Toplevel(parent, class_="QCReview", bg=BG)
        self.top.title(f"MuReport · Contrôle qualité · {exam_id}")
        self._style()
        self._build_header()
        body = tk.Frame(self.top, bg=BG, padx=12)
        body.pack(fill=tk.X)
        self.blocks = []
        for segment, method in BLOCKS:
            job = job_store.latest_ready_job(jobs, segment, method)
            self.blocks.append(BlockForm(body, exam_id, segment, method, job,
                                         on_change=self._refresh_summary, on_copy=self._copy_into))
        self._build_summary()
        self._build_actions()
        self._resume_drafts()
        self._refresh_summary()
        self._tick()

    def _style(self):
        self.top.option_add("*QCReview*Font", ("Helvetica", 10))
        style = ttk.Style()
        style.configure("QC.TRadiobutton", background=BG, font=("Helvetica", 10))
        style.configure("QC.TLabelframe", background=BG, bordercolor=PRIMARY)
        style.configure("QC.TLabelframe.Label", foreground=PRIMARY, background=BG, font=("Helvetica", 11, "bold"))
        style.configure("QCOff.TLabelframe", background=BG, bordercolor="#c8ccd2")
        style.configure("QCOff.TLabelframe.Label", foreground=GREY, background=BG, font=("Helvetica", 11, "bold"))

    def _build_header(self):
        bar = tk.Frame(self.top, bg=PRIMARY, pady=6)
        bar.pack(fill=tk.X)
        tk.Label(bar, text="MuReport · Contrôle qualité", fg="white", bg=PRIMARY, font=("Helvetica", 13, "bold")).pack()
        info = tk.Frame(self.top, bg=BG, pady=6, padx=12)
        info.pack(fill=tk.X)
        tk.Label(info, text=f"Examen {self.exam_id}", bg=BG, fg=PRIMARY, font=("Helvetica", 12, "bold")).pack(side=tk.LEFT)
        tk.Label(info, text=f"   technicien : {self.author}", bg=BG, fg=GREY).pack(side=tk.LEFT)
        self._timer = tk.Label(info, text="", bg=BG, fg=PRIMARY, font=("Helvetica", 12, "bold"))
        self._timer.pack(side=tk.RIGHT)

    def _build_summary(self):
        frame = tk.LabelFrame(self.top, text="  Ce que le rapport contiendra  ", bg="#eef2f7", fg=PRIMARY,
                              font=("Helvetica", 11, "bold"), bd=1, relief="solid", padx=10, pady=4)
        frame.pack(fill=tk.X, padx=12, pady=(2, 6))
        self._summary_lines = [tk.Label(frame, text="", bg="#eef2f7", anchor="w") for _ in self.blocks]
        for label in self._summary_lines:
            label.pack(fill=tk.X)

    def _build_actions(self):
        actions = tk.Frame(self.top, bg=BG, pady=6)
        actions.pack(fill=tk.X, padx=12)
        tk.Button(actions, text="Valider le QC", bg=PRIMARY, fg="white", relief="flat", padx=18, pady=4,
                  font=("Helvetica", 11, "bold"), command=self._validate).pack(side=tk.RIGHT)
        tk.Button(actions, text="Enregistrer (reprendre plus tard)", bg=BUTTON, fg=PRIMARY, relief="flat",
                  padx=12, pady=4, command=self._save_drafts).pack(side=tk.RIGHT, padx=8)
        tk.Label(actions, text="Chaque bloc rempli est enregistré comme un QC à part. "
                 "Un bloc sans QC validé ne paraît pas dans le rapport.", bg=BG, fg=GREY).pack(side=tk.LEFT)

    def _tick(self):
        if not self.top.winfo_exists():
            return
        elapsed = int((datetime.now() - self.started_at).total_seconds())
        self._timer.config(text=f"⏱ {elapsed // 60:02d}:{elapsed % 60:02d}")
        self.top.after(1000, self._tick)

    def _resume_drafts(self):
        """A draft left on the current run of a block is filled back in (the most recent one)."""
        for block in self.blocks:
            if not block.acquired:
                continue
            drafts = [qc for qc in self.store.list_for_block(self.exam_id, block.segment, block.method)
                      if qc.status is ReviewStatus.DRAFT and qc.job_id == block.job.job_id]
            if drafts:
                block.resume(max(drafts, key=lambda qc: qc.started_at))

    def _refresh_summary(self):
        """What the report will contain, from section_plan of what is entered."""
        if not hasattr(self, "_summary_lines"):
            return   # blocks notify while the window is still being built
        for block, label in zip(self.blocks, self._summary_lines):
            name = block.title
            if not block.acquired:
                label.config(text=f"–  {name} : non acquis", fg=GREY)
            elif not block.touched():
                label.config(text=f"✖  {name} : non contrôlé, section retirée", fg=RED)
            else:
                plan = section_plan(block.to_qc(ReviewStatus.VALIDATED, self.author, self.started_at))
                if plan.fate is SectionFate.SHOWN:
                    label.config(text=f"✔  {name} : paraît", fg=GREEN)
                else:
                    reason = f" ({plan.reason})" if plan.reason else ""
                    label.config(text=f"✖  {name} : section retirée, {MENTIONS[plan.mention]}{reason}", fg=RED)

    def _copy_into(self, target):
        """'Copier depuis...': entries of the other block of the same segment, through copy_entries."""
        sources = [b for b in self.blocks if b is not target and b.acquired and b.segment == target.segment]
        if not sources:
            messagebox.showinfo("Copier", "L'autre bloc de ce segment n'est pas acquis : rien à copier.", parent=self.top)
            return
        source = sources[0]
        copied = copy_entries(source.to_qc(ReviewStatus.DRAFT, self.author, self.started_at),
                              target.to_qc(ReviewStatus.DRAFT, self.author, self.started_at))
        target.fill_from(copied, f"entrées copiées depuis {source.title} : à vérifier avant de valider")
        self._refresh_summary()

    def _filled_blocks(self):
        return [block for block in self.blocks if block.acquired and block.touched()]

    def _save(self, qcs, done_message):
        try:
            for qc in qcs:
                self.store.save(qc)
        except QCReviewStoreError as error:
            messagebox.showerror("QC", f"Enregistrement impossible :\n{error}", parent=self.top)
            return False
        messagebox.showinfo("QC", done_message, parent=self.top)
        self.top.destroy()
        return True

    def _save_drafts(self):
        """Keep what is entered, unchecked, to finish later (design doc: Should)."""
        blocks = self._filled_blocks()
        if not blocks:
            messagebox.showinfo("QC", "Aucun bloc rempli : rien à enregistrer.", parent=self.top)
            return
        drafts = [block.to_qc(ReviewStatus.DRAFT, self.author, self.started_at) for block in blocks]
        self._save(drafts, f"{len(drafts)} brouillon(s) enregistré(s), à reprendre en rouvrant le contrôle qualité "
                           f"de l'examen {self.exam_id}. Un brouillon ne compte pas pour le rapport.")

    def _validate(self):
        """Check every filled block with check_complete; save them all only if none is missing anything."""
        now = datetime.now()
        duration_s = int((now - self.started_at).total_seconds())
        to_save, problems = [], []
        for block in self._filled_blocks():
            qc = block.to_qc(ReviewStatus.VALIDATED, self.author, self.started_at, now, duration_s)
            missing = check_complete(qc, GRADE_RULES)
            if missing:
                problems.append(f"{block.title} :\n  - " + "\n  - ".join(missing))
            else:
                to_save.append(qc)
        if problems:
            messagebox.showwarning("QC incomplet", "Rien n'est enregistré. À compléter :\n\n" + "\n\n".join(problems),
                                   parent=self.top)
            return
        if not to_save:
            messagebox.showinfo("QC", "Aucun bloc rempli : rien à valider.", parent=self.top)
            return
        self._save(to_save, f"{len(to_save)} QC validé(s) pour l'examen {self.exam_id}.")

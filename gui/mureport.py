"""
gui/mureport.py
Mureport main window. 
"""

import json
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path

from adapters.dummy_exam_catalog import DummyExamCatalog
from runner.errors import PipelineError
from runner.parsing import parse_acquisition, parse_method, parse_series
from runner.pipeline import run_pipeline
from runner import methods_registry
from methods.dixon3pt import Dixon3ptMethod
from methods.t2map_3exp import T2Map3ExpMethod


methods_registry.register(Dixon3ptMethod)
methods_registry.register(T2Map3ExpMethod)

class MainApp():
    """Gathered all section forms and call run_pipeline for each of them"""

    def __init__(self):
        #Create main window
        self.root = tk.Tk()
        self.root.title("MuReport")
        self.root.geometry("720x560")
        self.root.resizable(True, True)
        self.sections = []

        self._build_ui()

        self.sections.append(SectionForm(parent=self.root))


    def _build_ui(self):
        """Create and place widgets in the window."""

        #Header
        header = tk.Frame(self.root, bg= "#2c3e50", pady=8)
        header.pack(fill=tk.X)
        tk.Label(
            header, 
            text="MuReport",
            fg="white", bg="#2c3e50",
            font=("Helvetica", 13, "bold"),
        ).pack()

        tk.Button(
            self.root, 
            text="Run",
            command=self._on_manage,
            width=22,
        ).pack(side=tk.LEFT, padx=4)

    def _on_manage(self):
        """Read section 0's fields, call run_pipeline once, show the result."""
        section = self.sections[0]

        exam_date = section.date_entry.get().strip() or None
        action = section.action_entry.get().strip() or None

        try:
            result = run_pipeline(
                catalog=DummyExamCatalog(),
                source_dir=section.source_dir_entry.get().strip(),
                acquisition_id=parse_acquisition(section.acquisition_id_entry.get().strip()),
                method=parse_method(section.method_entry.get().strip()),
                output_dir=section.output_dir_entry.get().strip(),
                series=parse_series(section.series_entry.get().strip()),
                qc=section.qc_mode_entry.get().strip() or "off",
                exam_id=section.exam_id_entry.get().strip() or None,
                exam_date=exam_date,
                debug=section.debug_var.get(),
                action=action,
                multicenter=section.multicenter_var.get(),
                seg_series=parse_series(section.seg_series_entry.get().strip()),
            )
        except PipelineError as exc:
            messagebox.showerror("Error", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Unexpected error", f"{type(exc).__name__}: {exc}")
            raise

        if result.status == "suspended":
            messagebox.showinfo(
                "Suspended for QC",
                f"Job {result.job_id} suspended (checkpoint: {result.checkpoint}).",
            )
        else:
            messagebox.showinfo("Done", f"Job {result.job_id} done — results written.")

class SectionForm:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="Section", padding=8)

        self._build_ui()
        self._load_defaults()

    def _build_ui(self):
        """Create and place widgets in the window."""

        self.frame.pack(fill=tk.X, padx=8, pady=4)
        self.frame.columnconfigure(1, weight=1)

        row = 0

        def add_entry(label_text):
            """Add one Label+Entry row, return the Entry widget."""
            nonlocal row
            tk.Label(self.frame, text=label_text).grid(row=row, column=0, sticky="w")
            entry = tk.Entry(self.frame)
            entry.grid(row=row, column=1, sticky="ew")
            row += 1
            return entry

        def add_checkbox(label_text):
            """Add one Checkbutton row, return its BooleanVar."""
            nonlocal row
            var = tk.BooleanVar(value=False)
            tk.Checkbutton(self.frame, text=label_text, variable=var).grid(
                row=row, column=0, columnspan=2, sticky="w"
            )
            row += 1
            return var

        self.exam_id_entry = add_entry("Exam ID")
        self.source_dir_entry = add_entry("Source directory")
        self.method_entry = add_entry("Method")
        self.acquisition_id_entry = add_entry("Acquisition ID (segment:side:acquisition)")
        self.output_dir_entry = add_entry("Output directory")
        self.series_entry = add_entry("Series")
        self.date_entry = add_entry("Date")
        self.qc_mode_entry = add_entry("Quality check mode")
        self.seg_series_entry = add_entry("Segmentation series")
        self.action_entry = add_entry("Action")

        self.debug_var = add_checkbox("Debug")
        self.open_qc_var = add_checkbox("Open QC folder")
        self.multicenter_var = add_checkbox("Multicenter")

    def _load_defaults(self):
        """Pre-fill the fields with default data."""
        self.qc_mode_entry.insert(0, "off")


if __name__ == "__main__":
    app = MainApp()
    app.root.mainloop()
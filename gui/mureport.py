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

        self._run_btn = tk.Button(
            self.root,
            text="Run",
            command=self._on_manage,
            width=22,
        )
        self._run_btn.pack(side=tk.LEFT, padx=4)

        prog_frame = tk.Frame(self.root)
        prog_frame.pack(fill=tk.X, padx=10, pady=(0,6))

        self._progress = ttk.Progressbar(prog_frame, mode="indeterminate", maximum=100)
        self._progress.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0,6))

        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(prog_frame, textvariable=self._status_var, anchor="w", width=28).pack(side=tk.RIGHT)

    def _set_status(self, text: str):
        """Met à jour le label de statut (thread-safe)."""
        self.root.after(0, lambda: self._status_var.set(text))

    def _on_manage(self):
        """Read section 0's fields (main thread), then hand off to a worker thread."""
        section = self.sections[0]

        try:
            kwargs = dict(
                source_dir=section.source_dir_entry.get().strip(),
                acquisition_id=parse_acquisition(section.acquisition_id_entry.get().strip()),
                method=parse_method(section.method_entry.get().strip()),
                output_dir=section.output_dir_entry.get().strip(),
                series=parse_series(section.series_entry.get().strip()),
                qc=section.qc_mode_entry.get().strip() or "off",
                exam_id=section.exam_id_entry.get().strip() or None,
                exam_date=section.date_entry.get().strip() or None,
                debug=section.debug_var.get(),
                action=section.action_entry.get().strip() or None,
                multicenter=section.multicenter_var.get(),
                seg_series=parse_series(section.seg_series_entry.get().strip()),
            )
        except Exception as exc:
            messagebox.showerror("Invalid input", f"{type(exc).__name__}: {exc}")
            return

        self._run_btn.config(state="disabled")
        self._set_status("Running...")
        self._progress.start()
        threading.Thread(target=self._run_job, kwargs=kwargs, daemon=True).start()

    def _run_job(self, **kwargs):
        """Runs off the main thread: calls run_pipeline, then reports back via .after()."""
        try:
            result = run_pipeline(catalog=DummyExamCatalog(), **kwargs)
        except PipelineError as exc:
            self.root.after(0, self._finish, None, str(exc))
            return
        except Exception as exc:
            self.root.after(0, self._finish, None, f"{type(exc).__name__}: {exc}")
            raise

        if result.status == "suspended":
            info = ("Suspended for QC", f"Job {result.job_id} suspended (checkpoint: {result.checkpoint}).")
            self.root.after(0, self._finish, info, None)
        else:
            info = ("Done", f"Job {result.job_id} done — results written.")
            self.root.after(0, self._finish, info, None)

    def _finish(self, info, error):
        """Runs back on the main thread: stop progress, re-enable button, show result."""
        self._progress.stop()
        self._run_btn.config(state="normal")
        if error:
            self._set_status("Error")
            messagebox.showerror("Error", error)
        else:
            title, msg = info
            self._set_status(title)
            messagebox.showinfo(title, msg)

class SectionForm:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="Section", padding=8)

        self._build_ui()
        self._load_defaults()

    def _browse_dir(self, entry):
        """Open a folder picker and fill the given entry with the chosen path."""
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def _build_ui(self):
        """Create and place widgets in the window."""

        self.frame.pack(fill=tk.X, padx=8, pady=4)
        self.frame.columnconfigure(1, weight=1)

        row = 0

        def add_entry(label_text, values=None, browse=False):
            """Add one Label+Entry row, return the Entry widget."""
            nonlocal row
            tk.Label(self.frame, text=label_text).grid(row=row, column=0, sticky="w")
            entry = ttk.Combobox(self.frame, values=values)
            entry.grid(row=row, column=1, sticky="ew")
            if browse:
                tk.Button(
                    self.frame, text="Browse",
                    command=lambda e=entry: self._browse_dir(e),
                ).grid(row=row, column=2, padx=(4, 0))
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
        self.source_dir_entry = add_entry("Source directory", browse=True)
        self.method_entry = add_entry("Method", list(methods_registry.list_methods().keys()))
        self.acquisition_id_entry = add_entry("Acquisition ID (segment:side:acquisition)")
        self.output_dir_entry = add_entry("Output directory", browse=True)
        self.series_entry = add_entry("Series")
        self.date_entry = add_entry("Date")
        self.qc_mode_entry = add_entry("Quality check mode", ["off","checkpoint","global"])
        self.seg_series_entry = add_entry("Segmentation series")
        self.action_entry = add_entry("Action", ["global-swap"])

        self.debug_var = add_checkbox("Debug")
        self.open_qc_var = add_checkbox("Open QC folder")
        self.multicenter_var = add_checkbox("Multicenter")

    def _load_defaults(self):
        """Pre-fill the fields with default data."""
        self.qc_mode_entry.insert(0, "off")


if __name__ == "__main__":
    app = MainApp()
    app.root.mainloop()
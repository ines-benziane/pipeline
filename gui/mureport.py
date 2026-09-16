"""
gui/mureport.py
Mureport main window. 
"""

import json
import shutil
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path

from adapters.dummy_exam_catalog import DummyExamCatalog
from runner.errors import PipelineError
from runner.parsing import parse_acquisition, parse_method, parse_series
from runner.pipeline import run_pipeline
from runner import methods_registry
from runner import progress
from methods.dixon3pt import Dixon3ptMethod
from methods.t2map_3exp import T2Map3ExpMethod

from sections import SectionForm


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
        progress.set_listener(lambda text, level: self._set_status(text))

        self.root.option_add("*Font", ("Helvetica", 14))
        ttk.Style().configure(".", font=("Helvetica", 14))

        self._build_header()
        self.sections.append(SectionForm(parent=self.root))
        self._build_footer()


    def _build_header(self):
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

    def _build_footer(self):
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


    def _validate(self, section):
        """Return an error string if required fields are missing, else None."""
        #TO DO : when implemented, searching by date and name only makes exam-id not required anymore
        required = {
            "Exam ID": section.exam_id_entry,
            "Source directory": section.source_dir_entry,
            "Method": section.method_entry,
            "Acquisition ID": section.acquisition_id_entry,
            "Output directory": section.output_dir_entry,
            "Series": section.series_entry
        }
        missing = [label for label, entry in required.items() if not entry.get().strip()]
        if missing:
            return "Missing fields : " + ", ".join(missing)
        return None

    def _on_manage(self):
        """Read section 0's fields (main thread), then hand off to a worker thread."""
        section = self.sections[0]
        error = self._validate(section)
        if error:
            self._set_status(error)
            return
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


if __name__ == "__main__":
    app = MainApp()
    app.root.mainloop()
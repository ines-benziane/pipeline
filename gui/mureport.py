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
from widgets import make_shadow_button


methods_registry.register(Dixon3ptMethod)
methods_registry.register(T2Map3ExpMethod)

PRIMARY = "#2c3e50"
BG = "#f5f6f8"

class MainApp():
    """Gathered all section forms and call run_pipeline for each of them"""

    def __init__(self):
        #Create main window
        self.root = tk.Tk()
        style = ttk.Style()
        style.theme_use("clam")
        self.root.configure(bg=BG)
        style.configure("TLabelframe", background=BG, bordercolor=PRIMARY)
        style.configure("TLabelframe.Label", foreground=PRIMARY, font=("Helvetica", 12, "bold"))
        style.configure("Accent.Horizontal.TProgressbar", background=PRIMARY, troughcolor=BG)
        style.configure("Running.TLabelframe", background=BG, bordercolor="#0589c2")
        style.configure("Running.TLabelframe.Label", foreground="#0589c2", font=("Helvetica", 12, "bold"))
        style.configure("Done.TLabelframe", background=BG, bordercolor="#27ae60")
        style.configure("Done.TLabelframe.Label", foreground="#27ae60", font=("Helvetica", 12, "bold"))
        style.configure("Error.TLabelframe", background=BG, bordercolor="#c0392b")
        style.configure("Error.TLabelframe.Label", foreground="#c0392b", font=("Helvetica", 12, "bold"))
        self.root.title("MuReport")
        self.root.geometry("1500x1000")
        self.root.resizable(True, True)
        self.sections = []
        self._current_section_label = ""
        progress.set_listener(self._on_announce)


        self.root.option_add("*Font", ("Helvetica", 14))
        ttk.Style().configure(".", font=("Helvetica", 14))

        self._build_header()
        self.sections_frame = tk.Frame(self.root, bg=BG)
        self.sections_frame.pack(fill=tk.X)
        self._add_section()
        self._add_section_btn = tk.Button(
            self.root, text="+ Add section",
            command=self._add_section,
            bg="#e4e6e9", fg=PRIMARY, relief="flat",
        )
        self._add_section_btn.pack(pady=(0,6))
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

    def _add_section(self):
        """Create a new SectionForm inside sections_frame and track it"""
        section = SectionForm(
            parent=self.sections_frame, on_delete=self._remove_section,
            default_name=f"Section {len(self.sections) + 1}",
        )
        self.sections.append(section)

    def _remove_section(self, section):
        """Destroy a section's widgets and stop tracking it. Always keep at least one."""
        if len(self.sections) <= 1:
            self._set_status("You must keep at least one section.")
            return
        section.wrapper.destroy()
        self.sections.remove(section)

    def _build_footer(self):
        prog_frame = tk.Frame(self.root)
        prog_frame.pack(fill=tk.X, padx=10, pady=(4, 2))
        self._progress = ttk.Progressbar(
            prog_frame, mode="indeterminate", maximum=100,
            style="Accent.Horizontal.TProgressbar",
        )
        self._progress.pack(fill=tk.X)

        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(self.root, textvariable=self._status_var, anchor="w").pack(fill=tk.X, padx=10, pady=(0, 6))

        run_container, self._run_btn = make_shadow_button(
            self.root, "Run", self._on_manage,
            bg=PRIMARY, fg="white", active_bg="#1a252f", width=22,
        )
        run_container.pack(pady=(0, 8))

    def _set_status(self, text: str):
        """Update the status label (thread-safe)."""
        self.root.after(0, lambda: self._status_var.set(text))

    def _on_announce(self, text, level):
        """progress.announce() listener: prefix pipeline step names with the current section."""
        prefix = f"{self._current_section_label} - " if self._current_section_label else ""
        self._set_status(prefix + text)

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
        missing = [label for label, entry in required.items() if not section.get_value(entry)]
        if missing:
            return "Missing fields : " + ", ".join(missing)
        return None

    def _validate_all(self):
        """Validate every section before running anything. Return an error string, or None"""
        for section in self.sections:
            error = self._validate(section)
            if error:
                return f"{section.display_name()}: {error}"

    def _build_kwargs(self, section):
        """Read one section's fields into run_pipeline kwargs."""
        return dict(
                        source_dir=section.source_dir_entry.get().strip(),
            acquisition_id=parse_acquisition(section.get_value(section.acquisition_id_entry)),
            method=parse_method(section.method_entry.get().strip()),
            output_dir=section.output_dir_entry.get().strip(),
            series=parse_series(section.series_entry.get().strip()),
            qc=section.qc_mode_entry.get().strip() or "global",
            exam_id=section.exam_id_entry.get().strip() or None,
            exam_date=section.date_entry.get().strip() or None,
            debug=section.debug_var.get(),
            action=section.action_entry.get().strip() or None,
            multicenter=section.multicenter_var.get(),
            seg_series=parse_series(section.seg_series_entry.get().strip()),
        )

    def _on_manage(self):
        """Validate every section (main thread), then run them all sequentially in a worker thread."""
        error = self._validate_all()
        if error:
            self._set_status(error)
            return

        self._run_btn.config(state="disabled")
        self._add_section_btn.config(state="disabled")
        self._progress.start()
        threading.Thread(target=self._run_all, daemon=True).start()

    def _run_all(self):
        """Runs off the main thread: executes every section's pipeline, in order."""
        total = len(self.sections)
        for i, section in enumerate(self.sections, start=1):
            self._current_section_label = f"Section {i}/{total} ({section.display_name()})"
            self.root.after(0, section.set_status, "running")
            try:
                kwargs = self._build_kwargs(section)
                result = run_pipeline(catalog=DummyExamCatalog(), **kwargs)
            except PipelineError as exc:
                self.root.after(0, section.set_status, "error")
                self.root.after(0, self._finish, str(exc))
                return
            except Exception as exc:
                self.root.after(0, section.set_status, "error")
                self.root.after(0, self._finish, f"{type(exc).__name__}: {exc}")
                raise

            # TODO: "suspended" (QC checkpoint) gets the "error" color for now — it isn't a
            # failure, but there's no GUI resume flow yet, so it needs attention just like one.
            if result.status == "suspended":
                self.root.after(0, section.set_status, "error")
            else:
                self.root.after(0, section.set_status, "done")

        self.root.after(0, self._finish, None)

    def _finish(self, error):
        """Runs back on the main thread: stop progress, re-enable button, report the outcome."""
        self._progress.stop()
        self._run_btn.config(state="normal")
        self._add_section_btn.config(state="normal")
        self._current_section_label = ""
        if error:
            self._set_status("Error — see message")
            messagebox.showerror("Error", error)
        else:
            self._set_status("All sections done.")


if __name__ == "__main__":
    app = MainApp()
    app.root.mainloop()
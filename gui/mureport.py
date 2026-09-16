"""
gui/mureport.py
Mureport main window.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from runner import methods_registry
from methods.dixon3pt import Dixon3ptMethod
from methods.t2map_3exp import T2Map3ExpMethod

from sections import SectionForm
from session import ReportSession
from widgets import make_shadow_button


methods_registry.register(Dixon3ptMethod)
methods_registry.register(T2Map3ExpMethod)

PRIMARY = "#2c3e50"
BG = "#f5f6f8"

class MainApp():
    """Builds the window, wires user actions to a ReportSession, reflects its callbacks."""

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

        self.session = ReportSession(
            on_progress=self._set_status,
            on_section_status=lambda section, status: self.root.after(0, section.set_status, status),
            on_done=lambda error: self.root.after(0, self._finish, error),
            on_report_done=lambda error, pdf_path: self.root.after(0, self._finish_report, error, pdf_path),
        )

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
        self._add_section_btn.pack(pady=(0, 6))
        self._build_footer()

    def _build_header(self):
        """Create and place widgets in the window."""

        #Header
        header = tk.Frame(self.root, bg="#2c3e50", pady=8)
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

        report_frame = tk.Frame(self.root, bg=BG)
        report_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        tk.Label(report_frame, text="Report output directory", bg=BG).pack(side=tk.LEFT)
        self._report_dir_entry = tk.Entry(report_frame, width=40)
        self._report_dir_entry.pack(side=tk.LEFT, padx=(6, 4))
        tk.Button(
            report_frame, text="Browse", command=self._browse_report_dir,
            bg="#e4e6e9", fg=PRIMARY, relief="flat",
        ).pack(side=tk.LEFT)

        report_container, self._report_btn = make_shadow_button(
            self.root, "Generate report", self._on_generate_report,
            bg=PRIMARY, fg="white", active_bg="#1a252f", width=22,
        )
        report_container.pack(pady=(0, 8))
        self._report_btn.config(state="disabled")

    def _set_status(self, text: str):
        """Update the status label (thread-safe)."""
        self.root.after(0, lambda: self._status_var.set(text))

    def _browse_report_dir(self):
        """Open a folder picker and fill the report output directory field."""
        path = filedialog.askdirectory()
        if path:
            self._report_dir_entry.delete(0, tk.END)
            self._report_dir_entry.insert(0, path)

    def _on_manage(self):
        """Validate every section (main thread), then run them all via the session."""
        error = self.session.validate_all(self.sections)
        if error:
            self._set_status(error)
            return

        self._run_btn.config(state="disabled")
        self._add_section_btn.config(state="disabled")
        self._progress.start()
        self.session.run_all(self.sections)

    def _finish(self, error):
        """Runs back on the main thread: stop progress, re-enable buttons, report the outcome."""
        self._progress.stop()
        self._run_btn.config(state="normal")
        self._add_section_btn.config(state="normal")
        if error:
            self._set_status("Error — see message")
            messagebox.showerror("Error", error)
        else:
            self._set_status("All sections done.")
            self._report_btn.config(state="normal")

    def _on_generate_report(self):
        """Validate exam_id + report dir (main thread), then generate the report via the session."""
        exam_id = self.session.shared_exam_id(self.sections)
        if not exam_id:
            self._set_status("All sections must share the same Exam ID to generate a report.")
            return
        report_dir = self._report_dir_entry.get().strip()
        if not report_dir:
            self._set_status("Missing field: Report output directory")
            return

        self._report_btn.config(state="disabled")
        self._run_btn.config(state="disabled")
        self._add_section_btn.config(state="disabled")
        self._set_status("Generating report...")
        self._progress.start()
        self.session.generate_report(exam_id, report_dir)

    def _finish_report(self, error, pdf_path):
        """Runs back on the main thread: stop progress, re-enable buttons, report the outcome."""
        self._progress.stop()
        self._run_btn.config(state="normal")
        self._add_section_btn.config(state="normal")
        self._report_btn.config(state="normal")
        if error:
            self._set_status("Error — see message")
            messagebox.showerror("Error", error)
        else:
            self._set_status(f"Report generated: {pdf_path}")


if __name__ == "__main__":
    app = MainApp()
    app.root.mainloop()

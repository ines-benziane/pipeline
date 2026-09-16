import tkinter as tk 
from tkinter import ttk, filedialog

from runner import methods_registry

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
        self.frame.columnconfigure(1)

        row = 0

        def add_entry(label_text, values=None, browse=False):
            """Add one Label+Entry row, return the Entry widget."""
            nonlocal row
            tk.Label(self.frame, text=label_text).grid(row=row, column=0, sticky="w")
            if values:
                entry = ttk.Combobox(self.frame, values=values, width="30")
            else:
                entry = tk.Entry(self.frame, width="30")
            entry.grid(row=row, column=1, sticky="w")
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

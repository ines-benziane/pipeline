import tkinter as tk 
from tkinter import ttk, filedialog

from runner import methods_registry
from widgets import make_shadow_button

class SectionForm:
    def __init__(self, parent, on_delete=None):
        # wrapper: a plain frame holding the section box + the delete button as SIBLINGS,
        # so the button can float outside the box's border (a child can never be
        # positioned outside its own parent's bounds — it gets clipped).
        self.wrapper = tk.Frame(parent, bg=parent.cget("bg"))
        self.wrapper.pack(fill=tk.X, padx=8, pady=4)

        self.frame = ttk.LabelFrame(self.wrapper, text="Section", padding=8, style="TLabelframe")
        self.frame.pack(fill=tk.X, pady=(12, 0))
        self.on_delete = on_delete

        self._build_ui()
        self._load_defaults()
        self._build_delete_button()

    def _build_delete_button(self):
        """Small X button, floating above the section box's top-right corner, outside it."""
        if self.on_delete is None:
            return
        tk.Button(
            self.wrapper, text="✕", command=lambda: self.on_delete(self),
            bg=self.wrapper.cget("bg"), fg="#c0392b", relief="flat", bd=0,
        ).place(relx=1.0, x=0, y=0, anchor="ne")

    def _browse_dir(self, entry):
        """Open a folder picker and fill the given entry with the chosen path."""
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def _add_placeholder(self, entry, text):
        """Show `text` in grey until the user types something (Tkinter has no native placeholder)."""
        entry.placeholder = text
        entry.insert(0, text)
        entry.config(fg="grey")

        def on_focus_in(event):
            if entry.get() == text and str(entry.cget("fg")) == "grey":
                entry.delete(0, tk.END)
                entry.config(fg="black")

        def on_focus_out(event):
            if not entry.get():
                entry.insert(0, text)
                entry.config(fg="grey")

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def get_value(self, entry):
        """Read an entry's text, treating an untouched placeholder as empty."""
        text = entry.get().strip()
        if text == getattr(entry, "placeholder", None):
            return ""
        return text

    def _build_ui(self):
        """Create and place widgets in the window."""

        columns_frame = tk.Frame(self.frame)
        columns_frame.pack()
        columns = [tk.Frame(columns_frame) for _ in range(3)]
        for col in columns:
            col.pack(side=tk.LEFT, anchor="n", padx=(0, 20))
            col.columnconfigure(1, minsize=130)
        rows = [0, 0, 0]

        def add_entry(col_index, label_text, values=None, browse=False):
            """Add one Label+Entry row, return the Entry widget."""
            frame = columns[col_index]
            row = rows[col_index]

            tk.Label(frame, text=label_text).grid(row=row, column=0, sticky="w", pady=3)
            if values:
                entry = ttk.Combobox(frame, values=values)
            else:
                entry = tk.Entry(frame)
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            if browse:
                browse_container, _ = make_shadow_button(
                    frame, "Browse", (lambda e=entry: self._browse_dir(e)),
                    bg="#e4e6e9", fg="#2c3e50", active_bg="#d3d6da",
                )
                browse_container.grid(row=row, column=2, padx=(7, 0), pady=3)
            rows[col_index] += 1
            return entry

        def add_checkbox(col_index, label_text):
            """Add one Checkbutton row, return its BooleanVar."""
            frame = columns[col_index]
            row = rows[col_index]
            var = tk.BooleanVar(value=False)
            tk.Checkbutton(frame, text=label_text, variable=var).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=3
            )
            rows[col_index] += 1
            return var

        self.exam_id_entry = add_entry(0, "Exam ID")
        self.source_dir_entry = add_entry(0, "Source directory", browse=True)
        self.method_entry = add_entry(0, "Method", list(methods_registry.list_methods().keys()))
        self.acquisition_id_entry = add_entry(0, "Acquisition ID")
        self._add_placeholder(self.acquisition_id_entry, "segment:side:acquisition")

        self.output_dir_entry = add_entry(1, "Output directory", browse=True)
        self.series_entry = add_entry(1, "Series")
        self.date_entry = add_entry(1, "Date")
        self.qc_mode_entry = add_entry(1, "Quality check mode", ["off","checkpoint","global"])

        self.seg_series_entry = add_entry(2, "Segmentation series")
        self.action_entry = add_entry(2, "Action", ["global-swap"])
        self.debug_var = add_checkbox(2, "Debug")
        self.open_qc_var = add_checkbox(2, "Open QC folder")
        self.multicenter_var = add_checkbox(2, "Multicenter")

    def _load_defaults(self):
        """Pre-fill the fields with default data."""
        self.qc_mode_entry.insert(0, "global")

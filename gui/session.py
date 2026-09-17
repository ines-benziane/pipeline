"""
gui/session.py
Orchestrates running sections' pipelines and generating the report.
"""

import threading

from adapters.dummy_exam_catalog import DummyExamCatalog
from adapters.medical_report_generator import MedicalReportGenerator
from runner import progress
from runner.errors import PipelineError
from runner.job_runner import RESULT_DIR
from runner.pipeline import run_pipeline


class ReportSession:
    def __init__(self, on_progress, on_section_status, on_done, on_report_done):
        self.on_progress = on_progress
        self.on_section_status = on_section_status
        self.on_done = on_done
        self.on_report_done = on_report_done
        self._current_section_label = ""
        self._successful_sections = []
        progress.set_listener(self._on_announce)

    def _on_announce(self, text, level):
        """progress.announce() listener: prefix pipeline step names with the current section."""
        prefix = f"{self._current_section_label} - " if self._current_section_label else ""
        self.on_progress(prefix + text)

    def validate_all(self, sections):
        """Validate every section before running anything. Return an error string, or None."""
        for section in sections:
            error = section.validate()
            if error:
                return f"{section.display_name()}: {error}"
        return None

    def shared_exam_id(self, sections):
        """Return the exam_id shared by every section, or None if they differ or are empty."""
        exam_ids = {section.exam_id() for section in sections}
        if len(exam_ids) == 1 and next(iter(exam_ids)):
            return next(iter(exam_ids))
        return None

    def run_all(self, sections):
        """Kick off _run_all_sync in a background thread."""
        threading.Thread(target=self._run_all_sync, args=(sections,), daemon=True).start()

    def _run_all_sync(self, sections):
        self._successful_sections = []
        total = len(sections)
        for i, section in enumerate(sections, start=1):
            self._current_section_label = f"Section {i}/{total} ({section.display_name()})"
            self.on_section_status(section, "running")
            try:
                kwargs = section.to_kwargs()
                result = run_pipeline(catalog=DummyExamCatalog(), **kwargs)
            except PipelineError as exc:
                self.on_section_status(section, "error")
                self._current_section_label = ""
                self.on_done(str(exc))
                return
            except Exception as exc:
                self.on_section_status(section, "error")
                self._current_section_label = ""
                self.on_done(f"{type(exc).__name__}: {exc}")
                raise

            # TO DO: "suspended" (QC checkpoint) gets the "error" color for now — it isn't a
            # failure, but there's no GUI resume flow yet, so it needs attention just like one.
            if result.status == "suspended":
                self.on_section_status(section, "error")
            else:
                self.on_section_status(section, "done")
                self._successful_sections.append(section)

        self._current_section_label = ""
        self.on_done(None)

    def generate_report(self, exam_id, report_dir):
        """Kick off _generate_report_sync in a background thread."""
        threading.Thread(target=self._generate_report_sync, args=(exam_id, report_dir), daemon=True).start()

    def _generate_report_sync(self, exam_id, report_dir):
        config = {"section": [section.config_entry() for section in self._successful_sections]}
        try:
            pdf_path = MedicalReportGenerator().generate(
                [exam_id], RESULT_DIR, report_dir, lang="en", config=config,
            )
        except Exception as exc:
            self.on_report_done(f"{type(exc).__name__}: {exc}", None)
            raise
        self.on_report_done(None, pdf_path)

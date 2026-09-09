"""Exception spine for the pipeline.

`PipelineError` is for every *expected* failure: a bad exam id,
missing results, an unparseable DICOM series.

"""


class PipelineError(Exception):
    """Base class for all expected pipeline failures.

    Args:
        message: technical, developer-facing description of what failed.
        hint: optional user-facing next step, e.g. "relaunch with --exam-id".
              Shown by the CLI barrier on its own line; never part of `str(e)`.
    """

    def __init__(self, message: str, *, hint: str | None =None):
        super().__init__(message)
        self.hint = hint


class MethodNotFoundError(PipelineError):
    """No method is registered under the requested name."""
    def __init__(self, method_name):
        super().__init__(f"Unknown method {method_name!r}", hint="run: pipeline show-methods")
        self.method_name = method_name


class JobNotFoundError(PipelineError):
    """No stored job matches the requested id."""
    def __init__(self, job_id):
        super().__init__(f"Unknown job {job_id!r}")
        self.job_id = job_id


class MethodError(PipelineError):
    """Base class for failures inside a processing method (mutools / museg-ai)."""


class DicomSelectionError(MethodError):
    """The selected DICOM series are missing or not usable by the method."""


class DixonReconstructionError(MethodError):
    """The Dixon fat/water reconstruction failed on otherwise valid input."""

class T2MappingError(MethodError):
    """The T2 mapping reconstruction failed"""

class SegmentationError(MethodError):
    """The segmentation model failed to produce ROIs."""


class UnknownSegmentError(MethodError):
    """The requested segment has no configured model."""
    def __init__(self, segment, available):
        super().__init__(
            f"Unknown segment {segment!r}",
            hint=f"expected one of: {', '.join(sorted(available))}",
        )
        self.segment = segment


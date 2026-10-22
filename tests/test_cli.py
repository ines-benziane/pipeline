"""Command line (cli/main.py): options reach the pipeline, outcomes and errors are reported cleanly."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from cli import main as cli_main
from runner.pipeline import PipelineOutcome

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def run():
    runner = CliRunner()
    return lambda *args: runner.invoke(cli_main.cli, list(args))


@pytest.fixture
def captured(monkeypatch):
    """Replace run_pipeline: record what the CLI passes, return a 'done' outcome."""
    calls = {}

    def fake_run_pipeline(**kwargs):
        calls.update(kwargs)
        return PipelineOutcome(exam_id=kwargs["exam_id"], status="done", job_id="JOB1")

    monkeypatch.setattr(cli_main, "run_pipeline", fake_run_pipeline)
    return calls


PROCESS = ["process", "-e", "EXAM001", "-sd", "dicoms", "-m", "t2map_3exp:fixed_fat=1",
           "-a", "thighs:L:1.0", "-od", "out", "-s", "13,14"]


def test_show_methods_lists_production_methods(run):
    result = run("show-methods")

    assert result.exit_code == 0
    assert "dixon3pt 1.0" in result.output and "t2map_3exp 1.0" in result.output


def test_process_passes_parsed_options_to_the_pipeline(run, captured):
    result = run(*PROCESS, "-ss", "8,9", "-da", "2026-01-12", "-qc-mode", "global",
                 "-qc-dir", "qc", "-act", "global-swap", "-mc", "-d")

    assert result.exit_code == 0, result.output
    assert captured["exam_id"] == "EXAM001"
    assert captured["source_dir"] == "dicoms"
    assert captured["method"] == ("t2map_3exp", {"fixed_fat": "1"})
    assert captured["acquisition_id"] == {"1.0": {"thighs": "L"}}
    assert captured["output_dir"] == "out"
    assert captured["series"] == [13, 14]
    assert captured["seg_series"] == [8, 9]
    assert captured["exam_date"] == "2026-01-12"
    assert (captured["qc"], captured["qc_dir"]) == ("global", "qc")
    assert (captured["action"], captured["multicenter"], captured["debug"]) == ("global-swap", True, True)


def test_process_defaults(run, captured):
    run(*PROCESS)

    assert (captured["qc"], captured["seg_series"], captured["action"], captured["debug"]) == ("off", None, None, False)


@pytest.mark.parametrize("missing", ["-e", "-sd", "-m", "-a", "-od", "-s"])
def test_process_refuses_missing_required_option(run, captured, missing):
    """FONC-001 (command line side): a missing mandatory field blocks the run and is named."""
    i = PROCESS.index(missing)
    result = run(*(PROCESS[:i] + PROCESS[i + 2:]))

    assert result.exit_code == 2
    assert "Missing option" in result.output
    assert captured == {}


def test_process_reports_done(run, captured):
    assert "Job JOB1 done" in run(*PROCESS).output


def test_process_reports_qc_suspension(run, monkeypatch):
    monkeypatch.setattr(cli_main, "run_pipeline", lambda **kw: PipelineOutcome(
        exam_id="EXAM001", status="suspended", job_id="JOB1", checkpoint="mutools"))

    assert "Job JOB1 suspended for QC review (checkpoint: mutools)" in run(*PROCESS).output


def test_pipeline_error_gives_message_and_hint_exit_1(run, isolated_store):
    result = run("resume", "-f", "no-such-job", "-dec", "yes", "-od", "out")

    assert result.exit_code == 1
    assert "Unknown job 'no-such-job'" in result.output


@pytest.mark.xfail(strict=True, reason="A malformed --series (user input) ends as 'Internal error' (exit 2) "
                                       "instead of a clear input error (exit 1 + hint). To decide.")
def test_malformed_series_is_reported_as_an_input_error(run, captured):
    i = PROCESS.index("-s")
    result = run(*(PROCESS[:i] + ["-s", "13,abc"] + PROCESS[i + 2:]))

    assert result.exit_code == 1
    assert "13,abc" in result.output


@pytest.mark.xfail(strict=True, reason="A non-existent DICOM folder ends as 'Internal error' (exit 2, "
                                       "FileNotFoundError) instead of a clear input error. To decide (VAL-002c).")
def test_missing_source_folder_is_reported_as_an_input_error(run, isolated_store, tmp_path):
    result = run("process", "-e", "EXAM001", "-sd", str(tmp_path / "nowhere"), "-m", "dummy",
                 "-a", "legs::1.0", "-od", str(tmp_path / "out"), "-s", "17,18")

    assert result.exit_code == 1
    assert "nowhere" in result.output


def test_process_end_to_end_with_dummy_method(run, isolated_store, tmp_path):
    """Integration: CLI -> pipeline -> job -> method -> result file, nothing mocked but the method."""
    (tmp_path / "dicoms").mkdir()
    result = run("process", "-e", "EXAM001", "-sd", str(tmp_path / "dicoms"), "-m", "dummy",
                 "-a", "legs::1.0", "-od", str(tmp_path / "out"), "-s", "17,18")

    assert result.exit_code == 0, result.output
    assert "done" in result.output
    assert any(isolated_store.glob("EXAM001_*.json"))


def test_report_generates_the_pdf(run, tmp_path):
    """Integration: CLI 'report' -> medical_report -> PDF, with the default report config."""
    result = run("report", "--exam-id", "E2E001", "--data-dir", str(FIXTURES / "report"),
                 "--output-dir", str(tmp_path), "--lang", "fr")

    assert result.exit_code == 0, result.output
    assert (tmp_path / "Medical_report.pdf").read_bytes()[:5] == b"%PDF-"


def test_report_for_unknown_exam_is_a_clean_error(run, tmp_path):
    result = run("report", "--exam-id", "NOPE", "--data-dir", str(FIXTURES / "report"),
                 "--output-dir", str(tmp_path))

    assert result.exit_code == 1
    assert "Error:" in result.output

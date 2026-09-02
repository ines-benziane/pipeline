### TO DO : batch sur plusieurs examens

import functools
import json
import logging
import sys

import click

from pathlib import Path
from adapters.medical_report_generator import MedicalReportGenerator
from methods.dummy import DummyMethod
from methods.dixon3pt import Dixon3ptMethod

from runner import methods_registry
from runner.errors import PipelineError
from runner.job import Job, JobState
from runner.job_runner import run_job
from runner.exam_retriever import DeidentificationMode
from runner.pipeline import run_pipeline
from runner.resume import resume_pipeline

from adapters.dummy_exam_catalog import DummyExamCatalog
from adapters.dummy_exam_retriever import DummyExamRetriever
from adapters.file_result_index import FileResultIndex


methods_registry.register(DummyMethod)
methods_registry.register(Dixon3ptMethod)

log = logging.getLogger(__name__)


def cli_barrier(func):
    """Single error boundary for a CLI command.

    PipelineError     -> clean message (+ cause + hint) on stderr, exit 1. No traceback.
    KeyboardInterrupt -> exit 130.
    anything else      -> full traceback via logging, terse message, exit 2.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PipelineError as e:
            click.echo(f"Error: {e}", err=True)
            if e.__cause__:
                click.echo(f"  caused by: {e.__cause__}", err=True)
            if e.hint:
                click.echo(f"  hint: {e.hint}", err=True)
            sys.exit(1)
        except KeyboardInterrupt:
            sys.exit(130)
        except Exception:
            log.exception("unexpected error in '%s'", func.__name__)
            click.echo("Internal error - see the traceback above.", err=True)
            sys.exit(2)
    return wrapper


@click.group()
def cli():
    """MRI Pipeline - Study processing and report generation"""

@cli.command()
@cli_barrier
def show_methods():
    """Lists available methods."""
    for name, cls in methods_registry.list_methods().items():
        click.echo(f"{name} {cls.version}")


# @cli.command()
# @click.option("--exam-id", required=True, help="Identifiant de l'examen.")
# @click.option("--method", required=True, help="Nom de la méthode (voir: pipeline show-methods).")
# @click.option("--segment", multiple=True,
#               help="Segment à traiter. Répétable. Défaut: legs et thighs.")
# @click.option("--dry-run", is_flag=True, help="Montre ce qui serait fait, sans rien créer.")
# @cli_barrier
# def apply_method(exam_id, method, segment, dry_run):
#     """Applies a method on a study, creates corresponding job (task) for tracking."""
#     segments = list(segment) if segment else ["legs", "thighs"]

#     if dry_run:
#         click.echo(f"{len(segments)} job(s) seraient créés :")
#         for seg in segments:
#             click.echo(f"  {exam_id}  {seg}  {method}")
#         return

#     for seg in segments:
#         job = Job(exam_id=exam_id, segment=seg, method_id=method)
#         try:
#             run_job(job)
#         except PipelineError as e:
#             click.echo(f"{job.job_id}  {seg}  FAILED: {e}", err=True)
#             if e.hint:
#                 click.echo(f"{job.job_id}  {seg}  hint: {e.hint}", err=True)
#             continue
#         click.echo(f"{job.job_id}  {seg}  {job.state.value}")


@cli.command()
@click.option("--exam-id", required=True, help="Identifiant de l'examen.")
@click.option("--data-dir", required=True, help="Dossier des résultats JSON (json_output).")
@click.option("--output-dir", required=True, help="Dossier de sortie du rapport PDF.")
@click.option("--lang", default="en", help="Langue du rapport.")
@cli_barrier
def report(exam_id, data_dir, output_dir, lang):
    """Generates report from already processed data. """
    generator = MedicalReportGenerator()
    pdf_path = generator.generate([exam_id], data_dir, output_dir, lang=lang)
    click.echo(str(pdf_path))


@cli.command()
@click.option("--exam-id", "-id", required=True, help="Exam of interest")
@click.option("--show-series", "-s", is_flag=True, help="Show the series of this exam")
@click.option("--related-exams", "-r", is_flag=True, help="Show the others exams related to the one of interst")
@cli_barrier
def exams(exam_id, show_series, related_exams):
    """Show information about an exam."""
    dummy = DummyExamCatalog()
    if show_series:
        for series in dummy.show_series(exam_id):
            click.echo(f"{series.series_id}  {series.description}")

    elif related_exams:
        for related in dummy.find_related_exams(exam_id):
            click.echo(f"{related.exam_id}  {related.patient_name}  {related.exam_date}")
    else :
        click.echo("Precise if you want to see this exam's series (--show-series) or the exams related (--related_exams).")

@cli.command()
@click.option("--exam-id", "-id", required=True, help="Exam of interest")
@click.option ("--dest-dir", "-dir", required=True, help="Directory for retrieved dicoms")
@click.option("--mode", "-m", type=click.Choice([m.value for m in DeidentificationMode]), required=True)
@click.option("--source-dir", "-sdir", required=True, help="Where the dummy takes the dicoms")
@cli_barrier
def retrieve(exam_id, dest_dir, mode, source_dir):
    """Retrieves an exam, de-identifies it and store it in destination directory"""
    dummy = DummyExamRetriever(source_dir)
    click.echo(dummy.retrieve_exam(exam_id, dest_dir, mode=DeidentificationMode(mode)))

### TO DO : batch sur plusieurs examens

def parse_series(series):
    if not series:
        return None
    series_numbers = [int(n) for n in series.split(",")]
    return series_numbers

def parse_acquisition(acquisition_id):
    if not acquisition_id:
        return None
    parts = acquisition_id.split(":")
    parts += [""] * (3 - len(parts))
    segment, side, acquisition,= parts[:3]
    side = side or None
    acquisition = acquisition or None
    return {acquisition: {segment: side}}

def parse_method(method_id):
    if not method_id:
        return None
    method_name, *params = method_id.split(":")
    return {method_name: params}

@cli.command()
@click.option("--exam-id", "-e", required=True)
@click.option("--source-dir", "-sd",  required=True, help="Folder with the dicom ")
@click.option("--method-id", "-m", required=True, help="method-id gathers the method's name and other optional parameters that might be needed by the method. Example : --method-name method_id:param1:param_2:param_3 ")
@click.option("--acquisition-id", "-a", required=True, help="Acquisition parameters.Usage: segment:side:acquisition")
@click.option("--output-dir", "-o", required=True, help="Fodler where the report will be stored.")
@click.option("--series", "-s", required=True, help="Acquisition parameters.Usage: --series 1,2,3")
# @click.option("--mode", type=click.Choice([m.value for m in DeidentificationMode]), required=True)
@click.option("--lang", "-l", default="en")
# @click.option("--with-antecedent", is_flag=True, help="Include patient's history in report.")
@click.option("--dev", "-d", is_flag=True, help="dev mode, detailed logging")
@click.option("--date", "-da", help="study date, optional, needed if the source directory has multiple studies. Ex : YYYY-MM-DD")
@click.option("--quality-check-mode", "-qc-mode", help="3 options : checkpoint, global or off. Checkpoint: there will be suspension at every step of the QC"
"Global: QC is done without suspension checkpoint. Off: no QC. Not given: QC off")
@click.option("--quality-check-dir", "-qc-dir", help="Indicates where the qc report has to go. If not given, dfault one is data/qc/job_id")
@click.option("--open-qc", "-oqc", is_flag=True, help="Opens QC folder")
@cli_barrier
def process(exam_id, source_dir, method_id, acquisition_id, output_dir, series, lang,  dev, date, quality_check_mode, quality_check_dir, open_qc):
    """from retrieval to one section of the report"""
    result = run_pipeline(
        # result_index=FileResultIndex(),
        report_generator=MedicalReportGenerator(),
        catalog=DummyExamCatalog(),
        # with_antecedent=with_antecedent,
        source_dir=source_dir,
        # mode=DeidentificationMode(mode),
        acquisition_id=parse_acquisition(acquisition_id),
        method_id=parse_method(method_id),
        output_dir=output_dir,
        series=parse_series(series),
        exam_id=exam_id,
        lang=lang,
        dev=dev,
        exam_date=date,
        qc=quality_check_mode  or "off",
        qc_dir=quality_check_dir
    )
    if result.status == "suspended":
        click.echo(f"Job {result.job_id} suspended for QC review (checkpoint: {result.checkpoint})")
        if open_qc and result.qc_dir:
            click.launch(str(result.qc_dir))
    else:
        click.echo(str(result.pdf_path))

@cli.command
@click.option("--job-file", "-f", required=True, help="The json file storing the job's data ")
@click.option("--decision_status", "-dec", required=True, help="Decision about the job. Continue, interrupt or apply specific functions.")
@click.option("--comment", "-com", help="User comment on the QC, will appear in the Medical report. Example: 'SAR muscle segmentation failed : must not take it into account' ")
@click.option("--tag", "-t", help="For common errors, use tag to caracterize it fastly. Must be in this list of tags : swap, muscle_off")
@click.option("--quality-check", "-qc", is_flag=True, help="If here, the rest of the process will include quality chek checkpoints")
@cli_barrier
def resume(job_file,  decision_status, quality_check, comment, tag):
    data = json.loads(Path(job_file).read_text(encoding="utf-8"))
    result = resume_pipeline(
        job_id=data["job_id"],
        decision_status=decision_status,
        state=data["state"],
        exam_id=data["exam_id"],
        segment=data["segment"],
        method_id=data["method_id"],
        workdir=data["workdir"],
        checkpoint=data["checkpoint"],
        qc=quality_check,
        source_dir=data["source_dir"],
        series=data["series"],
        tag=tag, 
        comment=comment
    )

    if result.state == JobState.SUSPENDED:
        click.echo(f"Job {result.job_id} suspended at checkpoint '{result.checkpoint}'")
    elif result.state == JobState.RESULTS_READY:
        click.echo(f"Job {result.job_id} finished — results ready.")
    else:
        click.echo(f"Job {result.job_id} state: {result.state.value}")
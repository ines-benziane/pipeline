### TO DO : batch sur plusieurs examens

import functools
import logging
import sys

import click

from adapters.medical_report_generator import MedicalReportGenerator
from methods.dummy import DummyMethod
from methods.dixon3pt import Dixon3ptMethod

from runner import methods_registry
from runner.errors import PipelineError
from runner.job import Job, JobState
from runner.job_runner import run_job, RESULT_DIR
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
@click.option("--output-dir", required=True, help="Dossier de sortie du rapport PDF.")
@click.option("--data-dir", help="Dossier des résultats JSON (json_output).")
@click.option("--lang", default="en", help="Langue du rapport.")
@cli_barrier
def report(exam_id, data_dir, output_dir, lang):
    """Generates report from already processed data. """
    generator = MedicalReportGenerator()
    pdf_path = generator.generate([exam_id], data_dir or RESULT_DIR, output_dir, lang=lang)
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
@click.option("--output-dir", "-od", required=True, help="Fodler where the files (medical report, qc report or else) will be stored.")
@click.option("--series", "-s", required=True, help="Acquisition parameters.Usage: --series 1,2,3")
# @click.option("--mode", type=click.Choice([m.value for m in DeidentificationMode]), required=True)
@click.option("--lang", "-l", default="en")
# @click.option("--with-antecedent", is_flag=True, help="Include patient's history in report.")
@click.option("--debug", "-d", is_flag=True, help="debug mode, detailed logging, saves data at every checkpoint.")
@click.option("--date", "-da", help="study date, optional, needed if the source directory has multiple studies. Ex : YYYY-MM-DD")
@click.option("--quality-check-mode", "-qc-mode", type=click.Choice(["off", "checkpoint", "global"]), default="off", help="3 options : checkpoint, global or off. Checkpoint: there will be suspension at every step of the QC"
"Global: QC is done without suspension checkpoint. Off: no QC. Not given: QC off")
@click.option("--quality-check-dir", "-qc-dir", help="Indicates where the qc report has to go. If not given, default one isoutput_dir")
@click.option("--open-qc", "-oqc", is_flag=True, help="Opens QC folder")
@cli_barrier
def process(exam_id, source_dir, method_id, acquisition_id, output_dir, series, lang,  debug, date, quality_check_mode, quality_check_dir, open_qc):
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
        debug=debug,
        exam_date=date,
        qc=quality_check_mode,
        qc_dir=quality_check_dir
    )
    if result.status == "suspended":
        click.echo(f"Job {result.job_id} suspended for QC review (checkpoint: {result.checkpoint})")
        if open_qc and result.qc_dir:
            click.launch(str(result.qc_dir))
    else:
        click.echo(str(result.pdf_path))

@cli.command()
@click.option("--job-id", "-f", required=True, help="Job to resume's ID")
@click.option("--decision_status", "-dec", required=True, type=click.Choice(["yes", "no", "pending"]), help="User verdict on the QC result.")
@click.option("--output-dir", "-od", required=True, help="Fodler where the files (medical report, qc report or else) will be stored.")
@click.option("--comment", "-com", help="User comment on the QC, will appear in the Medical report. Example: 'SAR muscle segmentation failed : must not take it into account' ")
@click.option("--tag", "-t", type=click.Choice(["swap", "muscle_off"]), help="Codified observation, for fast stats on recurring issues.")
@click.option("--quality-check", "-qc", is_flag=True, help="If here, the rest of the process will include quality chek checkpoints")
@click.option("--debug", "-d", is_flag=True, help="debug mode, detailed logging, saves data at every checkpoint.")
@click.option("--action", "-a", help="Launch method with this particular action. Actions are specific to the method. Example: --action global-swap")
@cli_barrier
def resume(job_id,  decision_status, output_dir, quality_check, comment, tag, debug, action):
    result = resume_pipeline(
        job_id=job_id,
        output_dir=output_dir,
        decision_status=decision_status,
        qc=quality_check,
        tag=tag,
        comment=comment,
        debug=debug,
        action=action,
    )

    if result.state == JobState.SUSPENDED:
        click.echo(f"Job {result.job_id} suspended at checkpoint '{result.checkpoint}'")
    elif result.state == JobState.RESULTS_READY:
        click.echo(f"Job {result.job_id} done — result saved. "
                   f"Run `pipeline report --exam-id {result.exam_id} --output-dir <dir>` to (re)generate the PDF.")
    else:
        click.echo(f"Job {result.job_id} state: {result.state.value}")
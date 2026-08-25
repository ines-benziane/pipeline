### TO DO : batch sur plusieurs examens

import sys

import click

from adapters.medical_report_generator import MedicalReportGenerator
from methods.dummy import DummyMethod
from methods.dixon3pt import Dixon3ptMethod
from runner import methods_registry
from runner.job import Job
from runner.report_generator import ReportGenerationError
from runner.job_runner import run_job

methods_registry.register(DummyMethod)
methods_registry.register(Dixon3ptMethod)

@click.group()
def cli():
    """MRI Pipeline - Study processing and report generation"""

@cli.command()
def show_methods():
    """Lists available methods."""
    for name, cls in methods_registry.list_methods().items():
        click.echo(f"{name} {cls.version}")


@cli.command()
@click.option("--exam-id", required=True, help="Identifiant de l'examen.")
@click.option("--method", required=True, help="Nom de la méthode (voir: pipeline show-methods).")
@click.option("--segment", multiple=True,
              help="Segment à traiter. Répétable. Défaut: legs et thighs.")
@click.option("--dry-run", is_flag=True, help="Montre ce qui serait fait, sans rien créer.")
def apply_method(exam_id, method, segment, dry_run):
    """Applies a method on a study, creates corresponding job (task) for tracking."""
    segments = list(segment) if segment else ["legs", "thighs"]

    if dry_run:
        click.echo(f"{len(segments)} job(s) seraient créés :")
        for seg in segments:
            click.echo(f"  {exam_id}  {seg}  {method}")
        return

    for seg in segments:
        job = Job(exam_id=exam_id, segment=seg, method_id=method)
        try:
            run_job(job)
        except Exception as e:
            click.echo(f"{job.job_id}  {seg}  Fail cmd run: {e}", err=True)
            continue
        click.echo(f"{job.job_id}  {seg}  {job.state.value}")


@cli.command()
@click.option("--exam-id", required=True, help="Identifiant de l'examen.")
@click.option("--data-dir", required=True, help="Dossier des résultats JSON (json_output).")
@click.option("--output-dir", required=True, help="Dossier de sortie du rapport PDF.")
@click.option("--lang", default="en", help="Langue du rapport.")
def report(exam_id, data_dir, output_dir, lang):
    """Generates report from already processed data. """
    generator = MedicalReportGenerator()
    try:
        pdf_path = generator.generate([exam_id], data_dir, output_dir, lang=lang)
    except ReportGenerationError as e:
        click.echo(f"Fail cmd report: {e}", err=True)
        sys.exit(1)
    click.echo(str(pdf_path))

from adapters.dummy_exam_catalog import DummyExamCatalog

@cli.command()
@click.option("--exam-id", "-id", required=True, help="Exam of interest")
@click.option("--show-series", "-s", is_flag=True, help="Show the series of this exam")
@click.option("--related-exams", "-r", is_flag=True, help="Show the others exams related to the one of interst")
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

from adapters.dummy_exam_retriever import DummyExamRetriever
from runner.exam_retriever import DeidentificationMode
from adapters.file_result_index import FileResultIndex
from runner.pipeline import run_pipeline

@cli.command()
@click.option("--exam-id", "-id", required=True, help="Exam of interest")
@click.optsource"--dest-dir", "-dir", required=True, help="Directory for retrieved dicoms")
@click.option("--mode", "-m", type=click.Choice([m.value for m in DeidentificationMode]), required=True)
@click.option("--source-dir", "-sdir", required=True, help="Where the dummy takes the dicoms")
def retrieve(exam_id, dest_dir, mode, source_dir):
    """Retrieves an exam, de-identifies it and store it in destination directory"""
    dummy = DummyExamRetriever(source_dir)
    click.echo(dummy.retrieve_exam(exam_id, dest_dir, mode=DeidentificationMode(mode)))

### TO DO : batch sur plusieurs examens

# def parse_series(series):
#     if not series:
#         return None
#     method, segment, series_str = series.split(":")
#     series_numbers = [int(n) for n in series_str.split(",")]
#     return {method: {segment: series_numbers}}

def parse_acquisition(acquisition_id):
    if not acquisition_id:
        return None
    acquisition, segment, side = acquisition_id.split(":")
    return {acquisition: {segment: side}}

def parse_method(method_id):
    if not method_id:
        return None
    method_name, *params = method_id.split(":")
    return {method_name: params}

@cli.command()
@click.option("--exam-id", required=True)
@click.option("--source-dir", required=True, help="Folder with the dicom ")
@click.option("--method-id", required=True, help="method-id gathers the method's name and parameters needed by the method. Example : --method-name method_id:param1:param_2:param_3 ")
@click.option("--acquisition-id", required=True, help="Acquisition parameters.Usage: acquisition:segment:side")
@click.option("--output-dir", required=True, help="Fodler where the report will be stored.")
@click.option("--series", required=True, help="Acquisition parameters.Usage: --series 1,2,3")
# @click.option("--mode", type=click.Choice([m.value for m in DeidentificationMode]), required=True)
@click.option("--lang", default="en")
# @click.option("--with-antecedent", is_flag=True, help="Inclure l'antécédent le plus récent dans le rapport.")
@click.option("--dev", "-d", is_flag=True, help="dev mode, detailed logging")
def process(exam_id, source_dir, method_id, acquisition_id, output_dir, series, lang,  dev):
    """Chaîne retrieve → apply-method → report, chemin heureux."""
    try:
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
            series=series,
            exam_id=exam_id,
            lang=lang,
            dev=dev,
        )
    except Exception as e:
        click.echo(f"Fail cmd process: {e}", err=True)
        sys.exit(1)
    click.echo(str(result["pdf_path"]))

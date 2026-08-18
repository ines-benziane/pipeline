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
    """Pipeline IRM - traitement d'examens et génération de rapports."""

@cli.command()
def methods():
    """Liste les méhodes disponibles."""
    for name, cls in methods_registry.list_methods().items():
        click.echo(f"{name} {cls.version}")


@cli.command()
@click.option("--exam-id", required=True, help="Identifiant de l'examen.")
@click.option("--method", required=True, help="Nom de la méthode (voir: pipeline methods).")
@click.option("--segment", multiple=True,
              help="Segment à traiter. Répétable. Défaut: legs et thighs.")
@click.option("--dry-run", is_flag=True, help="Montre ce qui serait fait, sans rien créer.")
def run(exam_id, method, segment, dry_run):
    """Lance un traitement sur un examen."""
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
    """Génère le rapport médical PDF d'un examen à partir des résultats déjà traités."""
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
    """Show informations about an exam."""
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
@click.option("--dest-dir", "-dir", required=True, help="Directory for retrieved dicoms")
@click.option("--mode", "-m", type=click.Choice([m.value for m in DeidentificationMode]), required=True)
@click.option("--source-dir", "-sdir", required=True, help="Where the dummy takes the dicoms")
def retrieve(exam_id, dest_dir, mode, source_dir):
    """Retrieves an exam, de-identifies it and store it in destination directory"""
    dummy = DummyExamRetriever(source_dir)
    click.echo(dummy.retrieve_exam(exam_id, dest_dir, mode=DeidentificationMode(mode)))

### TO DO : batch sur plusieurs examens

@cli.command()
@click.option("--exam-id", required=True)
@click.option("--source-dir", required=True, help="Où le faux dicom va chercher les fichiers")
@click.option("--dest-dir", required=True, help="Sert à la fois de destination de retrieve et d'exam_dir pour run")
@click.option("--mode", type=click.Choice([m.value for m in DeidentificationMode]), required=True)
@click.option("--method", required=True)
@click.option("--output-dir", required=True)
@click.option("--segment", multiple=True,
              help="Segment à traiter. Répétable. Défaut: legs et thighs.")
@click.option("--lang", default="en")
@click.option("--with-antecedent", is_flag=True, help="Inclure l'antécédent le plus récent dans le rapport.")
@click.option("--series", help="Optionnel. Associate the segment with its series. Caution : for 1 exam only. For multiple exams, use series-file. If not given : automated detectionof series. ")
@click.option("--series-file", help="Optionnel. File's path of the association of the segment with its series for each exam.  If not given : automated detectionof series.")
@click.option("--dev", "-d", is_flag=True, help="dev mode, detailed logging")
def process(exam_id, source_dir, dest_dir, mode, method, output_dir, lang, segment, with_antecedent, dev):
    """Chaîne retrieve → run → report, chemin heureux."""
    try:
        result = run_pipeline(
            result_index=FileResultIndex(),
            retriever=DummyExamRetriever(source_dir),
            report_generator=MedicalReportGenerator(),
            catalog=DummyExamCatalog(),
            with_antecedent=with_antecedent,
            dest_dir=dest_dir,
            mode=DeidentificationMode(mode),
            method=method,
            output_dir=output_dir,
            exam_id=exam_id,
            lang=lang,
            segment=list(segment) or None,
            dev=dev
        )
    except Exception as e:
        click.echo(f"Fail cmd process: {e}", err=True)
        sys.exit(1)
    click.echo(str(result["pdf_path"]))

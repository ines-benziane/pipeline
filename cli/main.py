import sys

import click

from adapters.medical_report_generator import MedicalReportGenerator
from methods.dummy import DummyMethod
from runner import methods_registry
from runner.job import Job
from runner.report_generator import ReportGenerationError
from runner.runner import run_job

methods_registry.register(DummyMethod)

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
    segments = list(segment) or ["legs", "thighs"]

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
            click.echo(f"{job.job_id}  {seg}  ÉCHEC: {e}", err=True)
            continue
        click.echo(f"{job.job_id}  {seg}  {job.state.value}")


@cli.command()
@click.option("--patient-id", required=True, help="Identifiant (pseudonyme) du patient.")
@click.option("--data-dir", required=True, help="Dossier des résultats JSON (json_output).")
@click.option("--output-dir", required=True, help="Dossier de sortie du rapport PDF.")
@click.option("--lang", default="fr", help="Langue du rapport.")
def report(patient_id, data_dir, output_dir, lang):
    """Génère le rapport médical PDF d'un patient à partir des résultats déjà traités."""
    generator = MedicalReportGenerator()
    try:
        pdf_path = generator.generate(patient_id, data_dir, output_dir, lang=lang)
    except ReportGenerationError as e:
        click.echo(f"ÉCHEC: {e}", err=True)
        sys.exit(1)
    click.echo(str(pdf_path))

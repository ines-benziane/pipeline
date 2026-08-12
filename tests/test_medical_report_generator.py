import pytest

from adapters import medical_report_generator as mrg
from adapters.medical_report_generator import MedicalReportGenerator
from runner.report_generator import NoPDFGeneratedError


def _fake_get_exam(exam_id, data_dir, config_data=None, antecedent_id=None):
    """Fake hermétique : renvoie un résultat non vide sans toucher au disque,
    pour atteindre l'appel à create_pdf (seul point réellement testé ici)."""
    return ["fake_exam"]


def _fake_create_pdf_writes_nothing(*args, **kwargs):
    """Fake create_pdf qui n'écrit rien — simule un échec interne avalé."""
    return None


def test_generate_raises_when_create_pdf_writes_nothing(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    monkeypatch.setattr(mrg, "get_exam", _fake_get_exam)
    monkeypatch.setattr(mrg, "create_pdf", _fake_create_pdf_writes_nothing)

    generator = MedicalReportGenerator()
    with pytest.raises(NoPDFGeneratedError):
        generator.generate(["exam_test"], tmp_path / "data", output_dir)


def test_generate_does_not_return_stale_pdf(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    stale_pdf = output_dir / mrg.OUTPUT_FILE
    stale_pdf.write_bytes(b"old stale pdf content")

    monkeypatch.setattr(mrg, "get_exam", _fake_get_exam)
    monkeypatch.setattr(mrg, "create_pdf", _fake_create_pdf_writes_nothing)

    generator = MedicalReportGenerator()
    with pytest.raises(NoPDFGeneratedError):
        generator.generate(["exam_test"], tmp_path / "data", output_dir)

    assert not stale_pdf.exists()

from types import SimpleNamespace

import pytest

from adapters import medical_report_generator as mrg
from adapters.medical_report_generator import MedicalReportGenerator
from qc_helpers import store_with_validated, validated_qc
from runner.qc_review import MapDecision, SegmentationDecision
from runner.report_generator import NoPDFGeneratedError, NoSectionAfterQCError


def _exam(exam_id, segment, method, date="2026-01-12"):
    return SimpleNamespace(metadata=SimpleNamespace(exam_id=exam_id, segment=segment, method=method, exam_date=date))


def _section(segment, method, antecedents=()):
    """What get_exam returns for one section: the exam of the section and its antecedents."""
    return SimpleNamespace(section_name=f"{segment}_{method}", exam=_exam("exam_test", segment, method),
                           antecedents=list(antecedents))


def _fake_get_exam(exam_id, data_dir, config_data=None, antecedent_ids=()):
    """Fake hermétique : renvoie un résultat non vide sans toucher au disque,
    pour atteindre l'appel à create_pdf (seul point réellement testé ici)."""
    return [_section("thighs", "dixon3pt")]


def _no_pacs(exam_id, exam_date):
    """Fake identity provider: these tests do not query the PACS."""
    return {"patient_name": "TEST PATIENT", "birth_date": "01/01/1970"}


def _fake_create_pdf_writes_nothing(*args, **kwargs):
    """Fake create_pdf qui n'écrit rien — simule un échec interne avalé."""
    return None


def _checked(tmp_path):
    return store_with_validated(tmp_path / "qc", "exam_test", [("thighs", "dixon3pt")])


def test_generate_raises_when_create_pdf_writes_nothing(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    monkeypatch.setattr(mrg, "get_exam", _fake_get_exam)
    monkeypatch.setattr(mrg, "create_pdf", _fake_create_pdf_writes_nothing)

    generator = MedicalReportGenerator(identity_provider=_no_pacs, qc_store=_checked(tmp_path))
    with pytest.raises(NoPDFGeneratedError):
        generator.generate(["exam_test"], tmp_path / "data", output_dir)


def test_generate_does_not_return_stale_pdf(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    stale_pdf = output_dir / mrg.OUTPUT_FILE
    stale_pdf.write_bytes(b"old stale pdf content")

    monkeypatch.setattr(mrg, "get_exam", _fake_get_exam)
    monkeypatch.setattr(mrg, "create_pdf", _fake_create_pdf_writes_nothing)

    generator = MedicalReportGenerator(identity_provider=_no_pacs, qc_store=_checked(tmp_path))
    with pytest.raises(NoPDFGeneratedError):
        generator.generate(["exam_test"], tmp_path / "data", output_dir)

    assert not stale_pdf.exists()


# --- QC filter: a section appears only if the latest validated QC of its block lets it appear


@pytest.fixture
def pdf_input(monkeypatch):
    """Replace create_pdf: record the sections it receives and write an empty PDF."""
    received = {}

    def fake_create_pdf(exams, output_dir, output_name, **kwargs):
        received["sections"] = exams
        (output_dir / output_name).write_bytes(b"%PDF-")

    monkeypatch.setattr(mrg, "create_pdf", fake_create_pdf)
    return received


def _generate(tmp_path, monkeypatch, sections, store):
    monkeypatch.setattr(mrg, "get_exam", lambda *args, **kwargs: sections)
    MedicalReportGenerator(identity_provider=_no_pacs, qc_store=store).generate(
        ["exam_test"], tmp_path / "data", tmp_path / "out")


def test_section_without_validated_qc_is_removed_and_reported(tmp_path, monkeypatch, pdf_input, capsys):
    sections = [_section("thighs", "dixon3pt"), _section("thighs", "t2map_3exp")]
    _generate(tmp_path, monkeypatch, sections, _checked(tmp_path))

    assert [s.section_name for s in pdf_input["sections"]] == ["thighs_dixon3pt"]
    assert "thighs_t2map_3exp" in capsys.readouterr().out


@pytest.mark.parametrize("map_decision, seg_decision", [
    (MapDecision.REJECTED, SegmentationDecision.ACCEPTED),
    (MapDecision.COMPLETE, SegmentationDecision.REJECTED),
    (MapDecision.LEFT_ONLY, SegmentationDecision.ACCEPTED),   # one side: whole section removed for now
])
def test_section_not_fully_accepted_is_removed(tmp_path, monkeypatch, pdf_input, map_decision, seg_decision):
    store = _checked(tmp_path)
    store.save(validated_qc("exam_test", "legs", "dixon3pt", map_decision=map_decision, map_reason="r",
                            seg_decision=seg_decision, seg_reason="r"))
    _generate(tmp_path, monkeypatch, [_section("thighs", "dixon3pt"), _section("legs", "dixon3pt")], store)

    assert [s.section_name for s in pdf_input["sections"]] == ["thighs_dixon3pt"]


def test_no_report_when_no_section_passes_the_qc(tmp_path, monkeypatch, pdf_input):
    with pytest.raises(NoSectionAfterQCError):
        _generate(tmp_path, monkeypatch, [_section("thighs", "dixon3pt")], store_with_validated(tmp_path / "qc", "x", []))

    assert "sections" not in pdf_input   # create_pdf never called


def test_antecedent_without_validated_qc_is_left_out_of_the_comparison(tmp_path, monkeypatch, pdf_input):
    checked_ant = _exam("ant_ok", "thighs", "dixon3pt", date="2025-01-12")
    unchecked_ant = _exam("ant_nope", "thighs", "dixon3pt", date="2024-01-12")
    store = _checked(tmp_path)
    store.save(validated_qc("ant_ok", "thighs", "dixon3pt"))

    _generate(tmp_path, monkeypatch, [_section("thighs", "dixon3pt", [unchecked_ant, checked_ant])], store)

    assert pdf_input["sections"][0].antecedents == [checked_ant]

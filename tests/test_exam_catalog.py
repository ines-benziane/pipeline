"""Contract tests for DummyExamCatalog: each ExamCatalog method returns the
expected type (a list of the right summary objects), not the exact content."""

import pytest
from runner.exam_catalog import ExamCatalog, ExamSummary, SeriesSummary
from adapters.dummy_exam_catalog import DummyExamCatalog

def test_find_exams_returns_exam_summaries():
    dummy = DummyExamCatalog() #vérifie la forme extérieure
    result = dummy.find_exams("John Doe")
    assert isinstance(result, list)
    assert all(isinstance(e, ExamSummary) for e in result ) # vérifie la forme intérieure 


def test_find_related_exams_returns_exam_summaries():
    dummy = DummyExamCatalog()
    result = dummy.find_related_exams("EXAM001")
    assert isinstance(result, list)
    assert all(isinstance(e, ExamSummary) for e in result)


def test_show_series_returns_series_summaries():
    dummy = DummyExamCatalog()
    result = dummy.show_series("EXAM001")
    assert isinstance(result, list)
    assert all(isinstance(s, SeriesSummary) for s in result)


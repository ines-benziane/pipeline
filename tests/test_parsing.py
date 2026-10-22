"""User input parsing (CLI and GUI fields). Input errors are the most frequent
user error, so every malformed input must fail loudly, never be guessed."""

import pytest

from runner.parsing import parse_acquisition, parse_method, parse_series


@pytest.mark.parametrize("raw, expected", [
    ("17,18", [17, 18]),
    ("17, 18", [17, 18]),
    ("17", [17]),
    ("", None),
    (None, None),
])
def test_parse_series(raw, expected):
    assert parse_series(raw) == expected


@pytest.mark.parametrize("raw", ["17,,18", "abc", "17;18"])
def test_parse_series_rejects_malformed(raw):
    with pytest.raises(ValueError):
        parse_series(raw)


@pytest.mark.parametrize("raw, expected", [
    ("legs:L:1.0", {"1.0": {"legs": "L"}}),
    ("legs", {None: {"legs": None}}),
    ("legs::1.0", {"1.0": {"legs": None}}),
    ("", None),
    (None, None),
])
def test_parse_acquisition(raw, expected):
    assert parse_acquisition(raw) == expected


def test_parse_acquisition_rejects_extra_parts():
    """segment:side:acquisition has 3 parts max; anything more is a typo."""
    with pytest.raises(ValueError):
        parse_acquisition("legs:L:1.0:extra")


@pytest.mark.parametrize("raw, expected", [
    ("dixon3pt", ("dixon3pt", {})),
    ("dixon3pt:a=1:b=2", ("dixon3pt", {"a": "1", "b": "2"})),
    ("t2map_3exp:fixed_fat=1", ("t2map_3exp", {"fixed_fat": "1"})),
])
def test_parse_method(raw, expected):
    assert parse_method(raw) == expected


def test_parse_method_rejects_param_without_value():
    with pytest.raises(ValueError):
        parse_method("dixon3pt:bad")

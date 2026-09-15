"""Parsing functions shared by CLI and GUI """

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

def parse_method(method):
    name, *raw = method.split(":")
    params = dict(p.split("=", 1) for p in raw)
    return (name, params)

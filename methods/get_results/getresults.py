import pathlib
from mutools import io
from mutools.tables import getresults as mutools_getresults 


def getresults(volumes, method_name, roi, labels, config_path=None, variant=None):
    """`variant` picks config/results_config_<variant>.yml (e.g. "raw": no erosion, no filter) instead of
    the default config/results_config.yml."""
    if config_path is None :
        name = f"results_config_{variant}.yml" if variant else "results_config.yml"
        config_path = pathlib.Path(__file__).parent / "config" / name
        if not config_path.exists():
            raise ValueError(f"unknown results_config variant {variant!r}: {config_path} not found")
    config_all = io.config.read(config_path)
    if method_name not in config_all :
        raise KeyError(f"Method {method_name} not in config file")
    config = config_all[method_name]
    task = config["variables"]
    defaults = config.get("default", {})
    reference = config.get("options", {}).get("reference")
    table = mutools_getresults.extract(task, roi, volumes, labels=labels, defaults=defaults, reference=reference)
    table.reset_index(inplace=True)
    return table
import pathlib
from mutools import io
from mutools.tables import getresults as mutools_getresults 


def getresults(volumes, method_name, roi, labels, config_path=None):
    if config_path is None :
        config_path = pathlib.Path(__file__).parent / "config" / "results_config.yml"
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
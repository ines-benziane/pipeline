from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Result :
    results : dict
    auto_valid : bool
    provenance : dict

class Method (ABC): 
    name : str
    version : str
    comparability_criteria : list

    @abstractmethod
    def run(self, source_dir, exam_id, workdir, segment, series, params, date, qc):
        ...

    @abstractmethod
    def handle_checkpoint(self, name, *, workdir):
        ... 
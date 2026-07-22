from abc import ABC, abstractmethod
from pathlib import Path


class ReportGenerator(ABC):
    @abstractmethod
    def generate(self, patient_id, data_dir, output_dir, *, lang="fr", config=None) -> Path:
        """Génère le PDF du patient à partir de data_dir, l'écrit sous output_dir,
        et retourne le chemin du PDF. Lève une exception en cas d'échec."""
        
        ...
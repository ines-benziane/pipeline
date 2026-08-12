"""Script jetable : copie les DICOM dont la SeriesDescription contient un motif
donné (dixon/VIBE par défaut) depuis un dossier source vers un dossier propre,
pour disposer de données de test sans mélange de séquences.

Usage:
    python scripts/extract_dixon_series.py <source_dir> <dest_dir> [--pattern VIBE]
"""

import argparse
import shutil
from pathlib import Path

import pydicom


def extract(source_dir: Path, dest_dir: Path, pattern: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    pattern_lower = pattern.lower()
    matched = 0
    skipped = 0

    for dcm_path in source_dir.glob("*.dcm"):
        ds = pydicom.dcmread(dcm_path, stop_before_pixels=True)
        description = getattr(ds, "SeriesDescription", "")
        if pattern_lower in description.lower():
            shutil.copy2(dcm_path, dest_dir / dcm_path.name)
            matched += 1
        else:
            skipped += 1

    print(f"{matched} fichier(s) copié(s) vers {dest_dir}")
    print(f"{skipped} fichier(s) ignoré(s) (SeriesDescription sans '{pattern}')")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("dest_dir", type=Path)
    parser.add_argument("--pattern", default="VIBE", help="Motif recherché dans SeriesDescription (défaut: VIBE)")
    args = parser.parse_args()

    extract(args.source_dir, args.dest_dir, args.pattern)

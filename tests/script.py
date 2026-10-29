"""This script compares results from MuReport with those of the manual segmentation, used currently in the lab
(and sent to clinicians).

RES-001 (FF) and RES-002 (T2): same exam, same segmentation (--external-seg), values side by side per region.
  - dixon3pt JSON   -> FF per group,  vs manual mean_roi_fat_ratio.txt
  - t2map_3exp JSON -> FF per muscle (fat fraction of the T2 fit), vs manual estimated_T2.txt (fat_fraction_noB1)
                       T2 per muscle, vs manual estimated_T2.txt (T2_noB1)

Usage:
    python tests/script.py <mureport.json> <manual results_* folder> [--tol-ff 1.0] [--tol-t2 1.0] [--out gaps.csv]
    add --slices to compare slice by slice instead of the whole muscle (region "TA_R z3" = TA_R, manual slice 3)
"""

import argparse
import csv
import json
import math
from pathlib import Path

# What to compare, depending on the muReport JSON given ("method" in its metadata).
# A dixon3pt JSON holds FF only -> 1 table. A t2map_3exp JSON holds T2 and FF (both from the T2 fit) -> 2 tables.
#
# Each comparison is written as 5 values. Example, the T2 line:
#     ("T2", "estimated_T2.txt", "T2_noB1", "num_pix_fit_noB1", 1)
#       |     |                   |          |                   |
#       |     |                   |          |                   +-- multiply the muReport value by this
#       |     |                   |          +-- column of the manual file giving the number of pixels per slice
#       |     |                   +-- column of the manual file giving the value per slice
#       |     +-- manual file to open (in the results_<date> folder)
#       +-- value to read in the muReport JSON (stats["T2"])
#
# Why multiply: muReport stores FF as 0.05, the manual file as 5 (%), so FF x 100. T2 is in ms on both sides, so x 1.
COMPARISONS = {
    "dixon3pt": [
        ("FF", "mean_roi_fat_ratio.txt", "FAT_RATIO", "num_pix", 100),
    ],
    "t2map_3exp": [
        ("FF", "estimated_T2.txt", "fat_fraction_noB1", "num_pix_fit_noB1", 100),
        ("T2", "estimated_T2.txt", "T2_noB1", "num_pix_fit_noB1", 1),
    ],
}
COLUMNS = ["biomarker", "region", "mureport", "manual", "diff", "npix_mureport", "npix_manual", "verdict"]


def read_mureport(data, biomarker, factor) -> dict[str, tuple[float, float]]:
    """muReport JSON data -> {"EXT_R": (value, npix)}, value in the manual unit."""
    values = {}
    for element in data["muscles"]:
        stats = element["volume"]["stats"]
        if biomarker in stats:
            values[f"{element['name']}_{element['side']}"] = (stats[biomarker] * factor, stats["NPIX"])
    return values


def read_manual(path, value_column, weight_column) -> dict[str, tuple[float, float]]:
    """Manual file (one line per slice and region) -> {"EXT_R": (mean weighted by pixels, total pixels)}.
    Lines starting with '#' are comments; columns are tab-separated; empty slices have 0 pixels or NaN."""
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = csv.DictReader((line for line in lines if not line.startswith("#")), delimiter="\t")
    sums = {}  # region -> [sum of value * pixels, sum of pixels] 
    for row in rows:
        value, weight = float(row[value_column]), float(row[weight_column])
        if weight == 0 or math.isnan(value):
            continue
        sums.setdefault(row["region"], [0.0, 0.0])
        sums[row["region"]][0] += value * weight
        sums[row["region"]][1] += weight
    return {region: (total / pixels, pixels) for region, (total, pixels) in sums.items()} #moyenne pondérée


def read_mureport_slices(data, biomarker, factor) -> dict[str, tuple[float, float | None]]:
    """muReport JSON data -> {"TA_R z3": (value, npix)} for every slice measured.
    muReport numbers slices from 0 (Z2), the manual file from 1 (slice 3): Z2 -> z3."""
    values = {}
    for element in data["muscles"]:
        for sl in element.get("slices", []):
            stats = sl.get("stats", {})
            if biomarker in stats:
                number = int(sl["index"].removeprefix("Z")) + 1
                key = f"{element['name']}_{element['side']} z{number}"
                values[key] = (stats[biomarker] * factor, stats.get("NPIX"))
    return values


def read_manual_slices(path, value_column, weight_column) -> dict[str, tuple[float, float]]:
    """Manual file -> {"TA_R z3": (value, pixels)}, one entry per non-empty slice (no averaging)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = csv.DictReader((line for line in lines if not line.startswith("#")), delimiter="	")
    values = {}
    for row in rows:
        value, weight = float(row[value_column]), float(row[weight_column])
        if weight == 0 or math.isnan(value):
            continue
        values[f"{row['region']} z{row['slice']}"] = (value, weight)
    return values


def verdict(diff, tolerance) -> str:
    if diff is None:
        return "ABSENT"
    if tolerance is None:
        return "-"
    return "PASS" if abs(diff) <= tolerance else "FAIL"


def compare(biomarker, mureport, manual, tolerance) -> list[dict]:
    """Build the table: one row per region (muscle or group).
    Regions come from both files: a region found in only one of them still gets a row, marked ABSENT,
    so that a muscle measured by muReport but not by the manual method (or the reverse) stays visible."""
    rows = []
    for region in sorted(mureport.keys() | manual.keys()):
        mu_value, mu_npix = mureport.get(region, (None, None))
        ma_value, ma_npix = manual.get(region, (None, None))
        diff = None if mu_value is None or ma_value is None else mu_value - ma_value
        rows.append({"biomarker": biomarker, "region": region, "mureport": mu_value, "manual": ma_value,
                     "diff": diff, "npix_mureport": mu_npix, "npix_manual": ma_npix,
                     "verdict": verdict(diff, tolerance)})
    return rows


def compare_results(json_path, manual_dir, tolerances, by_slice=False) -> list[dict]:
    """Main function, return the result: one row per (biomarker, region), or per (biomarker, region, slice)."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    method = data["metadata"]["method"]
    if method not in COMPARISONS:
        raise ValueError(f"no manual comparison for method {method!r} (known: {list(COMPARISONS)})")
    rows = []
    for biomarker, file, value_column, weight_column, factor in COMPARISONS[method]:
        if by_slice:
            mureport = read_mureport_slices(data, biomarker, factor)
            manual = read_manual_slices(manual_dir / file, value_column, weight_column)
        else:
            mureport = read_mureport(data, biomarker, factor)
            manual = read_manual(manual_dir / file, value_column, weight_column)
        rows += compare(biomarker, mureport, manual, tolerances[biomarker])
    return rows


def form(value, decimals=2) -> str:
    return "-" if value is None else f"{value:.{decimals}f}"


def print_table(rows) -> None:
    print(f"{'':4}{'region':<16}{'muReport':>10}{'manual':>10}{'diff':>8}{'NPIX mu':>10}{'NPIX ma':>10}  verdict")
    for r in rows:
        print(f"{r['biomarker']:<4}{r['region']:<16}{form(r['mureport']):>10}{form(r['manual']):>10}{form(r['diff']):>8}"
              f"{form(r['npix_mureport'], 0):>10}{form(r['npix_manual'], 0):>10}  {r['verdict']}")


def write_csv(rows, path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def main () -> None:
    parser = argparse.ArgumentParser(description="Compares results from MuReport with those of the manual segmentation.")
    parser.add_argument("json", type = Path, help="file json from MuReport")
    parser.add_argument("manual", type = Path, help="results folder from manual pipeline (LEG|THIGH/RESULTS/results_<date>)")
    parser.add_argument("--tol-ff", type=float, help="FF tolerance, in percentage points (PASS/FAIL if given)")
    parser.add_argument("--tol-t2", type=float, help="T2 tolerance, in ms (PASS/FAIL if given)")
    parser.add_argument("--out", type=Path, help="also write the table to this CSV file (proof for resultats_tests/)")
    parser.add_argument("--slices", action="store_true", help="compare slice by slice instead of the whole muscle")
    args = parser.parse_args()

    rows = compare_results(args.json, args.manual, {"FF": args.tol_ff, "T2": args.tol_t2}, by_slice=args.slices)
    print_table(rows)
    if args.out:
        write_csv(rows, args.out)


if __name__ == "__main__" :
    main()

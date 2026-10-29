"""RES-001 (FF) and RES-002 (T2) on the whole reference lot.

For each exam, segment (legs, thighs) and method (dixon3pt, t2map_3exp):
  1. find the manual processing of the exam: series used, ROI drawn, results (latest run);
  2. run muReport on the same series with the same ROI (--external-seg);
  3. compare the muReport JSON with the manual results (tests/script.py).

Inputs (read only):
  dicom/output_dir/<exam>/                       DICOM of the lot (dicom brick)
  <MANUAL_ROOT>/<year>/<year>_<exam>_<initials>/  manual processing:
      ROI_DIXON_LEG, ROI_T2_LEG, ...              ROI drawn by the technicians
      LEG/RESULTS/config_<date>.yml               series used for this run
      LEG/RESULTS/results_<date>/                 manual results of this run

Outputs, in resultats_tests/RES_lot/ (not in git: exam IDs contain dates):
  json/<exam>_<segment>_<method>.json   muReport result
  comparisons/<exam>_<segment>_<method>.csv   comparison table (one row per region)
  comparisons_slices/<exam>_<segment>_<method>.csv   same, slice by slice
  summary.csv   one row per exam, segment and biomarker: regions compared, mean and max gap, ABSENT regions
  runs.log      every run, OK or the error

Usage (from PIPELINE_01, pipeline environment):
  python scripts/run_lot.py                          the whole lot
  python scripts/run_lot.py --exams CL2LD260112      some exams only
  python scripts/run_lot.py --force                  re-run muReport even if its JSON is already there
  python scripts/run_lot.py --raw                    measure without erosion nor filters (results_config_raw.yml),
                                                     like the manual method; outputs in resultats_tests/RES_lot_raw/
  python scripts/run_lot.py --raw --legs-action swap-right --segments legs --methods dixon3pt
                                                     dixon3pt on the legs with an action (water/fat swap of the right leg,
                                                     as decided at QC); outputs in resultats_tests/RES_lot_raw_swap-right/
"""

import argparse
import csv
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.script import compare_results, write_csv  # noqa: E402

MANUAL_ROOT = Path(r"N:\0_Wip\New\0_Etudes_Protocolisees\2_Protos_3T_4T_Humain\&6_2014_CL_Clinique"
                   r"\3_Processed_Data\3T_Processing\Mesure_T2")
DICOM_DIR = ROOT / "dicom" / "output_dir"
OUT_DIR = ROOT / "resultats_tests" / "RES_lot"
MUREPORT_RESULTS = ROOT / "workdirs" / "results"

# muReport segment -> name of the part in the manual folders
PARTS = {"legs": "LEG", "thighs": "THIGH"}
# muReport method -> (key of its series in the manual config, prefix of the manual ROI folder)
METHODS = {"dixon3pt": ("DIXON_3PT", "ROI_DIXON_"), "t2map_3exp": ("T2_MAP", "ROI_T2_")}
SUMMARY_COLUMNS = ["exam", "segment", "method", "biomarker", "n_compared", "mean_diff", "max_abs_diff",
                   "max_region", "absent"]


def find_manual_dir(exam: str) -> Path:
    """<MANUAL_ROOT>/2026/2026_CL2LD260112_<initials>/ ; the year is in the exam ID (CL2LD 26 0112)."""
    year = "20" + exam[5:7]
    found = list((MANUAL_ROOT / year).glob(f"{year}_{exam}_*"))
    if len(found) != 1:
        raise FileNotFoundError(f"{len(found)} manual folders for {exam} in {MANUAL_ROOT / year}")
    return found[0]


def latest_manual_run(manual_dir: Path, part: str) -> tuple[Path, Path]:
    """Latest manual run of a part: (its config_<date>.yml, its results_<date>/ folder).
    Some exams were processed twice; the latest run is the one sent to the clinicians."""
    configs = list((manual_dir / part / "RESULTS").glob("config_*.yml"))
    if not configs:
        raise FileNotFoundError(f"no manual results for {part} in {manual_dir.name}")
    date = lambda cfg: datetime.strptime(cfg.stem.removeprefix("config_"), "%d-%b-%Y_%H%M%S")
    config = max(configs, key=date)
    return config, config.parent / config.stem.replace("config_", "results_")


def manual_series(config: Path, method: str) -> list[int]:
    """Series used by the manual run, e.g. DIXON_3PT: {SERIES: [17.0, 18.0]} -> [17, 18]."""
    data = yaml.safe_load(config.read_text(encoding="utf-8", errors="replace"))
    series = data[METHODS[method][0]]["SERIES"]
    return [int(s) for s in (series if isinstance(series, list) else [series])]


def run_mureport(exam: str, segment: str, method: str, series: list[int], roi_dir: Path, raw: bool,
                 action: str | None) -> Path:
    """Run `pipeline process` (the real CLI) with the manual ROI; return the JSON it wrote.
    raw: measure every pixel of the ROI (no erosion, no filter) with the method option results_config=raw.
    action: method action (-act), e.g. swap-right."""
    method_option = f"{method}:results_config=raw" if raw else method
    command = ["pipeline", "process",
               "-e", exam, "-sd", str(DICOM_DIR / exam), "-m", method_option, "-a", segment,
               "-od", str(OUT_DIR / "mureport_output"), "-s", ",".join(map(str, series)),
               "-extseg", str(roi_dir)] + (["-act", action] if action else [])
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        error = [line for line in (done.stdout + done.stderr).splitlines() if line.startswith(("Error", "  hint"))]
        raise RuntimeError(f"muReport failed (code {done.returncode}): {' '.join(error) or done.stderr.strip()[-300:]}")
    # muReport names its JSON <exam>_<date>_<segment>_<method>_<versions>.json in workdirs/results
    return max(MUREPORT_RESULTS.glob(f"{exam}_*_{segment}_{method}_*.json"), key=lambda p: p.stat().st_mtime)


def summarize(exam, segment, method, rows) -> list[dict]:
    """One summary row per biomarker of the comparison table."""
    summary = []
    for biomarker in sorted({r["biomarker"] for r in rows}):
        compared = [r for r in rows if r["biomarker"] == biomarker and r["diff"] is not None]
        absent = [r["region"] for r in rows if r["biomarker"] == biomarker and r["diff"] is None]
        worst = max(compared, key=lambda r: abs(r["diff"]), default=None)
        summary.append({
            "exam": exam, "segment": segment, "method": method, "biomarker": biomarker,
            "n_compared": len(compared),
            "mean_diff": sum(r["diff"] for r in compared) / len(compared) if compared else None,
            "max_abs_diff": abs(worst["diff"]) if worst else None,
            "max_region": worst["region"] if worst else None,
            "absent": " ".join(absent),
        })
    return summary


def process_one(exam, segment, method, force, raw, legs_action, log) -> list[dict]:
    """Steps 1 to 3 for one exam, segment and method; return its summary rows."""
    part = PARTS[segment]
    manual_dir = find_manual_dir(exam)
    config, results_dir = latest_manual_run(manual_dir, part)
    series = manual_series(config, method)
    roi_dir = manual_dir / f"{METHODS[method][1]}{part}"

    json_path = OUT_DIR / "json" / f"{exam}_{segment}_{method}.json"
    if force or not json_path.exists():
        action = legs_action if (segment, method) == ("legs", "dixon3pt") else None
        produced = run_mureport(exam, segment, method, series, roi_dir, raw, action)
        # a raw result is not a clinical result: moved out of workdirs/results so no report can use it
        (shutil.move if raw else shutil.copy)(produced, json_path)

    rows = compare_results(json_path, results_dir, {"FF": None, "T2": None})
    write_csv(rows, OUT_DIR / "comparisons" / f"{exam}_{segment}_{method}.csv")
    slice_rows = compare_results(json_path, results_dir, {"FF": None, "T2": None}, by_slice=True)
    write_csv(slice_rows, OUT_DIR / "comparisons_slices" / f"{exam}_{segment}_{method}.csv")
    log(f"OK     {exam} {segment} {method} series={series} manual={results_dir.name}")
    return summarize(exam, segment, method, rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exams", nargs="+", help="exam IDs (default: every exam in dicom/output_dir)")
    parser.add_argument("--force", action="store_true", help="re-run muReport even if its JSON is already there")
    parser.add_argument("--raw", action="store_true", help="measure without erosion nor filters, like the manual method")
    parser.add_argument("--legs-action", choices=["global-swap", "swap-right", "swap-left"],
                        help="action given to dixon3pt on the legs (water/fat swap decided at QC)")
    parser.add_argument("--segments", nargs="+", choices=list(PARTS), default=list(PARTS), help="default: all")
    parser.add_argument("--methods", nargs="+", choices=list(METHODS), default=list(METHODS), help="default: all")
    args = parser.parse_args()
    global OUT_DIR
    if args.raw:
        OUT_DIR = OUT_DIR.with_name("RES_lot_raw")
    if args.legs_action:
        OUT_DIR = OUT_DIR.with_name(f"{OUT_DIR.name}_{args.legs_action}")

    for sub in ("json", "comparisons", "comparisons_slices"):
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)
    exams = args.exams or sorted(p.name for p in DICOM_DIR.iterdir() if p.name.startswith("CL"))

    with open(OUT_DIR / "runs.log", "a", encoding="utf-8") as log_file:
        def log(message):
            line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
            print(line)
            log_file.write(line + "\n")
            log_file.flush()

        log(f"--- lot run: {len(exams)} exams{' (raw)' if args.raw else ''}"
            f"{f' legs action {args.legs_action}' if args.legs_action else ''}, {args.segments} x {args.methods}")
        summary = []
        for exam in exams:
            for segment in args.segments:
                for method in args.methods:
                    try:
                        summary += process_one(exam, segment, method, args.force, args.raw, args.legs_action, log)
                    except Exception as exc:  # one failing run must not stop the lot
                        log(f"FAILED {exam} {segment} {method}: {type(exc).__name__}: {exc}")

    with open(OUT_DIR / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(summary)
    print(f"\nSummary: {OUT_DIR / 'summary.csv'}")


if __name__ == "__main__":
    main()

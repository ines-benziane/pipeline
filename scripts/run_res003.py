"""RES-003 (orientation of the images): run muReport as delivered on the reference lot, then build the reports.

Two steps:
  1. --make-table : find the series of each exam and segment, check them, write a table to review
       series = the ones used by the manual processing (LEG|THIGH/RESULTS/config_<date>.yml, see scripts/run_lot.py);
       check  = each series exists in the DICOM folder and its SeriesDescription names the segment
                (JAMBE for legs, CUISSE for thighs) -> status OK, or A VERIFIER with the reason.
  2. --series-table <csv> : run muReport on the rows with status OK, as delivered
       a. dixon3pt   -qc-mode global                    -> overview.png, segmentation.gif
       b. t2map_3exp segmented on the Dixon series (-ss)
       c. pipeline report on the JSON of this run only  -> <exam>.pdf

  cd /mnt/rmn_files/Users/IB/mureport
  python scripts/run_res003.py --dicom-dir dicom_lot --make-table          # then open the table and check it
  nohup python scripts/run_res003.py --dicom-dir dicom_lot --series-table resultats_tests/RES003_series.csv \
      > res003_$(date +%Y%m%d).log 2>&1 &

Step 2 needs MuSeg-AI (Docker with the GPU): station only. Run detached (nohup): it does not depend on your PC.

Outputs (not in git):
  resultats_tests/RES003_series.csv                  step 1: one row per exam and segment
  resultats_tests/RES003_<date>/<exam>/<exam>.pdf     report to check
  resultats_tests/RES003_<date>/<exam>/qc/<job>/      overview.png, segmentation.gif to check
  resultats_tests/RES003_<date>/<exam>/json/          muReport results used for the report
  resultats_tests/RES003_<date>/runs.log              every run, OK or the error

Options: --exams <exam> ...      (default: every exam of the DICOM folder / of the table)
         --legs-action swap-right (water/fat swap of the right leg, as decided at QC)
         --dry-run                (step 2: print the commands, run nothing)
"""

import argparse
import csv
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pydicom

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_lot import PARTS, find_manual_dir, latest_manual_run, manual_series  # noqa: E402

MUREPORT_RESULTS = ROOT / "workdirs" / "results"
DEFAULT_TABLE = ROOT / "resultats_tests" / "RES003_series.csv"
SEGMENT_WORD = {"legs": "JAMBE", "thighs": "CUISSE"}   # expected in the SeriesDescription
COLUMNS = ["exam", "segment", "dixon_series", "dixon_descriptions", "t2_series", "t2_description", "status", "remark"]


# --- step 1: series table ----------------------------------------------------------------------

def series_description(exam_dicom: Path, number: int) -> str | None:
    """SeriesDescription of series <number> (folders are named <number>_<description> by the dicom brick)."""
    folders = [f for f in exam_dicom.glob(f"{number}_*") if f.is_dir()]
    files = [p for f in folders for p in f.glob("*.dcm")]
    if not files:
        return None
    return str(pydicom.dcmread(files[0], stop_before_pixels=True).get("SeriesDescription", ""))


def table_row(exam, segment, dicom_dir) -> dict:
    """Series of one exam and segment, checked against the DICOM folder."""
    row = dict(exam=exam, segment=segment, dixon_series="", dixon_descriptions="", t2_series="", t2_description="",
               status="A VERIFIER", remark="")
    try:
        config, _ = latest_manual_run(find_manual_dir(exam), PARTS[segment])
    except (FileNotFoundError, IndexError) as exc:
        row["remark"] = f"pas de traitement manuel : {exc}"
        return row
    dixon, t2 = manual_series(config, "dixon3pt"), manual_series(config, "t2map_3exp")
    descriptions = {n: series_description(dicom_dir / exam, n) for n in dixon + t2}
    row.update(dixon_series=",".join(map(str, dixon)), t2_series=",".join(map(str, t2)),
               dixon_descriptions=" | ".join(str(descriptions[n]) for n in dixon),
               t2_description=" | ".join(str(descriptions[n]) for n in t2))

    problems = [f"série {n} absente" for n, d in descriptions.items() if d is None]
    problems += [f"série {n} ne mentionne pas {SEGMENT_WORD[segment]} ({d})" for n, d in descriptions.items()
                 if d is not None and SEGMENT_WORD[segment] not in d.upper()]
    if len(dixon) != 2:
        problems.append(f"{len(dixon)} série(s) Dixon au lieu de 2")
    if len(t2) != 1:
        problems.append(f"{len(t2)} série(s) T2 au lieu de 1")
    row.update(status="OK" if not problems else "A VERIFIER", remark="; ".join(problems))
    return row


def make_table(exams, dicom_dir, path):
    rows = [table_row(exam, segment, dicom_dir) for exam in exams for segment in PARTS]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    ok = sum(r["status"] == "OK" for r in rows)
    print(f"{path}: {len(rows)} rows, {ok} OK, {len(rows) - ok} A VERIFIER")
    for r in rows:
        if r["status"] != "OK":
            print(f"  A VERIFIER  {r['exam']} {r['segment']}: {r['remark']}")


def read_table(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


# --- step 2: muReport runs -----------------------------------------------------------------------

def run(command, log, dry_run) -> bool:
    """Run one CLI command from the project root; log OK / FAILED with the error lines."""
    if dry_run:
        log("DRY    " + " ".join(command))
        return True
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode == 0:
        return True
    error = [line for line in (done.stdout + done.stderr).splitlines() if line.startswith(("Error", "  hint", "  caused by"))]
    log(f"FAILED {' '.join(command[:8])} ...: {' '.join(error) or done.stderr.strip()[-300:]}")
    return False


def collect_json(exam, segment, method, started, dest):
    """Copy the JSON muReport just wrote for this exam/segment/method into dest (the report reads only those)."""
    produced = [p for p in MUREPORT_RESULTS.glob(f"{exam}_*_{segment}_{method}_*.json") if p.stat().st_mtime >= started]
    for p in produced:
        shutil.copy(p, dest / p.name)
    return bool(produced)


def process_exam(exam, rows, dicom_dir, out, legs_action, log, dry_run):
    """Runs of one exam (rows of the series table), then its report."""
    exam_out = out / exam
    for sub in ("json", "qc"):
        (exam_out / sub).mkdir(parents=True, exist_ok=True)
    for row in rows:
        segment = row["segment"]
        if row["status"] != "OK":
            log(f"SKIP   {exam} {segment}: {row['remark']}")
            continue
        common = ["-e", exam, "-sd", str(dicom_dir / exam), "-a", segment, "-od", str(exam_out / "qc"),
                  "-qc-mode", "global"]
        action = ["-act", legs_action] if legs_action and segment == "legs" else []
        steps = [
            ("dixon3pt", ["pipeline", "process", "-m", "dixon3pt", "-s", row["dixon_series"]] + common + action),
            ("t2map_3exp", ["pipeline", "process", "-m", "t2map_3exp", "-s", row["t2_series"],
                            "-ss", row["dixon_series"]] + common),
        ]
        for method, command in steps:
            started = time.time()
            if run(command, log, dry_run) and not dry_run:
                ok = collect_json(exam, segment, method, started, exam_out / "json")
                log(f"{'OK    ' if ok else 'NOJSON'} {exam} {segment} {method}")

    report = ["pipeline", "report", "--exam-id", exam, "--data-dir", str(exam_out / "json"),
              "--output-dir", str(exam_out), "--lang", "fr"]
    if run(report, log, dry_run) and not dry_run:
        pdf = exam_out / "Medical_report.pdf"
        if pdf.exists():
            pdf.rename(exam_out / f"{exam}.pdf")
            log(f"OK     {exam} report")


def run_lot(table, dicom_dir, exams, legs_action, dry_run):
    rows = read_table(table)
    if exams:
        rows = [r for r in rows if r["exam"] in exams]
    out = ROOT / "resultats_tests" / f"RES003_{datetime.now():%Y%m%d}"
    out.mkdir(parents=True, exist_ok=True)
    by_exam = {}
    for r in rows:
        by_exam.setdefault(r["exam"], []).append(r)

    with open(out / "runs.log", "a", encoding="utf-8") as log_file:
        def log(message):
            line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
            print(line, flush=True)
            log_file.write(line + "\n")
            log_file.flush()

        log(f"--- RES-003 run: {len(by_exam)} exams, table {table}, DICOM {dicom_dir}"
            f"{f', legs action {legs_action}' if legs_action else ''}")
        for exam, exam_rows in by_exam.items():
            try:
                process_exam(exam, exam_rows, dicom_dir, out, legs_action, log, dry_run)
            except Exception as exc:  # one failing exam must not stop the lot
                log(f"FAILED {exam}: {type(exc).__name__}: {exc}")
    print(f"\nOutputs: {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dicom-dir", type=Path, default=ROOT / "dicom" / "output_dir",
                        help="folder with one sub-folder of DICOM per exam (default: dicom/output_dir)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--make-table", action="store_true", help="step 1: write and check the series table")
    mode.add_argument("--series-table", type=Path, help="step 2: run muReport on the OK rows of this table")
    parser.add_argument("--exams", nargs="+", help="exam IDs (default: all)")
    parser.add_argument("--legs-action", choices=["swap-right", "swap-left", "global-swap"],
                        help="action given to dixon3pt on the legs")
    parser.add_argument("--dry-run", action="store_true", help="step 2: print the commands, run nothing")
    args = parser.parse_args()

    dicom_dir = args.dicom_dir if args.dicom_dir.is_absolute() else ROOT / args.dicom_dir
    if args.make_table:
        exams = args.exams or sorted(p.name for p in dicom_dir.iterdir() if p.name.startswith("CL"))
        make_table(exams, dicom_dir, DEFAULT_TABLE)
    else:
        table = args.series_table if args.series_table.is_absolute() else ROOT / args.series_table
        run_lot(table, dicom_dir, args.exams, args.legs_action, args.dry_run)


if __name__ == "__main__":
    main()

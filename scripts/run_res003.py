"""RES-003 (orientation of the images): run muReport as delivered on the reference lot, then build the reports.

For each exam: segmentation by MuSeg-AI (no --external-seg), QC images, then the PDF report.
  1. dixon3pt   on legs and thighs, -qc-mode global  -> overview.png, segmentation.gif
  2. t2map_3exp on legs and thighs, segmented on the Dixon series (-ss)
  3. pipeline report on the JSON of this run only  -> <exam>.pdf
Series: the ones used by the manual processing (LEG|THIGH/RESULTS/config_<date>.yml), see scripts/run_lot.py.

Needs MuSeg-AI, so Docker with the GPU: run it on the station, detached so it survives the logout:
  cd /mnt/rmn_files/Users/IB/mureport
  nohup python scripts/run_res003.py --dicom-dir dicom_lot > res003_$(date +%Y%m%d).log 2>&1 &

Outputs, in resultats_tests/RES003_<date>/ (not in git):
  <exam>/<exam>.pdf                                  report to check
  <exam>/qc/<job>/overview.png, segmentation.gif     QC images to check
  <exam>/json/                                       muReport results used for the report
  runs.log                                           every run, OK or the error

Options: --exams <exam> ...      (default: every exam of the DICOM folder)
         --legs-action swap-right (water/fat swap of the right leg, as decided at QC)
         --dry-run                (print the commands, run nothing)
"""

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_lot import PARTS, find_manual_dir, latest_manual_run, manual_series  # noqa: E402

MUREPORT_RESULTS = ROOT / "workdirs" / "results"


def run(command, log, dry_run) -> bool:
    """Run one CLI command from the project root; log OK / FAILED with the error lines."""
    if dry_run:
        log("DRY    " + " ".join(command))
        return True
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode == 0:
        return True
    error = [line for line in (done.stdout + done.stderr).splitlines() if line.startswith(("Error", "  hint"))]
    log(f"FAILED {' '.join(command[:8])} ...: {' '.join(error) or done.stderr.strip()[-300:]}")
    return False


def collect_json(exam, segment, method, started, dest):
    """Copy the JSON muReport just wrote for this exam/segment/method into dest (the report reads only those)."""
    produced = [p for p in MUREPORT_RESULTS.glob(f"{exam}_*_{segment}_{method}_*.json") if p.stat().st_mtime >= started]
    for p in produced:
        shutil.copy(p, dest / p.name)
    return bool(produced)


def process_exam(exam, dicom_dir, out, legs_action, log, dry_run):
    exam_out = out / exam
    for sub in ("json", "qc"):
        (exam_out / sub).mkdir(parents=True, exist_ok=True)
    manual_dir = find_manual_dir(exam)
    for segment, part in PARTS.items():
        try:
            config, _ = latest_manual_run(manual_dir, part)
        except FileNotFoundError as exc:
            log(f"SKIP   {exam} {segment}: {exc}")
            continue
        dixon, t2 = manual_series(config, "dixon3pt"), manual_series(config, "t2map_3exp")
        common = ["-e", exam, "-sd", str(dicom_dir / exam), "-a", segment, "-od", str(exam_out / "qc"),
                  "-qc-mode", "global"]
        action = ["-act", legs_action] if legs_action and segment == "legs" else []
        steps = [
            ("dixon3pt", ["pipeline", "process", "-m", "dixon3pt", "-s", ",".join(map(str, dixon))] + common + action),
            ("t2map_3exp", ["pipeline", "process", "-m", "t2map_3exp", "-s", ",".join(map(str, t2)),
                            "-ss", ",".join(map(str, dixon))] + common),
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dicom-dir", type=Path, default=ROOT / "dicom" / "output_dir",
                        help="folder with one sub-folder of DICOM per exam (default: dicom/output_dir)")
    parser.add_argument("--exams", nargs="+", help="exam IDs (default: every exam of the DICOM folder)")
    parser.add_argument("--legs-action", choices=["swap-right", "swap-left", "global-swap"],
                        help="action given to dixon3pt on the legs")
    parser.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")
    args = parser.parse_args()

    dicom_dir = args.dicom_dir if args.dicom_dir.is_absolute() else ROOT / args.dicom_dir
    exams = args.exams or sorted(p.name for p in dicom_dir.iterdir() if p.name.startswith("CL"))
    out = ROOT / "resultats_tests" / f"RES003_{datetime.now():%Y%m%d}"
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "runs.log", "a", encoding="utf-8") as log_file:
        def log(message):
            line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
            print(line, flush=True)
            log_file.write(line + "\n")
            log_file.flush()

        log(f"--- RES-003 run: {len(exams)} exams, DICOM {dicom_dir}"
            f"{f', legs action {args.legs_action}' if args.legs_action else ''}")
        for exam in exams:
            try:
                process_exam(exam, dicom_dir, out, args.legs_action, log, args.dry_run)
            except Exception as exc:  # one failing exam must not stop the lot
                log(f"FAILED {exam}: {type(exc).__name__}: {exc}")
    print(f"\nOutputs: {out}")


if __name__ == "__main__":
    main()

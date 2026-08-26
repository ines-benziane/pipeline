"""Run job, manage its state. 
If SUCCESS : save the final result file (JSON file used by medical_report).
If any exception raised : job's state becomes FAILED --Later : and the crash mode is activated. 
"""

import shutil
import logging
import json
from pathlib import Path

from mutools.io import volume
from mutools import io

from runner.method import Result
from runner import job_store, methods_registry
from runner.job import JobState, QCMutoolsException, QCMuSegAIException

WORKDIR_ROOT = Path("workdirs")
RESULT_DIR = Path("data") / "results"

def make_workdir(job_id: str) -> Path:
    workdir = WORKDIR_ROOT / job_id
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir 

def run_job(job, dev=False) :
    method = methods_registry.get(job.method_id) #retrieve the method asked
    job.workdir = make_workdir(job.job_id)       #creates a workdir to store job's trace
    job.state = JobState.IN_PROGRESS             #changes job status 
    log_path = job.workdir / "run.log"
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.setLevel(logging.DEBUG if dev else logging.INFO)
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.DEBUG if dev else logging.INFO)
    root_logger.addHandler(handler)
    # quiets noisy third-party libraries even in dev mode (docker/urllib3 log
    # every HTTP call to the docker daemon at DEBUG level)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("docker").setLevel(logging.WARNING)

    job_store.save(job)

    try: 
        if job.checkpoint == "mutools":
            echo_times_record = json.loads((Path(job.workdir) / "echo_times_record.json").read_text())
            exam_date = echo_times_record["exam_date"]
            ffmap = volume.read(Path(job.workdir) / "ffmap.mha" )
            volumes = [volume.read(Path(job.workdir) / f"echo_{i}.mha") for i in range(3)]
            rois, labels, exam_date = method.segmentation(volumes, job.segment, job.exam_id, job.qc, exam_date, job.workdir)
            metadata = {"exam_id": job.exam_id, "exam_date": exam_date, "segment": job.segment,
                        "method": method.name, "version": method.version, "acquisition": "1.0", "biomarker": "FF"}
            json_path = method.write_results(ffmap, rois, labels, metadata, job.workdir)
            result = Result(json_path, auto_valid=True, provenance={"name": method.name, "version": method.version})
        elif job.checkpoint == "segmentation":
            echo_times_record = json.loads((Path(job.workdir) / "echo_times_record.json").read_text())
            exam_date = echo_times_record["exam_date"]
            metadata = {"exam_id": job.exam_id, "exam_date": exam_date, "segment": job.segment,
                        "method": method.name, "version": method.version, "acquisition": "1.0", "biomarker": "FF"}
            ffmap = volume.read(Path(job.workdir) / "ffmap.mha")
            roi = [volume.read(Path(job.workdir) / "roi.mha")]
            labels_obj = io.read_labels(Path(job.workdir) / "labels.txt")
            labels = dict(zip(labels_obj.indices, labels_obj.descriptions))
            json_path = method.write_results(ffmap, roi, labels, metadata, job.workdir)
            result = Result(json_path, auto_valid=True, provenance={"name": method.name, "version": method.version})
        else:
            result = method.run(job.source_dir, job.exam_id, job.workdir, job.segment, job.series, job.other_params, job.exam_date, job.qc)

    except QCMutoolsException as e:
        job.state = JobState.SUSPENDED 
        job.checkpoint = "mutools"
        job_store.save(job)
        return(job)
    
    except QCMuSegAIException as e:
        job.state = JobState.SUSPENDED
        job.checkpoint = "segmentation"
        job_store.save(job)
        return(job)
    
    except Exception:
        job.state = JobState.FAILED
        job_store.save(job)
        raise
    finally :
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_level)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(result.results, RESULT_DIR / result.results.name) #results given by method (ex json_output)
    if result.auto_valid: #not implemented yet 
        job.state = JobState.RESULTS_READY
    else : 
        job.state = JobState.SUSPENDED
    job_store.save(job)
    return job

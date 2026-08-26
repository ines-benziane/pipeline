import json
from pathlib import Path

from runner import job_store, methods_registry
from runner.job import JobState
from mutools.io import volume


def resume_pipeline(job_id, decision, state, exam_id, segment, method_id, workdir, checkpoint):
    """Resume where the job stopped. After mutools or after segmentation."""
    method = methods_registry.get(method_id)
    if checkpoint == "mutools" :
        volumes = [volume.read(Path(workdir) / f"echo_{i}.mha") for i in range(3)]
        state = JobState.IN_PROGRESS
        method.segmentation(volumes, segment, exam_id, True)
        #appeler la fonction qui reprend après mutools
    elif checkpoint == "segmentation":
    #appeler la fonction qui reprend à la segmentation
        ...
    job_store.save(...)



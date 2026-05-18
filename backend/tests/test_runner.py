from pathlib import Path

import pytest

from app.jobs.models import (
    Device,
    Engine,
    JobRequest,
    JobStage,
    JobStatus,
    Language,
    OutputFormat,
    Preprocess,
)
from app.jobs.store import JobStore
from app.pipeline.runner import run_job

pytestmark = pytest.mark.skipif(
    not __import__("shutil").which("tesseract"), reason="tesseract not installed"
)


def test_runner_produces_outputs(tmp_path: Path, text_pdf: Path):
    store = JobStore(ttl_seconds=600)
    req = JobRequest(
        file_id="t",
        engine=Engine.ocrmypdf,
        languages=[Language.en],
        page_range=(1, 1),
        preprocess=Preprocess(),
        formats=[OutputFormat.txt, OutputFormat.pdf, OutputFormat.json],
        workers=1,
        device=Device.cpu,
    )
    work_dir = tmp_path / "job"
    work_dir.mkdir()
    # Pretend file_id resolved to text_pdf
    state = store.create(work_dir=work_dir, total_pages=1, request=req)
    run_job(store=store, job_id=state.job_id, input_pdf=text_pdf)

    final = store.get(state.job_id)
    assert final.status == JobStatus.done
    assert final.stage == JobStage.finished
    produced = {o.format for o in final.outputs}
    assert produced == {OutputFormat.txt, OutputFormat.pdf, OutputFormat.json}
    for out in final.outputs:
        assert out.path.exists()
        assert out.size_bytes > 0

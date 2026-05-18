import pytest
from pydantic import ValidationError

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


def test_languages_enum():
    assert {l.value for l in Language} == {"pl", "en", "de", "fr", "es", "ru"}


def test_engine_enum():
    assert {e.value for e in Engine} == {"ocrmypdf", "paddle"}


def test_output_format_enum():
    assert {f.value for f in OutputFormat} == {"pdf", "txt", "md", "docx", "json"}


def test_job_status_terminal():
    assert JobStatus.done in {JobStatus.done, JobStatus.failed}


def test_job_stages():
    assert JobStage.ocr.value == "ocr"
    assert JobStage.formatting.value == "formatting"


def test_job_request_minimal():
    req = JobRequest(
        file_id="abc",
        engine=Engine.ocrmypdf,
        languages=[Language.pl],
        page_range=(1, 3),
        preprocess=Preprocess(deskew=True, denoise=False),
        formats=[OutputFormat.pdf, OutputFormat.txt],
        workers=4,
        device=Device.cpu,
    )
    assert req.page_range == (1, 3)


def test_job_request_rejects_inverted_range():
    with pytest.raises(ValidationError):
        JobRequest(
            file_id="abc",
            engine=Engine.ocrmypdf,
            languages=[Language.pl],
            page_range=(5, 2),
            preprocess=Preprocess(deskew=False, denoise=False),
            formats=[OutputFormat.txt],
            workers=1,
            device=Device.cpu,
        )


def test_job_request_rejects_empty_languages():
    with pytest.raises(ValidationError):
        JobRequest(
            file_id="abc",
            engine=Engine.ocrmypdf,
            languages=[],
            page_range=(1, 1),
            preprocess=Preprocess(deskew=False, denoise=False),
            formats=[OutputFormat.txt],
            workers=1,
            device=Device.cpu,
        )


def test_job_request_rejects_empty_formats():
    with pytest.raises(ValidationError):
        JobRequest(
            file_id="abc",
            engine=Engine.ocrmypdf,
            languages=[Language.pl],
            page_range=(1, 1),
            preprocess=Preprocess(deskew=False, denoise=False),
            formats=[],
            workers=1,
            device=Device.cpu,
        )


def test_job_request_rejects_empty_file_id():
    with pytest.raises(ValidationError):
        JobRequest(
            file_id="",
            engine=Engine.ocrmypdf,
            languages=[Language.pl],
            page_range=(1, 1),
            preprocess=Preprocess(deskew=False, denoise=False),
            formats=[OutputFormat.txt],
            workers=1,
            device=Device.cpu,
        )


def test_job_state_rejects_naive_finished_at():
    from datetime import datetime

    from app.jobs.models import JobState, JobStatus, JobStage
    from pathlib import Path

    req = JobRequest(
        file_id="abc",
        engine=Engine.ocrmypdf,
        languages=[Language.pl],
        page_range=(1, 1),
        preprocess=Preprocess(),
        formats=[OutputFormat.txt],
        workers=1,
        device=Device.cpu,
    )
    with pytest.raises(ValidationError):
        JobState(
            job_id="j",
            status=JobStatus.done,
            stage=JobStage.finished,
            total_pages=1,
            work_dir=Path("/tmp/x"),
            request=req,
            finished_at=datetime(2024, 1, 1, 12, 0, 0),  # naive
        )

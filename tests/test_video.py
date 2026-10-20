import io
import json
from urllib.parse import parse_qs

import httpx
import pytest

from poof import Job, Poof, PoofError

JOB = {
    "id": "job_8f3a1c2e9b7d4a10",
    "status": "queued",
    "progress": 0,
    "created_at": "2026-10-16T10:00:00Z",
    "started_at": None,
    "completed_at": None,
    "duration_seconds": 12.4,
    "fps": 29.97,
    "width": 1920,
    "height": 1080,
    "frames": 372,
    "credits": 65,
    "format": "webm",
    "channels": "rgba",
    "status_url": "https://api.poof.bg/v1/jobs/job_8f3a1c2e9b7d4a10",
    "result_url": None,
    "expires_at": None,
    "error": None,
    "stats": None,
}
RESULT_URL = "https://cdn.poof.bg/1d/jobs/job_8f3a1c2e9b7d4a10/result.webm"


def _job(**overrides: object) -> dict:
    return {**JOB, **overrides}


def _client(handler) -> Poof:
    return Poof(
        api_key="poof_test",
        httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _parts(request: httpx.Request) -> tuple[dict[str, str], dict[str, str]]:
    """Return (text fields, file parts keyed by field name -> filename)."""
    body = request.read()
    fields: dict[str, str] = {}
    files: dict[str, str] = {}
    content_type = request.headers["content-type"]
    if content_type.startswith("application/x-www-form-urlencoded"):
        # No file part: httpx sends a plain form body
        return {k: v[0] for k, v in parse_qs(body.decode()).items()}, files
    boundary = content_type.split("boundary=")[1].encode()
    for part in body.split(b"--" + boundary)[1:-1]:
        head, _, value = part.partition(b"\r\n\r\n")
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        if b"filename=" in head:
            files[name] = head.split(b'filename="')[1].split(b'"')[0].decode()
        else:
            fields[name] = value.rstrip(b"\r\n").decode()
    return fields, files


def test_video_upload_returns_job_and_uses_file_field():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(202, json=JOB)

    job = _client(handler).remove_background(
        io.BytesIO(b"\x00\x00\x00\x1cftypisom"), format="webm", channels="alpha"
    )

    assert isinstance(job, Job)
    assert job.id == "job_8f3a1c2e9b7d4a10"
    assert job.status == "queued" and not job.is_done
    assert job.credits == 65 and job.frames == 372 and job.fps == 29.97
    assert job.result_url is None
    assert job.raw == JOB
    fields, files = _parts(captured["request"])
    assert files == {"file": "file"}
    assert fields == {"format": "webm", "channels": "alpha"}
    assert captured["request"].headers["x-api-key"] == "poof_test"


def test_gif_format_is_sent_and_reported():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(202, json={**JOB, "format": "gif"})

    job = _client(handler).remove_background(
        io.BytesIO(b"GIF89a\x01\x00\x01\x00"), format="gif", size="medium"
    )

    assert isinstance(job, Job)
    assert job.format == "gif"
    fields, files = _parts(captured["request"])
    assert files == {"file": "file"}
    assert fields == {"format": "gif", "size": "medium"}


def test_url_input_sends_url_field_without_file():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(202, json=JOB)

    job = _client(handler).remove_background(
        url="https://example.com/clip.mp4", format="mp4", bg_color="#00ff00"
    )

    assert isinstance(job, Job)
    fields, files = _parts(captured["request"])
    assert files == {}
    assert fields == {
        "url": "https://example.com/clip.mp4",
        "format": "mp4",
        "bg_color": "#00ff00",
    }


def test_image_and_url_are_mutually_exclusive():
    client = _client(lambda request: httpx.Response(500))
    with pytest.raises(ValueError):
        client.remove_background()
    with pytest.raises(ValueError):
        client.remove_background(b"img", url="https://example.com/a.jpg")


def test_image_path_is_unchanged():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            content=b"\x89PNG",
            headers={
                "Content-Type": "image/png",
                "X-Image-Width": "640",
                "X-Image-Height": "480",
            },
        )

    result = _client(handler).remove_background(b"img", width=500, height=300)

    assert not isinstance(result, Job)
    assert bytes(result) == b"\x89PNG"
    assert result.width == 640 and result.height == 480
    fields, files = _parts(captured["request"])
    assert files == {"file": "file"}
    assert fields == {"width": "500", "height": "300"}


def test_get_job():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=_job(status="processing", progress=0.42))

    job = _client(handler).get_job("job_8f3a1c2e9b7d4a10")

    assert captured["request"].method == "GET"
    assert captured["request"].url.path == "/v1/jobs/job_8f3a1c2e9b7d4a10"
    assert job.status == "processing" and job.progress == 0.42


def test_get_job_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"code": "job_not_found", "message": "No such job"}
        )

    with pytest.raises(PoofError) as exc:
        _client(handler).get_job("job_missing")
    assert exc.value.code == "job_not_found" and exc.value.status_code == 404


def test_wait_for_job_polls_until_completed():
    states = iter(
        [
            _job(status="queued", progress=0),
            _job(status="processing", progress=0.5),
            _job(
                status="completed",
                progress=1,
                result_url=RESULT_URL,
                expires_at="2026-10-17T10:00:00Z",
            ),
        ]
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=next(states))

    seen: list[float] = []
    job = _client(handler).wait_for_job(
        Job.from_dict(JOB),
        poll_interval=0,
        on_progress=lambda j: seen.append(j.progress),
    )

    assert job.status == "completed" and job.is_done
    assert job.result_url == RESULT_URL
    assert seen == [0, 0.5, 1]
    assert calls == ["/v1/jobs/job_8f3a1c2e9b7d4a10"] * 3


def test_wait_for_job_accepts_job_id_and_completed_job():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_job(status="completed", result_url=RESULT_URL))

    client = _client(handler)
    assert (
        client.wait_for_job("job_8f3a1c2e9b7d4a10", poll_interval=0).result_url
        == RESULT_URL
    )

    # An already finished Job is returned without a request
    done = Job.from_dict(_job(status="completed", result_url=RESULT_URL))
    assert _client(lambda r: httpx.Response(500)).wait_for_job(done) is done


def test_wait_for_job_raises_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_job(
                status="failed",
                error={"code": "processing_failed", "message": "Encoder crashed"},
            ),
        )

    with pytest.raises(PoofError) as exc:
        _client(handler).wait_for_job("job_8f3a1c2e9b7d4a10", poll_interval=0)
    assert exc.value.code == "job_failed"
    assert exc.value.message == "Encoder crashed"
    assert exc.value.details == "processing_failed"


def test_wait_for_job_times_out():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_job(status="processing", progress=0.1))

    with pytest.raises(PoofError) as exc:
        _client(handler).wait_for_job(
            "job_8f3a1c2e9b7d4a10", poll_interval=0, timeout=0
        )
    assert exc.value.code == "timeout"


def test_remove_background_wait_returns_completed_job():
    states = iter(
        [
            (202, _job(status="queued")),
            (200, _job(status="processing", progress=0.5)),
            (200, _job(status="completed", progress=1, result_url=RESULT_URL)),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        status, body = next(states)
        return httpx.Response(status, json=body)

    client = Poof(
        api_key="poof_test",
        httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    # wait=True polls with the default interval; patch sleep out of the test
    import poof as poof_module

    original_sleep = poof_module.time.sleep
    poof_module.time.sleep = lambda s: None  # type: ignore[assignment]
    try:
        job = client.remove_background(io.BytesIO(b"vid"), wait=True)
    finally:
        poof_module.time.sleep = original_sleep

    assert isinstance(job, Job) and job.status == "completed"
    assert job.result_url == RESULT_URL


def test_download_writes_result_to_path(tmp_path):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200, content=b"webm-bytes", headers={"Content-Type": "video/webm"}
        )

    job = Job.from_dict(_job(status="completed", result_url=RESULT_URL))
    dest = _client(handler).download(job, tmp_path / "out.webm")

    assert dest.read_bytes() == b"webm-bytes"
    assert str(captured["request"].url) == RESULT_URL
    assert "x-api-key" not in captured["request"].headers

    # A bare URL works too
    dest2 = _client(handler).download(RESULT_URL, tmp_path / "out2.webm")
    assert dest2.read_bytes() == b"webm-bytes"


def test_download_requires_result_url(tmp_path):
    with pytest.raises(PoofError) as exc:
        _client(lambda r: httpx.Response(500)).download(
            Job.from_dict(JOB), tmp_path / "x"
        )
    assert exc.value.code == "job_not_ready"


def test_download_failure(tmp_path):
    with pytest.raises(PoofError) as exc:
        _client(lambda r: httpx.Response(404)).download(RESULT_URL, tmp_path / "x")
    assert exc.value.code == "download_failed" and exc.value.status_code == 404
    assert not (tmp_path / "x").exists()


def test_job_from_dict_round_trip():
    job = Job.from_dict(json.loads(json.dumps(JOB)))
    assert job.duration_seconds == 12.4 and job.width == 1920 and job.channels == "rgba"
    assert job.status_url.endswith("/jobs/job_8f3a1c2e9b7d4a10")


def test_crop_false_is_not_sent_for_video():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(202, json=JOB)

    _client(handler).remove_background(io.BytesIO(b"\x00" * 16), crop=False)

    fields, _ = _parts(captured["request"])
    assert "crop" not in fields


def test_validation_error_keeps_details_dict_and_doc_url():
    from poof import ValidationError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "code": "validation_error",
                "message": "crop is not supported for video",
                "details": {"field": "crop"},
                "request_id": "req_1",
                "doc_url": "https://docs.poof.bg/errors/validation-error",
            },
        )

    with pytest.raises(ValidationError) as excinfo:
        _client(handler).remove_background(io.BytesIO(b"\x00" * 16), crop=True)
    assert excinfo.value.details == {"field": "crop"}
    assert excinfo.value.doc_url == "https://docs.poof.bg/errors/validation-error"

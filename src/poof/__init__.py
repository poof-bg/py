"""
Poof - Python SDK for the Poof background removal API.

Simple, clean API for removing backgrounds from images and videos.

Example:
    from poof import Poof

    client = Poof(api_key="your-api-key")
    result = client.remove_background("image.jpg")
    result.save("output.png")

    # Videos are processed as a job
    job = client.remove_background("clip.mp4", wait=True)
    client.download(job, "clip.webm")
"""

from __future__ import annotations

import mimetypes
import time
from dataclasses import dataclass, field
from io import IOBase
from pathlib import Path
from typing import Any, BinaryIO, Callable, Literal, TypedDict, Union, cast

import httpx

from .exceptions import (
    AuthError,
    PaymentRequiredError,
    PermissionDeniedError,
    PoofError,
    RateLimitError,
    ServerError,
    ValidationError,
)

__version__ = "0.4.1"
__all__ = [
    "Poof",
    "PoofError",
    "AuthError",
    "RateLimitError",
    "PaymentRequiredError",
    "PermissionDeniedError",
    "ValidationError",
    "ServerError",
    "AccountInfo",
    "RemoveBackgroundResult",
    "Job",
    "ImageInput",
    "Format",
    "VideoFormat",
    "Channels",
    "Size",
    "Fit",
    "JobStatus",
]

DEFAULT_BASE_URL = "https://api.poof.bg/v1"
DEFAULT_TIMEOUT = 60.0

# Type aliases
ImageInput = Union[str, Path, bytes, BinaryIO]
Format = Literal["png", "jpg", "webp"]
VideoFormat = Literal["webm", "mov", "mp4", "gif"]
Channels = Literal["rgba", "rgb", "alpha"]
Size = Literal["full", "preview", "medium", "hd"]
Fit = Literal["contain", "cover", "scale-down"]
JobStatus = Literal["queued", "processing", "completed", "failed"]


class AccountInfo(TypedDict, total=False):
    """Account information returned by the /me endpoint."""

    organizationId: str
    plan: str
    maxCredits: int
    usedCredits: int
    autoRechargeThreshold: int | None


class RemoveBackgroundResult:
    """Result of a background removal operation.

    Attributes:
        data: The processed image bytes.
        content_type: MIME type of the image (e.g., "image/png").
        request_id: Unique request identifier for support.
        processing_time_ms: Processing time in milliseconds.
        width: Output image width in pixels.
        height: Output image height in pixels.
        matte_confidence: Confidence in the alpha matte, 0-1. 1 means a fully
            decisive mask; lower values mean the model hedged. Heuristic, not
            a calibrated probability.
        matte_ambiguous_ratio: Fraction of pixels with alpha between 0.1 and
            0.9, 0-1. High values indicate large uncertain regions - useful
            for flagging results for review.
    """

    __slots__ = (
        "data",
        "content_type",
        "request_id",
        "processing_time_ms",
        "width",
        "height",
        "matte_confidence",
        "matte_ambiguous_ratio",
    )

    def __init__(
        self,
        data: bytes,
        content_type: str | None = None,
        request_id: str | None = None,
        processing_time_ms: int | None = None,
        width: int | None = None,
        height: int | None = None,
        matte_confidence: float | None = None,
        matte_ambiguous_ratio: float | None = None,
    ) -> None:
        self.data = data
        self.content_type = content_type
        self.request_id = request_id
        self.processing_time_ms = processing_time_ms
        self.width = width
        self.height = height
        self.matte_confidence = matte_confidence
        self.matte_ambiguous_ratio = matte_ambiguous_ratio

    def __bytes__(self) -> bytes:
        """Return the image data as bytes."""
        return self.data

    def __len__(self) -> int:
        """Return the size of the image data in bytes."""
        return len(self.data)

    def save(self, path: str | Path) -> None:
        """Save the image to a file.

        Args:
            path: Destination file path.
        """
        Path(path).write_bytes(self.data)

    def __repr__(self) -> str:
        return (
            f"RemoveBackgroundResult("
            f"size={len(self.data)}, "
            f"content_type={self.content_type!r}, "
            f"dimensions={self.width}x{self.height})"
        )


@dataclass
class Job:
    """A video background removal job.

    Returned by :meth:`Poof.remove_background` when the input is a video,
    and by :meth:`Poof.get_job` / :meth:`Poof.wait_for_job`.

    Attributes:
        id: Job id (``job_...``).
        status: ``queued``, ``processing``, ``completed`` or ``failed``.
        progress: Fraction of the video processed so far, 0 to 1.
        created_at: When the job was accepted (ISO 8601).
        started_at: When processing started, or None.
        completed_at: When the job finished, or None.
        duration_seconds: Duration of the input video.
        fps: Frame rate of the input video.
        width: Width of the input video in pixels.
        height: Height of the input video in pixels.
        frames: Number of frames in the input video.
        credits: Credits charged for this job: 5 per second, rounded up
            (10 above 30 fps; animated GIF input is always 5 per second).
            Refunded if it fails.
        format: Output container: ``webm``, ``mov``, ``mp4`` or ``gif``.
        channels: Output channels: ``rgba``, ``rgb`` or ``alpha``.
        status_url: URL to poll for this job.
        result_url: Public download URL of the result once ``completed``,
            None before that. Valid until ``expires_at``.
        expires_at: When ``result_url`` stops working (24 h after completion).
        error: ``{"code": ..., "message": ...}`` when ``failed``, else None.
        stats: Processing statistics once completed, else None.
        raw: The job object exactly as returned by the API.
    """

    id: str
    status: str
    progress: float = 0.0
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    fps: float | None = None
    width: int | None = None
    height: int | None = None
    frames: int | None = None
    credits: int | None = None
    format: str | None = None
    channels: str | None = None
    status_url: str | None = None
    result_url: str | None = None
    expires_at: str | None = None
    error: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def is_done(self) -> bool:
        """True once the job has ``completed`` or ``failed``."""
        return self.status in ("completed", "failed")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        """Build a Job from the API's job object."""
        return cls(
            id=str(data.get("id", "")),
            status=str(data.get("status", "")),
            progress=float(data.get("progress") or 0.0),
            created_at=data.get("created_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            duration_seconds=data.get("duration_seconds"),
            fps=data.get("fps"),
            width=data.get("width"),
            height=data.get("height"),
            frames=data.get("frames"),
            credits=data.get("credits"),
            format=data.get("format"),
            channels=data.get("channels"),
            status_url=data.get("status_url"),
            result_url=data.get("result_url"),
            expires_at=data.get("expires_at"),
            error=data.get("error"),
            stats=data.get("stats"),
            raw=data,
        )


class Poof:
    """Client for the Poof background removal API.

    Args:
        api_key: Your Poof API key. Get one at https://dash.poof.bg
        base_url: API base URL. Defaults to https://api.poof.bg/v1
        timeout: Request timeout in seconds. Defaults to 60.
        httpx_client: Optional custom httpx.Client instance.

    Example:
        >>> from poof import Poof
        >>> client = Poof(api_key="your-api-key")
        >>> result = client.remove_background("photo.jpg")
        >>> result.save("output.png")
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        httpx_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._owns_client = httpx_client is None
        self._client = httpx_client or httpx.Client(timeout=timeout)

    def __enter__(self) -> Poof:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._owns_client:
            self._client.close()

    def _get_headers(self) -> dict[str, str]:
        """Get default headers for API requests."""
        return {
            "x-api-key": self._api_key,
            "User-Agent": f"poofbg/{__version__}",
        }

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle error responses from the API."""
        try:
            error_data = response.json()
            code = error_data.get("code", "unknown_error")
            message = error_data.get("message", "Unknown error")
            details = error_data.get("details")
            request_id = error_data.get("request_id")
            doc_url = error_data.get("doc_url")
        except Exception:
            code = "unknown_error"
            message = response.text or f"HTTP {response.status_code}"
            details = None
            request_id = response.headers.get("X-Request-ID")
            doc_url = None

        error_kwargs = {
            "message": message,
            "code": code,
            "details": details,
            "request_id": request_id,
            "status_code": response.status_code,
            "doc_url": doc_url,
        }

        if response.status_code == 401:
            raise AuthError(**error_kwargs)
        elif response.status_code == 402:
            raise PaymentRequiredError(**error_kwargs)
        elif response.status_code == 403:
            raise PermissionDeniedError(**error_kwargs)
        elif response.status_code == 429:
            raise RateLimitError(**error_kwargs)
        elif response.status_code == 400:
            raise ValidationError(**error_kwargs)
        elif response.status_code >= 500:
            raise ServerError(**error_kwargs)
        else:
            raise PoofError(**error_kwargs)

    def _prepare_file(self, image: ImageInput) -> tuple[str, bytes, str]:
        """Prepare an image or video for upload.

        Returns:
            Tuple of (filename, data, content_type)
        """
        if isinstance(image, (str, Path)):
            path = Path(image)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            filename = path.name
            data = path.read_bytes()
            content_type = (
                mimetypes.guess_type(filename)[0] or "application/octet-stream"
            )
        elif isinstance(image, bytes):
            filename = "file"
            data = image
            content_type = "application/octet-stream"
        elif isinstance(image, IOBase) or hasattr(image, "read"):
            # File-like object
            data = image.read()
            filename = getattr(image, "name", "file")
            if isinstance(filename, (str, Path)):
                filename = Path(filename).name
            else:
                filename = "file"
            content_type = (
                mimetypes.guess_type(filename)[0] or "application/octet-stream"
            )
        else:
            raise TypeError(
                f"file must be a file path, bytes, or file-like object, "
                f"got {type(image).__name__}"
            )

        return filename, data, content_type

    def remove_background(
        self,
        image: ImageInput | None = None,
        *,
        url: str | None = None,
        format: Format | VideoFormat | None = None,
        channels: Channels | None = None,
        bg_color: str | None = None,
        size: Size | None = None,
        crop: bool | str | None = None,
        padding: str | None = None,
        width: int | None = None,
        height: int | None = None,
        fit: Fit | None = None,
        wait: bool = False,
    ) -> RemoveBackgroundResult | Job:
        """Remove the background from an image or a video.

        Poof detects the media type from the bytes. An image is processed
        synchronously and returned as a :class:`RemoveBackgroundResult`. A video
        is accepted as a :class:`Job`: poll it with :meth:`wait_for_job` (or pass
        ``wait=True``) and fetch the file with :meth:`download`.

        Args:
            image: Image or video to process. Can be a file path (str or Path),
                bytes, or a file-like object. Either ``image`` or ``url``.
            url: Public HTTPS URL of the image or video to process instead of
                uploading it (videos up to 500 MB).
            format: Output format. Images: "png" (default), "jpg" or "webp".
                Videos: "webm" (default, VP9 with alpha), "mov" (ProRes 4444),
                "mp4" (H.264, composited on ``bg_color``) or "gif" (looping,
                1-bit transparency, no audio, capped at 1280 px on the longest
                side / 720p for widescreen and 50 fps).
            channels: Color channels - "rgba" for transparency, "rgb" for opaque,
                "alpha" for the grayscale alpha matte only. Defaults to "rgba".
            bg_color: Background color: hex (#ffffff), rgb, or color name.
                Setting it fills the background, so the result is opaque, for
                images and videos in every format (webm, mov and gif included).
                With channels "rgb" (or format "jpg"/"mp4") and no bg_color the
                background is white. Ignored with channels "alpha".
            size: Output size preset - "full", "preview", "medium", "hd".
                Defaults to "full". For videos the longest side is capped at
                640 (preview), 1280 (medium), 1920 (hd) or the source
                resolution up to 4096 px / 4K (full).
            crop: Images only. Crop the image to the subject bounds. Pass
                True or an aspect ratio string like "1:1", "4:3", "16:9".
                Only sent when enabled, so ``crop=False`` is a no-op (also
                for videos).
            padding: Images only. Padding around the subject when crop is
                enabled, as a fraction ("0.1") or percentage ("10%").
            width: Images only. Output width in pixels (1-6000). On its own,
                the height follows the aspect ratio. Overrides ``size``.
            height: Images only. Output height in pixels (1-6000). On its own,
                the width follows the aspect ratio. Overrides ``size``.
            fit: Images only. How to fit the image into ``width`` x ``height``
                (never stretched) - "contain" (default; fit inside, pad the
                rest), "cover" (fill, crop the overflow around the subject) or
                "scale-down" (like contain, but never enlarge a smaller image).
            wait: For videos, block until the job finishes and return the
                completed :class:`Job` (see :meth:`wait_for_job`). Has no
                effect on images.

        Returns:
            RemoveBackgroundResult for an image, Job for a video.

        Raises:
            FileNotFoundError: If the path doesn't exist.
            ValueError: If neither or both of ``image`` and ``url`` are given.
            AuthError: Invalid or missing API key.
            PaymentRequiredError: Insufficient credits (for a video: not
                enough left to cover the whole clip).
            RateLimitError: Rate limit exceeded.
            ValidationError: Invalid parameters or file.
            ServerError: Server-side error.
            PoofError: Other API errors, including a failed job when ``wait``.

        Example:
            >>> result = client.remove_background("photo.jpg", format="webp", crop=True)
            >>> result.save("output.webp")
            >>> # Exact 500x500 product image, subject cropped and centred
            >>> result = client.remove_background("photo.jpg", crop=True, width=500, height=500)
            >>> # Video: transparent WebM, wait for the job, then download it
            >>> job = client.remove_background("clip.mp4", wait=True)
            >>> client.download(job, "clip.webm")
        """
        if (image is None) == (url is None):
            raise ValueError("pass exactly one of image or url")

        # Build multipart form data
        files: dict[str, tuple[str, bytes, str]] | None = None
        form_data: dict[str, str] = {}
        if image is not None:
            files = {"file": self._prepare_file(image)}
        else:
            form_data["url"] = cast(str, url)

        if format is not None:
            form_data["format"] = format
        if channels is not None:
            form_data["channels"] = channels
        if bg_color is not None:
            form_data["bg_color"] = bg_color
        if size is not None:
            form_data["size"] = size
        # crop defaults to off and is image-only: only send it when enabled,
        # so crop=False on a video is not rejected with a validation_error.
        if crop is True:
            form_data["crop"] = "true"
        elif isinstance(crop, str) and crop:
            form_data["crop"] = crop
        if padding is not None:
            form_data["padding"] = padding
        if width is not None:
            form_data["width"] = str(width)
        if height is not None:
            form_data["height"] = str(height)
        if fit is not None:
            form_data["fit"] = fit

        response = self._client.post(
            f"{self._base_url}/remove",
            headers=self._get_headers(),
            files=files,
            data=form_data if form_data else None,
        )

        if response.status_code == 202:
            # Video: the API accepted a job
            job = Job.from_dict(cast("dict[str, Any]", response.json()))
            return self.wait_for_job(job) if wait else job

        if response.status_code != 200:
            self._handle_error(response)

        # Extract metadata from headers
        headers = response.headers
        processing_time = headers.get("X-Processing-Time-Ms")
        out_width = headers.get("X-Image-Width")
        out_height = headers.get("X-Image-Height")
        matte_confidence = headers.get("X-Matte-Confidence")
        matte_ambiguous_ratio = headers.get("X-Matte-Ambiguous-Ratio")

        return RemoveBackgroundResult(
            data=response.content,
            content_type=headers.get("Content-Type"),
            request_id=headers.get("X-Request-ID"),
            processing_time_ms=int(processing_time) if processing_time else None,
            width=int(out_width) if out_width else None,
            height=int(out_height) if out_height else None,
            matte_confidence=float(matte_confidence) if matte_confidence else None,
            matte_ambiguous_ratio=float(matte_ambiguous_ratio)
            if matte_ambiguous_ratio
            else None,
        )

    def get_job(self, job: str | Job) -> Job:
        """Fetch the current state of a video job.

        Polling is free and does not count against your rate limit.

        Args:
            job: Job id (``job_...``) or a :class:`Job`.

        Returns:
            The job with its current status, progress and ``result_url``.

        Raises:
            PoofError: ``job_not_found`` (404) or other API errors.

        Example:
            >>> job = client.get_job("job_8f3a1c2e9b7d4a10")
            >>> print(job.status, job.progress)
        """
        job_id = job.id if isinstance(job, Job) else job
        response = self._client.get(
            f"{self._base_url}/jobs/{job_id}",
            headers=self._get_headers(),
        )

        if response.status_code != 200:
            self._handle_error(response)

        return Job.from_dict(cast("dict[str, Any]", response.json()))

    def wait_for_job(
        self,
        job: str | Job,
        *,
        poll_interval: float = 3.0,
        timeout: float = 600.0,
        on_progress: Callable[[Job], None] | None = None,
    ) -> Job:
        """Poll a video job until it completes.

        Args:
            job: Job id or :class:`Job` as returned by :meth:`remove_background`.
            poll_interval: Seconds between status checks. Defaults to 3.
            timeout: Give up after this many seconds. Defaults to 600 (10 min).
                Videos process at roughly real time, so allow at least the
                clip's duration.
            on_progress: Called with the latest :class:`Job` after every poll.

        Returns:
            The completed job; ``result_url`` is set.

        Raises:
            PoofError: ``job_failed`` if the job failed (credits are refunded),
                ``timeout`` if it did not finish within ``timeout`` seconds,
                or other API errors.

        Example:
            >>> job = client.remove_background("clip.mp4")
            >>> job = client.wait_for_job(job, on_progress=lambda j: print(j.progress))
            >>> client.download(job, "clip.webm")
        """
        current = job if isinstance(job, Job) else None
        deadline = time.monotonic() + timeout
        while True:
            if current is None or not current.is_done:
                current = self.get_job(current if current is not None else job)
                if on_progress is not None:
                    on_progress(current)
            if current.status == "completed":
                return current
            if current.status == "failed":
                error = current.error or {}
                raise PoofError(
                    error.get("message") or f"Job {current.id} failed",
                    code="job_failed",
                    details=error.get("code"),
                )
            if time.monotonic() >= deadline:
                raise PoofError(
                    f"Job {current.id} did not finish within {timeout:g} seconds",
                    code="timeout",
                )
            time.sleep(poll_interval)

    def download(self, job: str | Job, path: str | Path) -> Path:
        """Download a finished video to a file.

        The result lives on Poof's CDN for 24 hours after completion and needs
        no API key.

        Args:
            job: A completed :class:`Job`, or its ``result_url``.
            path: Destination file path.

        Returns:
            The destination path.

        Raises:
            PoofError: ``job_not_ready`` if the job has no ``result_url`` yet,
                or ``download_failed`` if the CDN did not return the file.

        Example:
            >>> job = client.remove_background("clip.mp4", format="mov", wait=True)
            >>> client.download(job, "clip.mov")
        """
        if isinstance(job, Job):
            if not job.result_url:
                raise PoofError(
                    f"Job {job.id} has no result yet (status: {job.status})",
                    code="job_not_ready",
                )
            url = job.result_url
        else:
            url = job

        dest = Path(path)
        with self._client.stream("GET", url) as response:
            if response.status_code != 200:
                raise PoofError(
                    f"Download failed with HTTP {response.status_code}",
                    code="download_failed",
                    status_code=response.status_code,
                )
            with dest.open("wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
        return dest

    def me(self) -> AccountInfo:
        """Get account information.

        Returns information about the authenticated account including
        plan details and credit usage.

        Returns:
            AccountInfo dict with organization details and credit usage.

        Raises:
            AuthError: Invalid or missing API key.
            PoofError: Other API errors.

        Example:
            >>> info = client.me()
            >>> print(f"Used {info['usedCredits']} of {info['maxCredits']} credits")
        """
        response = self._client.get(
            f"{self._base_url}/me",
            headers=self._get_headers(),
        )

        if response.status_code != 200:
            self._handle_error(response)

        return cast(AccountInfo, response.json())

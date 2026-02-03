"""
Poof - Python SDK for the Poof background removal API.

Simple, clean API for removing backgrounds from images.

Example:
    from poof import Poof

    client = Poof(api_key="your-api-key")
    result = client.remove_background("image.jpg")

    # Save the result
    with open("output.png", "wb") as f:
        f.write(result)
"""

from __future__ import annotations

import mimetypes
import os
from io import IOBase
from pathlib import Path
from typing import BinaryIO, Literal, TypedDict, Union

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

__version__ = "0.1.0"
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
]

DEFAULT_BASE_URL = "https://api.poof.bg/v1"
DEFAULT_TIMEOUT = 60.0

# Type aliases
ImageInput = Union[str, Path, bytes, BinaryIO]
Format = Literal["png", "jpg", "webp"]
Channels = Literal["rgba", "rgb"]
Size = Literal["full", "preview", "small", "medium", "large"]


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
    """

    __slots__ = (
        "data",
        "content_type",
        "request_id",
        "processing_time_ms",
        "width",
        "height",
    )

    def __init__(
        self,
        data: bytes,
        content_type: str | None = None,
        request_id: str | None = None,
        processing_time_ms: int | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        self.data = data
        self.content_type = content_type
        self.request_id = request_id
        self.processing_time_ms = processing_time_ms
        self.width = width
        self.height = height

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
            "User-Agent": f"poof-python/{__version__}",
        }

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle error responses from the API."""
        try:
            error_data = response.json()
            code = error_data.get("code", "unknown_error")
            message = error_data.get("message", "Unknown error")
            details = error_data.get("details")
            request_id = error_data.get("request_id")
        except Exception:
            code = "unknown_error"
            message = response.text or f"HTTP {response.status_code}"
            details = None
            request_id = response.headers.get("X-Request-ID")

        error_kwargs = {
            "message": message,
            "code": code,
            "details": details,
            "request_id": request_id,
            "status_code": response.status_code,
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

    def _prepare_image(
        self, image: ImageInput
    ) -> tuple[str, bytes, str]:
        """Prepare image for upload.

        Returns:
            Tuple of (filename, data, content_type)
        """
        if isinstance(image, (str, Path)):
            path = Path(image)
            if not path.exists():
                raise FileNotFoundError(f"Image file not found: {path}")
            filename = path.name
            data = path.read_bytes()
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        elif isinstance(image, bytes):
            filename = "image"
            data = image
            content_type = "application/octet-stream"
        elif isinstance(image, IOBase) or hasattr(image, "read"):
            # File-like object
            data = image.read()  # type: ignore
            filename = getattr(image, "name", "image")
            if isinstance(filename, (str, Path)):
                filename = Path(filename).name
            else:
                filename = "image"
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        else:
            raise TypeError(
                f"image must be a file path, bytes, or file-like object, "
                f"got {type(image).__name__}"
            )

        return filename, data, content_type

    def remove_background(
        self,
        image: ImageInput,
        *,
        format: Format | None = None,
        channels: Channels | None = None,
        bg_color: str | None = None,
        size: Size | None = None,
        crop: bool | None = None,
    ) -> RemoveBackgroundResult:
        """Remove background from an image.

        Args:
            image: Image to process. Can be a file path (str or Path),
                bytes, or a file-like object.
            format: Output format - "png", "jpg", or "webp". Defaults to "png".
            channels: Color channels - "rgba" for transparency, "rgb" for opaque.
                Defaults to "rgba".
            bg_color: Background color when channels="rgb". Can be hex (#ffffff),
                rgb, or color name.
            size: Output size preset - "full", "preview", "small", "medium", "large".
                Defaults to "full".
            crop: Whether to crop the image to the subject bounds.

        Returns:
            RemoveBackgroundResult containing the processed image and metadata.

        Raises:
            FileNotFoundError: If image path doesn't exist.
            AuthError: Invalid or missing API key.
            PaymentRequiredError: Insufficient credits.
            RateLimitError: Rate limit exceeded.
            ValidationError: Invalid parameters or image.
            ServerError: Server-side error.
            PoofError: Other API errors.

        Example:
            >>> result = client.remove_background("photo.jpg", format="webp", crop=True)
            >>> result.save("output.webp")
        """
        filename, data, content_type = self._prepare_image(image)

        # Build multipart form data
        files = {"image_file": (filename, data, content_type)}
        form_data: dict[str, str] = {}

        if format is not None:
            form_data["format"] = format
        if channels is not None:
            form_data["channels"] = channels
        if bg_color is not None:
            form_data["bg_color"] = bg_color
        if size is not None:
            form_data["size"] = size
        if crop is not None:
            form_data["crop"] = str(crop).lower()

        response = self._client.post(
            f"{self._base_url}/remove",
            headers=self._get_headers(),
            files=files,
            data=form_data if form_data else None,
        )

        if response.status_code != 200:
            self._handle_error(response)

        # Extract metadata from headers
        headers = response.headers
        processing_time = headers.get("X-Processing-Time-Ms")
        width = headers.get("X-Image-Width")
        height = headers.get("X-Image-Height")

        return RemoveBackgroundResult(
            data=response.content,
            content_type=headers.get("Content-Type"),
            request_id=headers.get("X-Request-ID"),
            processing_time_ms=int(processing_time) if processing_time else None,
            width=int(width) if width else None,
            height=int(height) if height else None,
        )

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

        return response.json()

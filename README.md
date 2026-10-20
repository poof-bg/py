# poofbg

The official Python SDK for the [Poof](https://poof.bg) [background removal API](https://poof.bg/background-removal-api). Removes backgrounds from images and from [video](https://poof.bg/video-background-removal-api).

Migrating from remove.bg? It shuts down on 1 December 2026 — see the [remove.bg alternative and migration guide](https://poof.bg/alternative/remove-bg).

## Installation

```bash
pip install poofbg
```

## Quick Start

```python
from poof import Poof

# Initialize the client
client = Poof(api_key="your-api-key")

# Remove background from an image
result = client.remove_background("photo.jpg")

# Save the result
result.save("output.png")
```

## Usage

### Remove Background

```python
from poof import Poof

client = Poof(api_key="your-api-key")

# From a file path
result = client.remove_background("image.jpg")

# From bytes
with open("image.jpg", "rb") as f:
    image_bytes = f.read()
result = client.remove_background(image_bytes)

# From a file object
with open("image.jpg", "rb") as f:
    result = client.remove_background(f)

# Save the result
result.save("output.png")

# Or get the bytes directly
image_data = result.data
# or: image_data = bytes(result)
```

### Options

```python
# Different output format
result = client.remove_background("photo.jpg", format="webp")

# Crop to subject bounds
result = client.remove_background("photo.jpg", crop=True)

# RGB output with background color (no transparency)
result = client.remove_background(
    "photo.jpg",
    channels="rgb",
    bg_color="#ffffff"
)

# Different size presets
result = client.remove_background("photo.jpg", size="preview")

# Exact output size, never stretched: subject cropped, then fitted into 500x500
result = client.remove_background("photo.jpg", crop=True, width=500, height=500)

# Fill the canvas instead (overflow cropped around the subject), on white
result = client.remove_background(
    "photo.jpg", width=1080, height=1080, fit="cover", format="jpg", bg_color="#ffffff"
)

# Cap the width and keep the aspect ratio; small images are left as they are
result = client.remove_background("photo.jpg", width=1000, fit="scale-down")
```

### Video

Videos go through the same `remove_background()` call. Poof detects the media type from the bytes: an image comes back at once, a video is accepted as a `Job` that you poll and then download. The result is a transparent WebM by default; `format="mov"` gives a ProRes 4444 MOV, `format="mp4"` an H.264 video composited on `bg_color`, `format="gif"` a looping GIF with 1-bit transparency and no audio, capped at 720p (for stickers and chat; add `size="preview"` for sticker-sized output), and `channels="alpha"` a grayscale alpha matte. Audio, frame rate and duration are preserved. An animated GIF is accepted as input too. Video costs 5 credits per second.

```python
from poof import Job, Poof

client = Poof(api_key="your-api-key")

# Submit, wait for the job and download the transparent WebM
job = client.remove_background("clip.mp4", wait=True)
client.download(job, "clip.webm")

# Or poll yourself, with progress
job = client.remove_background("clip.mp4", format="mov")
job = client.wait_for_job(job, on_progress=lambda j: print(f"{j.progress:.0%}"))
client.download(job, "clip.mov")

# From a public URL (up to 500 MB), green-screen MP4
job = client.remove_background(
    url="https://example.com/clip.mp4", format="mp4", bg_color="#00ff00", wait=True
)
print(job.credits, job.duration_seconds, job.result_url)

# Check on a job later by id
job = client.get_job("job_8f3a1c2e9b7d4a10")
if job.is_done:
    ...
```

When you do not know whether an input is an image or a video, check the return type:

```python
result = client.remove_background(path)
if isinstance(result, Job):
    client.download(client.wait_for_job(result), "out.webm")
else:
    result.save("out.png")
```

`crop`, `padding`, `width`, `height` and `fit` are image-only; sending them with a video raises a `ValidationError`. Results stay on the CDN for 24 hours (`job.expires_at`). A failed job is refunded and `wait_for_job()` raises a `PoofError` with `code == "job_failed"`.

### Result Metadata

```python
result = client.remove_background("photo.jpg")

print(f"Image size: {result.width}x{result.height}")
print(f"Processing time: {result.processing_time_ms}ms")
print(f"Content type: {result.content_type}")
print(f"Request ID: {result.request_id}")
```

### Account Info

```python
info = client.me()

print(f"Plan: {info['plan']}")
print(f"Credits used: {info['usedCredits']} / {info['maxCredits']}")
```

### Context Manager

```python
with Poof(api_key="your-api-key") as client:
    result = client.remove_background("photo.jpg")
    result.save("output.png")
# Client is automatically closed
```

## Error Handling

```python
from poof import (
    Poof,
    PoofError,
    AuthError,
    RateLimitError,
    PaymentRequiredError,
    ValidationError,
)

client = Poof(api_key="your-api-key")

try:
    result = client.remove_background("photo.jpg")
except AuthError as e:
    print(f"Authentication failed: {e.message}")
except PaymentRequiredError as e:
    print(f"Insufficient credits: {e.message}")
except RateLimitError as e:
    print(f"Rate limited: {e.message}")
except ValidationError as e:
    print(f"Invalid request: {e.message}")
except PoofError as e:
    print(f"API error: {e.message} (code: {e.code})")
```

All exceptions include:
- `message`: Human-readable error description
- `code`: Machine-readable error code
- `details`: Additional troubleshooting info
- `request_id`: Unique ID for support
- `status_code`: HTTP status code

## Configuration

```python
# Custom timeout (default: 60 seconds)
client = Poof(api_key="...", timeout=120)

# Custom base URL
client = Poof(api_key="...", base_url="https://api.example.com/v1")

# Bring your own httpx client
import httpx

with httpx.Client(timeout=30, http2=True) as http_client:
    client = Poof(api_key="...", httpx_client=http_client)
    result = client.remove_background("photo.jpg")
```

## API Reference

### `Poof(api_key, *, base_url, timeout, httpx_client)`

Create a new Poof client.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | required | Your Poof API key |
| `base_url` | `str` | `https://api.poof.bg/v1` | API base URL |
| `timeout` | `float` | `60.0` | Request timeout in seconds |
| `httpx_client` | `httpx.Client` | `None` | Custom HTTP client |

### `client.remove_background(image=None, *, url, format, channels, bg_color, size, crop, padding, width, height, fit, wait)`

Remove the background from an image or a video.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image` | `str \| Path \| bytes \| BinaryIO` | `None` | Image or video to upload (one of `image`/`url`) |
| `url` | `str` | `None` | Public HTTPS URL of the image or video instead of an upload |
| `format` | `"png" \| "jpg" \| "webp"` / `"webm" \| "mov" \| "mp4" \| "gif"` | `"png"` / `"webm"` | Output format (images / videos) |
| `channels` | `"rgba" \| "rgb" \| "alpha"` | `"rgba"` | Color channels (`alpha` = grayscale matte only) |
| `bg_color` | `str` | white | Background color when the output has no alpha (`rgb`, `jpg`, `mp4`) |
| `size` | `"full" \| "preview" \| "medium" \| "hd"` | `"full"` | Output size preset (images: megapixel cap; video: longest side 640 / 1280 / 1920, `full` = source up to 4K); ignored when `width`/`height` is set |
| `crop` | `bool \| str` | `False` | Images only. Crop to subject bounds, or an aspect ratio like `"1:1"` |
| `padding` | `str` | `"10%"` | Images only. Padding around the subject when cropping (`"10%"`, `"0.1"`, or `"10%,7.5%"`) |
| `width` | `int` | `None` | Images only. Output width in pixels (1-6000); alone, height follows the aspect ratio |
| `height` | `int` | `None` | Images only. Output height in pixels (1-6000); alone, width follows the aspect ratio |
| `fit` | `"contain" \| "cover" \| "scale-down"` | `"contain"` | Images only. How to fit into `width` x `height` without stretching: pad, crop the overflow, or pad without enlarging |
| `wait` | `bool` | `False` | Videos only. Block until the job finishes and return the completed `Job` |

Returns a `RemoveBackgroundResult` for an image, with:
- `data`: Image bytes
- `content_type`: MIME type
- `width`, `height`: Image dimensions
- `processing_time_ms`: Processing time
- `request_id`: Request ID for support
- `save(path)`: Save to file

Returns a `Job` for a video (see below).

### `client.get_job(job)`

Fetch the current state of a video job by id or `Job`. Polling is free and does not count against the rate limit. Returns a `Job`.

### `client.wait_for_job(job, *, poll_interval=3.0, timeout=600.0, on_progress=None)`

Poll a job until it completes and return the completed `Job`. Raises `PoofError` with `code="job_failed"` if the job fails and `code="timeout"` if it is not done within `timeout` seconds. `on_progress` is called with the latest `Job` after every poll.

### `client.download(job, path)`

Download a completed job (or a bare `result_url`) to `path`. No API key is needed; the file is served from the CDN for 24 hours.

### `Job`

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Job id (`job_...`) |
| `status` | `str` | `queued`, `processing`, `completed` or `failed` |
| `progress` | `float` | Fraction processed, 0 to 1 |
| `is_done` | `bool` | True once `completed` or `failed` |
| `duration_seconds`, `fps`, `width`, `height`, `frames` | | Properties of the input video |
| `credits` | `int` | Credits charged (5 per second, refunded on failure) |
| `format`, `channels` | `str` | Output format and channels |
| `result_url` | `str \| None` | Public download URL once completed |
| `expires_at` | `str \| None` | When `result_url` stops working (24 h after completion) |
| `error` | `dict \| None` | `{"code", "message"}` when failed |
| `stats` | `dict \| None` | Processing statistics once completed |
| `raw` | `dict` | The job object as returned by the API |

### `client.me()`

Get account information.

Returns an `AccountInfo` dict:
- `organizationId`: Organization ID
- `plan`: Plan name
- `maxCredits`: Total credits
- `usedCredits`: Used credits
- `autoRechargeThreshold`: Auto-recharge threshold (if enabled)

## License

MIT

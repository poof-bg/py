# poofbg

The official Python SDK for the [Poof](https://poof.bg) background removal API.

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

### `client.remove_background(image, *, format, channels, bg_color, size, crop, padding, width, height, fit)`

Remove background from an image.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image` | `str \| Path \| bytes \| BinaryIO` | required | Image to process |
| `format` | `"png" \| "jpg" \| "webp"` | `"png"` | Output format |
| `channels` | `"rgba" \| "rgb" \| "alpha"` | `"rgba"` | Color channels (`alpha` = grayscale mask only) |
| `bg_color` | `str` | `None` | Background color (when `channels` is `"rgb"` or `"rgba"`) |
| `size` | `"full" \| "preview" \| "medium" \| "hd"` | `"full"` | Output size preset (megapixel cap); ignored when `width`/`height` is set |
| `crop` | `bool \| str` | `False` | Crop to subject bounds, or an aspect ratio like `"1:1"` |
| `padding` | `str` | `"10%"` | Padding around the subject when cropping (`"10%"`, `"0.1"`, or `"10%,7.5%"`) |
| `width` | `int` | `None` | Output width in pixels (1-6000); alone, height follows the aspect ratio |
| `height` | `int` | `None` | Output height in pixels (1-6000); alone, width follows the aspect ratio |
| `fit` | `"contain" \| "cover" \| "scale-down"` | `"contain"` | How to fit into `width` x `height` without stretching: pad, crop the overflow, or pad without enlarging |

Returns a `RemoveBackgroundResult` with:
- `data`: Image bytes
- `content_type`: MIME type
- `width`, `height`: Image dimensions
- `processing_time_ms`: Processing time
- `request_id`: Request ID for support
- `save(path)`: Save to file

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

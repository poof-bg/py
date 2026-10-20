# Changelog

All notable changes to `poofbg`. Versions follow [semver](https://semver.org).

## 0.4.1 - 2026-10-20

### Fixed

- `crop` is only sent when enabled (`True` or an aspect ratio). `crop=False` used to be sent as `crop=false`, which the API rejects for videos with a 400 `validation_error`.
- `PoofError.details` is typed `dict | str | None` (the API returns a dict such as `{"field": "crop"}` for validation errors).

### Added

- `PoofError.doc_url`: link to the documentation page for the error code.
- `dev` extra (`pip install -e ".[dev]"`) with pytest, ruff and mypy.
- GitHub Releases are created automatically when a version tag is pushed.

### Docs

- `gif` output: looping, 1-bit transparency, no audio, capped at 1280 px on the longest side (720p for widescreen) and 50 fps.
- Audio is kept except for `gif` and `channels="alpha"` output.
- `bg_color` applies to opaque output (`rgb`, `jpg`, `mp4`) and is ignored for transparent output.
- Video pricing: 5 credits per second rounded up (10 above 30 fps); animated GIF input is always 5 credits per second. A 402 is returned when remaining credits don't cover the clip.
- Limits: 5 minutes, 100 MB upload, 500 MB by URL.

## 0.4.0 - 2026-10-20

- `gif` added to `VideoFormat`: animated GIF output for stickers and chat. Animated GIF input is processed as a video.
- Documented 4K output for videos with `size="full"`.

## 0.3.0 - 2026-10-20

- Video background removal: `remove_background()` returns a `Job` for videos, plus `get_job()`, `wait_for_job()`, `download()`, `wait=True` and `url=` input.
- Video output formats `webm`, `mov` and `mp4`.

## 0.2.0 - 2026-09-07

- `channels="alpha"` (grayscale mask output) and matte confidence metadata.
- `width`, `height` and `fit` output-size parameters; corrected size presets.
- Publishing to PyPI on version tags via trusted publishing.

## 0.1.0 - 2026-02-03

- Initial release.

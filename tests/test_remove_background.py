import io

import httpx

from poof import Poof


def _client_capturing(captured: dict) -> Poof:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            content=b"\x89PNG",
            headers={
                "Content-Type": "image/png",
                "X-Request-ID": "req_test",
                "X-Processing-Time-Ms": "12",
                "X-Image-Width": "500",
                "X-Image-Height": "500",
            },
        )

    return Poof(
        api_key="poof_test",
        httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _form_fields(request: httpx.Request) -> dict[str, str]:
    body = request.read()
    boundary = request.headers["content-type"].split("boundary=")[1].encode()
    fields = {}
    for part in body.split(b"--" + boundary)[1:-1]:
        head, _, value = part.partition(b"\r\n\r\n")
        if b"filename=" in head:
            continue
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        fields[name] = value.rstrip(b"\r\n").decode()
    return fields


def test_output_size_parameters_are_sent():
    captured: dict = {}
    client = _client_capturing(captured)
    result = client.remove_background(
        io.BytesIO(b"img"), crop=True, width=500, height=300, fit="cover"
    )

    fields = _form_fields(captured["request"])
    assert fields["crop"] == "true"
    assert fields["width"] == "500"
    assert fields["height"] == "300"
    assert fields["fit"] == "cover"
    assert result.width == 500 and result.height == 500


def test_single_dimension_with_scale_down():
    captured: dict = {}
    _client_capturing(captured).remove_background(
        io.BytesIO(b"img"), width=1000, fit="scale-down"
    )

    fields = _form_fields(captured["request"])
    assert fields == {"width": "1000", "fit": "scale-down"}


def test_omitted_parameters_are_not_sent():
    captured: dict = {}
    _client_capturing(captured).remove_background(io.BytesIO(b"img"))

    assert _form_fields(captured["request"]) == {}

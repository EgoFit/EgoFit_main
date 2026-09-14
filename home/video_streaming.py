from __future__ import annotations

import mimetypes
from email.utils import formatdate
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse, StreamingHttpResponse

from home.exceptions import VideoStreamException


DEFAULT_CHUNK_SIZE = 1024 * 1024


def parse_http_range(range_header: str | None, file_size: int) -> tuple[int, int] | None:
    if not range_header or not range_header.startswith("bytes="):
        return None

    ranges = range_header.removeprefix("bytes=").split(",")
    if len(ranges) != 1:
        return None

    start_text, _, end_text = ranges[0].partition("-")
    try:
        if start_text == "":
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
    except (TypeError, ValueError):
        return None

    if start < 0 or end < start or start >= file_size:
        return None

    return start, min(end, file_size - 1)


def iter_file_range(file_path: Path, start: int, end: int, chunk_size: int = DEFAULT_CHUNK_SIZE):
    with file_path.open("rb") as stream:
        stream.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = stream.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def build_video_response(file_path: str | Path, range_header: str | None = None):
    path = Path(file_path)
    try:
        stat_result = path.stat()
    except OSError as exc:
        raise VideoStreamException("Video file is not available") from exc

    file_size = stat_result.st_size
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    x_accel_prefix = getattr(settings, "VIDEO_X_ACCEL_REDIRECT_PREFIX", "").strip()
    etag = f'"{int(stat_result.st_mtime)}-{file_size}"'

    if file_size <= 0:
        return HttpResponse(status=404)

    byte_range = parse_http_range(range_header, file_size)
    if range_header and byte_range is None:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{file_size}"
        response["Accept-Ranges"] = "bytes"
        return response

    if byte_range:
        start, end = byte_range
        response = StreamingHttpResponse(iter_file_range(path, start, end), status=206, content_type=content_type)
        response["Content-Length"] = str(end - start + 1)
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    elif x_accel_prefix:
        response = HttpResponse(content_type=content_type)
        response["X-Accel-Redirect"] = f"{x_accel_prefix.rstrip('/')}/{path.name}"
        response["Content-Length"] = str(file_size)
    else:
        response = FileResponse(path.open("rb"), content_type=content_type)
        response["Content-Length"] = str(file_size)

    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "private, max-age=3600"
    response["ETag"] = etag
    response["Last-Modified"] = formatdate(stat_result.st_mtime, usegmt=True)
    response["Content-Disposition"] = f'inline; filename="{path.name}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response

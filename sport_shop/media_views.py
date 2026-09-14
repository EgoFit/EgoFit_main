import logging
import mimetypes
from pathlib import Path
from typing import Dict
from urllib.parse import quote

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponseNotModified
from django.utils.http import http_date, parse_http_date_safe
from django.views import View

logger = logging.getLogger(__name__)


class ResilientMediaView(View):
    """
    Serve local media when available and backfill it from remote storage when
    the local mirror is missing. Responses are cacheable so browsers do not
    re-download the same asset on every navigation.
    """

    def _response_headers(self, file_path: Path) -> Dict[str, str]:
        stat_result = file_path.stat()
        last_modified = http_date(stat_result.st_mtime)
        etag = f'W/"{stat_result.st_mtime_ns:x}-{stat_result.st_size:x}"'
        cache_max_age = int(getattr(settings, "MEDIA_CACHE_MAX_AGE", 86400))
        return {
            "Last-Modified": last_modified,
            "ETag": etag,
            "Cache-Control": f"public, max-age={cache_max_age}",
        }

    def _is_not_modified(self, request, file_path: Path) -> bool:
        stat_result = file_path.stat()
        etag = f'W/"{stat_result.st_mtime_ns:x}-{stat_result.st_size:x}"'
        if request.META.get("HTTP_IF_NONE_MATCH"):
            client_etags = [token.strip() for token in request.META["HTTP_IF_NONE_MATCH"].split(",")]
            if etag in client_etags:
                return True

        if_modified_since = request.META.get("HTTP_IF_MODIFIED_SINCE")
        if if_modified_since:
            modified_since = parse_http_date_safe(if_modified_since)
            if modified_since is not None and int(stat_result.st_mtime) <= modified_since:
                return True

        return False

    def _serve_file(self, request, file_path: Path):
        content_type, _ = mimetypes.guess_type(str(file_path))
        if self._is_not_modified(request, file_path):
            response = HttpResponseNotModified()
        else:
            response = FileResponse(file_path.open("rb"), content_type=content_type)

        if content_type in {
            "text/html",
            "application/xhtml+xml",
            "image/svg+xml",
            "application/javascript",
            "text/javascript",
        }:
            response["Content-Disposition"] = (
                f"attachment; filename*=UTF-8''{quote(file_path.name)}"
            )

        for header, value in self._response_headers(file_path).items():
            response[header] = value
        return response

    def _safe_media_path(self, path: str):
        """Return a normalized media name and path confined to MEDIA_ROOT."""
        normalized_path = (path or "").lstrip("/")
        if not normalized_path or "\x00" in normalized_path:
            raise Http404("File not found")

        media_root = Path(settings.MEDIA_ROOT).resolve()
        try:
            resolved_path = (media_root / normalized_path).resolve()
            resolved_path.relative_to(media_root)
        except (OSError, RuntimeError, ValueError):
            # ValueError is raised when the resolved path is outside MEDIA_ROOT;
            # the other exceptions cover malformed paths and filesystem errors.
            raise Http404("File not found")
        return normalized_path, resolved_path

    def get(self, request, path):
        normalized_path, local_path = self._safe_media_path(path)
        if local_path.exists() and local_path.is_file():
            return self._serve_file(request, local_path)

        fetch_remote = getattr(default_storage, "fetch_remote_to_local", None)
        if callable(fetch_remote):
            try:
                fetched = fetch_remote(normalized_path)
            except Exception as exc:
                logger.warning("Remote media backfill failed for %s: %s", normalized_path, exc)
                fetched = False

            if fetched:
                _, refreshed_path = self._safe_media_path(normalized_path)
                if refreshed_path.exists() and refreshed_path.is_file():
                    return self._serve_file(request, refreshed_path)

        raise Http404("File not found")

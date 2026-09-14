from __future__ import annotations

from pathlib import Path

from django.http import Http404

from home.exceptions import VideoStreamException
from home.video_streaming import build_video_response


class VideoService:
    @staticmethod
    def _ensure_local_video_path(storage, name: str) -> Path | None:
        try:
            local_path = Path(storage.path(name))
        except NotImplementedError:
            return None

        if local_path.exists() and local_path.is_file():
            return local_path

        fetch_remote = getattr(storage, "fetch_remote_to_local", None)
        if callable(fetch_remote):
            try:
                fetched = fetch_remote(name)
            except Exception as exc:
                raise VideoStreamException("Video file is not available") from exc

            if fetched and local_path.exists() and local_path.is_file():
                return local_path

        return None

    @staticmethod
    def get_video_response(*, episode, user, range_header: str | None = None):
        series = episode.season.series if episode.season else None
        if series is None:
            raise Http404("Video is not available")

        from home.selectors.course_selector import CourseSelector

        if not CourseSelector.get_user_has_access(user=user, series=series):
            raise Http404("You do not have access to this video")

        if not episode.video_file:
            raise Http404("Video file is not available")

        storage = episode.video_file.storage
        name = episode.video_file.name
        file_path = VideoService._ensure_local_video_path(storage, name)
        if file_path is None:
            raise Http404("Video file is not available locally")

        try:
            return build_video_response(file_path, range_header)
        except VideoStreamException as exc:
            raise Http404(str(exc)) from exc

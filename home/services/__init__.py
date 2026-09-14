from __future__ import annotations

from home.exceptions import CommentSubmissionException, HomeException, SearchValidationException, SeriesAccessDeniedException, VideoStreamException
from home.services.comment_service import CommentService
from home.services.content_service import ContentService
from home.services.search_service import SearchService
from home.services.series_service import SeriesService
from home.services.video_service import VideoService

__all__ = [
    "HomeException",
    "SearchValidationException",
    "CommentSubmissionException",
    "SeriesAccessDeniedException",
    "VideoStreamException",
    "normalize_search_query",
    "search_courses",
    "search_blogs",
    "list_blog_categories",
    "SearchService",
    "ContentService",
    "CommentService",
    "SeriesService",
    "VideoService",
]


def __getattr__(name: str):
    if name == "SearchService":
        return SearchService
    if name == "ContentService":
        return ContentService
    if name == "CommentService":
        return CommentService
    if name == "SeriesService":
        return SeriesService
    if name == "VideoService":
        return VideoService
    raise AttributeError(name)


def normalize_search_query(raw_query: str) -> str:
    return SearchService.normalize_search_query(raw_query)


def search_courses(raw_query: str):
    return SearchService.search_courses(raw_query)


def search_blogs(raw_query: str):
    return SearchService.search_blogs(raw_query)


def list_blog_categories():
    return SearchService.list_blog_categories()


class HomeException(Exception):
    """Base exception for home domain errors."""


class SearchValidationException(HomeException):
    """Raised when a search query is invalid."""


class CommentSubmissionException(HomeException):
    """Raised when a comment or reply cannot be stored."""


class SeriesAccessDeniedException(HomeException):
    """Raised when a user cannot access a series or episode."""


class VideoStreamException(HomeException):
    """Raised when a video file cannot be streamed."""


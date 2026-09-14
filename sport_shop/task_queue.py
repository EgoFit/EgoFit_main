from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class TaskQueueUnavailable(RuntimeError):
    """Raised when a background task cannot be queued."""


try:
    from celery import shared_task as _celery_shared_task
except ImportError:  # pragma: no cover - exercised only without optional dependency
    _celery_shared_task = None


def shared_task(*task_args: Any, **task_kwargs: Any):
    if _celery_shared_task is not None:
        return _celery_shared_task(*task_args, **task_kwargs)

    def decorator(function: Callable[..., Any]):
        @wraps(function)
        def delay(*args: Any, **kwargs: Any):
            message = (
                f"Cannot queue task {function.__module__}.{function.__name__}; "
                "install Celery, configure CELERY_BROKER_URL, and run a worker."
            )
            raise TaskQueueUnavailable(message)

        function.delay = delay
        return function

    return decorator


def _queue_is_required() -> bool:
    return bool(getattr(settings, "DJANGO_TASK_QUEUE_REQUIRED", True))


def dispatch_task(task: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return task(*args, **kwargs)

    delay = getattr(task, "delay", None)
    if not callable(delay):
        raise TaskQueueUnavailable(f"Task {task!r} does not expose a queue interface.")

    try:
        return delay(*args, **kwargs)
    except TaskQueueUnavailable:
        if _queue_is_required():
            raise
        logger.warning(
            "Background task %s is unavailable; running it inline.",
            getattr(task, "__name__", task),
        )
        return task(*args, **kwargs)
    except Exception as exc:
        if not _queue_is_required():
            logger.warning(
                "Background task %s could not be queued; running it inline: %s",
                getattr(task, "__name__", task),
                exc,
            )
            return task(*args, **kwargs)
        logger.exception("Unable to enqueue background task %s.", getattr(task, "__name__", task))
        raise TaskQueueUnavailable("صف کارهای پس‌زمینه در دسترس نیست.") from exc

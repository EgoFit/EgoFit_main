# Development Handoff

Last updated: 2026-08-31

## Current State

The Django project is configured for local SQLite development and production deployment with optional Redis/Celery background jobs and resilient Liara media storage.

## Completed Work

- Made the Celery app import optional when the dependency is unavailable.
- Added queue dispatch fallback controlled by `DJANGO_TASK_QUEUE_REQUIRED`.
- Routed OTP, session, notification, and course notification jobs through the shared dispatcher.
- Corrected the Ghasedak OTP request payload to use `receptors` and `inputs`.
- Changed default static and media paths to project-local directories.
- Separated public Liara URL generation from credential-required remote storage I/O.
- Added the Celery worker command and related environment variables to `README.md`.

## Validation

- `107` Django tests pass with `python manage.py test --noinput`.
- `python manage.py check --deploy` passes with production-style settings.
- `python manage.py makemigrations account cart home --check --dry-run` reports no project migration changes.
- Python compilation completes successfully for the project apps.

## Local Setup

Use the project `.venv` with Python 3.12. For local development, set `DJANGO_DEBUG=true` and `DJANGO_USE_SQLITE=true`. Set `DJANGO_TASKS_RUN_INLINE=true` when a Redis worker is not running.

For production, configure `.env`, Redis, and run:

```bash
celery -A sport_shop worker --loglevel=INFO
```

## Follow-Up

The third-party `admin_persian` package reports its own migration drift when all apps are checked; the generated migration is outside the project and was not modified.

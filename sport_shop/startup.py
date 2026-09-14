from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from time import time

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

logger = logging.getLogger(__name__)

STARTUP_LOCK_NAME = "startup-migrate.lock"
STARTUP_LOCK_STALE_SECONDS = int(os.getenv("DJANGO_STARTUP_MIGRATE_LOCK_TTL", "300"))


def _startup_lock_path() -> Path:
    tmp_dir = Path(getattr(settings, "BASE_DIR", Path.cwd())) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir / STARTUP_LOCK_NAME


@contextmanager
def _exclusive_lock(path: Path):
    fd = None
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        yield True
    except FileExistsError:
        try:
            if time() - path.stat().st_mtime > STARTUP_LOCK_STALE_SECONDS:
                path.unlink(missing_ok=True)
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                yield True
                return
        except OSError:
            pass
        yield False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def _has_pending_migrations() -> bool:
    executor = MigrationExecutor(connections["default"])
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    return bool(plan)


def ensure_database_ready() -> bool:
    if not getattr(settings, "DJANGO_AUTO_MIGRATE_ON_STARTUP", False):
        logger.debug("Startup migration disabled; run manage.py migrate during deployment.")
        return False

    if not apps.ready:
        logger.debug("Startup migration skipped because Django app registry is not ready.")
        return False

    if not _has_pending_migrations():
        return False

    lock_path = _startup_lock_path()
    with _exclusive_lock(lock_path) as acquired:
        if not acquired:
            return False

        if not _has_pending_migrations():
            return False

        logger.info("Applying pending database migrations on startup.")
        call_command("migrate", interactive=False, verbosity=0)
        return True


def ensure_static_files_ready() -> bool:
    if not getattr(settings, "DJANGO_AUTO_COLLECTSTATIC_ON_STARTUP", False):
        logger.debug("Startup collectstatic disabled; run manage.py collectstatic during deployment.")
        return False

    if not apps.ready:
        logger.debug("Startup collectstatic skipped because Django app registry is not ready.")
        return False

    lock_path = _startup_lock_path().with_name("startup-collectstatic.lock")
    with _exclusive_lock(lock_path) as acquired:
        if not acquired:
            return False

        logger.info("Collecting static files on startup.")
        call_command("collectstatic", interactive=False, verbosity=0)
        return True

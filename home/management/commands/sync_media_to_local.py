from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db.models import FileField


class Command(BaseCommand):
    help = "Sync media files referenced in the database from remote storage into local MEDIA_ROOT."

    def _safe_text(self, value):
        text = str(value)
        encoding = getattr(self.stdout, "encoding", None) or "utf-8"
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report files that would be synchronized.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Re-fetch files even if a local copy already exists.",
        )
        parser.add_argument(
            "--app",
            dest="app_label",
            help="Limit synchronization to a specific Django app label.",
        )

    def handle(self, *args, **options):
        fetch_remote = getattr(default_storage, "fetch_remote_to_local", None)
        if not callable(fetch_remote):
            self.stderr.write(self.style.ERROR(self._safe_text("Default storage does not support remote-to-local sync.")))
            return

        dry_run = options["dry_run"]
        overwrite = options["overwrite"]
        app_label = options.get("app_label")

        scanned = 0
        synced = 0
        skipped = 0
        missing = 0
        failed = 0
        seen_names = set()

        for model in apps.get_models():
            if app_label and model._meta.app_label != app_label:
                continue

            file_fields = [field for field in model._meta.get_fields() if isinstance(field, FileField)]
            if not file_fields:
                continue

            field_names = [field.name for field in file_fields]
            queryset = model._default_manager.only("pk", *field_names).iterator(chunk_size=200)

            for instance in queryset:
                for field_name in field_names:
                    file_field = getattr(instance, field_name, None)
                    file_name = getattr(file_field, "name", "")
                    if not file_name or file_name in seen_names:
                        continue

                    seen_names.add(file_name)
                    scanned += 1

                    local_file = Path(settings.MEDIA_ROOT) / file_name
                    if not overwrite and local_file.exists():
                        skipped += 1
                        continue

                    if dry_run:
                        self.stdout.write(self._safe_text(f"would-sync {file_name}"))
                        continue

                    try:
                        if fetch_remote(file_name):
                            synced += 1
                            self.stdout.write(self.style.SUCCESS(self._safe_text(f"synced {file_name}")))
                        else:
                            missing += 1
                            self.stdout.write(self.style.WARNING(self._safe_text(f"missing {file_name}")))
                    except Exception as exc:
                        failed += 1
                        self.stderr.write(self.style.ERROR(self._safe_text(f"failed {file_name}: {exc}")))

        summary = (
            f"scan={scanned} synced={synced} skipped={skipped} "
            f"missing={missing} failed={failed} dry_run={dry_run}"
        )
        self.stdout.write(self._safe_text(summary))

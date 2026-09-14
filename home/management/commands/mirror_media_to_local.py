from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models

from sport_shop.storage_backends import (
    ensure_local_media_from_assets,
    get_local_media_path,
    mirror_content_to_local,
)


class Command(BaseCommand):
    help = "Mirror all database-backed media files into local MEDIA_ROOT for fallback serving."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-copy files even if a local mirror already exists.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        mirrored = 0
        skipped = 0
        failed = 0

        for model in apps.get_models():
            file_fields = [
                field for field in model._meta.get_fields()
                if isinstance(field, (models.FileField, models.ImageField))
            ]

            if not file_fields:
                continue

            for instance in model.objects.all().iterator():
                for field in file_fields:
                    bound_file = getattr(instance, field.name, None)
                    file_name = getattr(bound_file, "name", "")

                    if not file_name:
                        continue

                    local_path = get_local_media_path(file_name)
                    if local_path and local_path.exists() and not force:
                        skipped += 1
                        continue

                    try:
                        asset_path = ensure_local_media_from_assets(file_name)
                        if asset_path and asset_path.exists():
                            mirrored += 1
                            continue

                        if hasattr(bound_file, "open"):
                            bound_file.open("rb")
                            mirror_content_to_local(file_name, bound_file)
                            bound_file.close()
                            mirrored += 1
                            continue

                        failed += 1
                        self.stdout.write(self.style.WARNING(f"Could not mirror: {model.__name__}.{field.name} -> {file_name}"))
                    except Exception as exc:
                        failed += 1
                        self.stdout.write(self.style.ERROR(f"Mirror failed for {model.__name__}.{field.name} -> {file_name}: {exc}"))

        self.stdout.write(self.style.SUCCESS(
            f"Media mirror finished. mirrored={mirrored}, skipped={skipped}, failed={failed}"
        ))

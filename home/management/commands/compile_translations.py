from pathlib import Path

import polib
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Compile hand-maintained locale/<lang>/LC_MESSAGES/django.po files into .mo catalogs "
        "using polib, without requiring the GNU gettext toolchain (msgfmt) to be installed."
    )

    def handle(self, *args, **options):
        locale_paths = [Path(path) for path in settings.LOCALE_PATHS]
        compiled = 0

        for locale_root in locale_paths:
            if not locale_root.exists():
                continue
            for po_path in sorted(locale_root.glob("*/LC_MESSAGES/django.po")):
                mo_path = po_path.with_suffix(".mo")
                try:
                    po_file = polib.pofile(str(po_path))
                except OSError as exc:
                    raise CommandError(f"Could not read {po_path}: {exc}") from exc

                po_file.save_as_mofile(str(mo_path))
                compiled += 1
                self.stdout.write(self.style.SUCCESS(f"Compiled {po_path} -> {mo_path}"))

        if not compiled:
            self.stdout.write(self.style.WARNING("No .po files found under LOCALE_PATHS."))

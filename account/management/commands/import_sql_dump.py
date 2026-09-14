from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import sqlparse
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+`(?P<table>[^`]+)`\s*"
    r"\((?P<columns>.*?)\)\s*VALUES\s*(?P<values>.*?);?\s*$",
    re.IGNORECASE | re.DOTALL,
)

# These tables contain framework bookkeeping, authentication/session state, or
# one-time credentials. They must not overwrite the live application's state.
SKIPPED_TABLES = frozenset(
    {
        "account_otp",
        "account_usersession",
        "django_admin_log",
        "django_content_type",
        "django_migrations",
        "django_session",
        "auth_permission",
    }
)


def _split_rows(values_sql: str) -> list[list[str]]:
    rows: list[list[str]] = []
    index = 0
    length = len(values_sql)

    while index < length:
        while index < length and (values_sql[index].isspace() or values_sql[index] == ","):
            index += 1
        if index >= length:
            break
        if values_sql[index] != "(":
            raise ValueError(f"Unexpected SQL near: {values_sql[index:index + 40]!r}")
        index += 1

        row: list[str] = []
        token: list[str] = []
        in_quote = False
        nested_parentheses = 0

        while index < length:
            char = values_sql[index]
            if in_quote:
                token.append(char)
                if char == "\\" and index + 1 < length:
                    index += 1
                    token.append(values_sql[index])
                elif char == "'":
                    if index + 1 < length and values_sql[index + 1] == "'":
                        index += 1
                        token.append(values_sql[index])
                    else:
                        in_quote = False
                index += 1
                continue

            if char == "'":
                in_quote = True
                token.append(char)
            elif char == "(":
                nested_parentheses += 1
                token.append(char)
            elif char == ")":
                if nested_parentheses:
                    nested_parentheses -= 1
                    token.append(char)
                else:
                    row.append("".join(token).strip())
                    index += 1
                    break
            elif char == "," and nested_parentheses == 0:
                row.append("".join(token).strip())
                token = []
            else:
                token.append(char)
            index += 1
        else:
            raise ValueError("Unterminated INSERT row")

        rows.append(row)

    return rows


def _decode_mysql_string(token: str) -> str:
    value = token[1:-1]
    decoded: list[str] = []
    index = 0
    escape_map = {
        "0": "\0",
        "b": "\b",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "Z": "\x1a",
        "\\": "\\",
        "'": "'",
        '"': '"',
    }
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            index += 1
            decoded.append(escape_map.get(value[index], value[index]))
        else:
            decoded.append(char)
        index += 1
    return "".join(decoded)


def _decode_value(token: str):
    if token.upper() == "NULL":
        return None
    if len(token) >= 2 and token[0] == "'" and token[-1] == "'":
        return _decode_mysql_string(token)
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if re.fullmatch(r"-?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?", token):
        number = float(token)
        return number if math.isfinite(number) else None
    return token


def _parse_insert(statement: str) -> tuple[str, list[str], list[list[object]]] | None:
    match = INSERT_RE.search(statement)
    if not match:
        return None
    table = match.group("table")
    columns = [part.strip().strip("`") for part in match.group("columns").split(",")]
    rows = [[_decode_value(token) for token in row] for row in _split_rows(match.group("values"))]
    if any(len(row) != len(columns) for row in rows):
        raise ValueError(f"Column/value count mismatch in {table}")
    return table, columns, rows


def _quote(identifier: str) -> str:
    return connection.ops.quote_name(identifier)


class Command(BaseCommand):
    help = "Import a MariaDB/phpMyAdmin SQL dump into the live Django database idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            "dump_path",
            nargs="?",
            default=str(Path.cwd() / "egofitir_EgoFit_App.sql"),
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("This importer currently targets the project's SQLite database.")

        dump_path = Path(options["dump_path"]).resolve()
        if not dump_path.is_file():
            raise CommandError(f"SQL dump not found: {dump_path}")

        table_rows = self._read_dump(dump_path)
        model_by_table = {
            model._meta.db_table: model
            for model in apps.get_models(include_auto_created=True)
        }
        live_tables = {
            table.name
            for table in connection.introspection.get_table_list(connection.cursor())
        }
        importable = {
            table: rows
            for table, rows in table_rows.items()
            if table not in SKIPPED_TABLES and table in live_tables
        }
        unknown_tables = sorted(set(table_rows) - set(live_tables))
        skipped = sorted(set(table_rows) & SKIPPED_TABLES)

        if unknown_tables:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {len(unknown_tables)} dump tables absent from the current schema: "
                    + ", ".join(unknown_tables)
                )
            )
        if skipped:
            self.stdout.write(
                f"Skipped framework/runtime tables: {', '.join(skipped)}"
            )

        column_map = {
            table: self._live_columns(table)
            for table in importable
        }
        fk_map = {
            table: self._foreign_key_columns(model_by_table.get(table))
            for table in importable
        }
        field_map = {
            table: self._model_fields(model_by_table.get(table))
            for table in importable
        }
        id_map = self._build_id_map(importable, model_by_table, column_map)

        if options["dry_run"]:
            stats = self._simulate(importable, column_map, id_map)
        else:
            stats = self._import(importable, column_map, field_map, fk_map, id_map)
        self._print_stats(stats)

    @staticmethod
    def _read_dump(dump_path: Path) -> dict[str, list[dict[str, object]]]:
        statements = sqlparse.split(dump_path.read_text(encoding="utf-8", errors="replace"))
        table_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
        for statement in statements:
            parsed = _parse_insert(statement)
            if parsed is None:
                continue
            table, columns, rows = parsed
            table_rows[table].extend(dict(zip(columns, row)) for row in rows)
        return dict(table_rows)

    @staticmethod
    def _live_columns(table: str) -> set[str]:
        description = connection.introspection.get_table_description(connection.cursor(), table)
        return {column.name for column in description}

    @staticmethod
    def _foreign_key_columns(model) -> dict[str, str]:
        if model is None:
            return {}
        result = {}
        for field in model._meta.local_fields:
            if field.remote_field is not None:
                result[field.column] = field.remote_field.model._meta.db_table
        return result

    @staticmethod
    def _model_fields(model) -> dict[str, object]:
        if model is None:
            return {}
        return {
            field.column: field
            for field in model._meta.local_fields
        }

    def _build_id_map(self, table_rows, model_by_table, column_map):
        """Map source IDs to live IDs, including natural-key duplicates."""
        id_map: dict[str, dict[object, object]] = defaultdict(dict)
        with connection.cursor() as cursor:
            for table, rows in table_rows.items():
                if "id" not in column_map[table]:
                    continue
                model = model_by_table.get(table)
                unique_fields = self._natural_key_fields(model, column_map[table])
                for row in rows:
                    source_id = row.get("id")
                    if source_id is None:
                        continue
                    source_id = int(source_id)
                    actual_id = self._existing_id_by_pk(cursor, table, source_id)
                    if actual_id is None and unique_fields:
                        actual_id = self._existing_id_by_natural_key(
                            cursor, table, model, unique_fields, row
                        )
                    id_map[table][source_id] = actual_id if actual_id is not None else source_id
        return id_map

    @staticmethod
    def _natural_key_fields(model, live_columns: set[str]) -> tuple[tuple[str, ...], ...]:
        if model is None:
            return ()
        candidates: list[tuple[str, ...]] = []
        for field in model._meta.local_fields:
            if field.unique and field.column != model._meta.pk.column:
                candidates.append((field.column,))
        for constraint in model._meta.total_unique_constraints:
            columns = tuple(
                model._meta.get_field(field).column
                if isinstance(field, str)
                else field.column
                for field in constraint.fields
            )
            if all(column in live_columns for column in columns):
                candidates.append(columns)
        for fields in model._meta.unique_together:
            columns = tuple(model._meta.get_field(field).column for field in fields)
            if all(column in live_columns for column in columns):
                candidates.append(columns)
        # Preserve declaration order while removing duplicates.
        return tuple(dict.fromkeys(candidates))

    @staticmethod
    def _existing_id_by_pk(cursor, table: str, source_id: int):
        cursor.execute(
            f"SELECT {_quote('id')} FROM {_quote(table)} WHERE {_quote('id')} = %s",
            [source_id],
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def _existing_id_by_natural_key(self, cursor, table, model, candidates, row):
        for columns in candidates:
            values = [row.get(column) for column in columns]
            if any(value in (None, "") for value in values):
                continue
            where = " AND ".join(f"{_quote(column)} = %s" for column in columns)
            cursor.execute(
                f"SELECT {_quote(model._meta.pk.column)} FROM {_quote(table)} WHERE {where} LIMIT 1",
                values,
            )
            match = cursor.fetchone()
            if match:
                return match[0]
        return None

    def _prepare_row(self, table, row, live_columns, fk_map, id_map):
        prepared = {
            column: value
            for column, value in row.items()
            if column in live_columns
        }
        if "id" in prepared and prepared["id"] is not None:
            source_id = int(prepared["id"])
            prepared["id"] = id_map.get(table, {}).get(source_id, source_id)
        for column, target_table in fk_map.items():
            if column in prepared and prepared[column] is not None:
                prepared[column] = id_map.get(target_table, {}).get(
                    int(prepared[column]), prepared[column]
                )
        return prepared

    @staticmethod
    def _values_equal(left, right, field=None) -> bool:
        if left == right:
            return True
        if left is None or right is None:
            return False
        if field is not None:
            try:
                left = field.to_python(left)
                right = field.to_python(right)
            except (TypeError, ValueError, OverflowError):
                pass
        if isinstance(left, (datetime, date)) and isinstance(right, (datetime, date)):
            return left == right
        if isinstance(left, Decimal) or isinstance(right, Decimal):
            try:
                return Decimal(str(left)) == Decimal(str(right))
            except (ValueError, TypeError):
                pass
        return str(left) == str(right)

    def _simulate(self, table_rows, column_map, id_map):
        stats = Counter()
        with connection.cursor() as cursor:
            for table, rows in table_rows.items():
                for row in rows:
                    prepared = self._prepare_row(table, row, column_map[table], {}, id_map)
                    stats["rows"] += 1
                    if prepared.get("id") is not None:
                        cursor.execute(
                            f"SELECT 1 FROM {_quote(table)} WHERE {_quote('id')} = %s",
                            [prepared["id"]],
                        )
                        exists = cursor.fetchone() is not None
                    else:
                        exists = False
                    stats["would_update" if exists else "would_insert"] += 1
        return stats

    def _import(self, table_rows, column_map, field_map, fk_map, id_map):
        stats = Counter()
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_keys = OFF")
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    for table, rows in table_rows.items():
                        for row in rows:
                            prepared = self._prepare_row(
                                table, row, column_map[table], fk_map[table], id_map
                            )
                            if not prepared:
                                stats["skipped"] += 1
                                continue
                            columns = list(prepared)
                            values = [prepared[column] for column in columns]
                            pk = prepared.get("id")
                            if pk is not None and "id" in column_map[table]:
                                select_columns = ", ".join(
                                    _quote(column) for column in columns
                                )
                                cursor.execute(
                                    f"SELECT {select_columns} FROM {_quote(table)} "
                                    f"WHERE {_quote('id')} = %s",
                                    [pk],
                                )
                                existing_row = cursor.fetchone()
                                exists = existing_row is not None
                            else:
                                existing_row = None
                                exists = False
                            if exists:
                                current_values = dict(zip(columns, existing_row))
                                if all(
                                    self._values_equal(
                                        current_values[column],
                                        prepared[column],
                                        field_map[table].get(column),
                                    )
                                    for column in columns
                                ):
                                    stats["unchanged"] += 1
                                    stats["rows"] += 1
                                    continue
                                update_columns = [column for column in columns if column != "id"]
                                if update_columns:
                                    assignments = ", ".join(
                                        f"{_quote(column)} = %s" for column in update_columns
                                    )
                                    update_values = [prepared[column] for column in update_columns]
                                    update_values.append(pk)
                                    cursor.execute(
                                        f"UPDATE {_quote(table)} SET {assignments} "
                                        f"WHERE {_quote('id')} = %s",
                                        update_values,
                                    )
                                stats["updated"] += 1
                            else:
                                quoted_columns = ", ".join(_quote(column) for column in columns)
                                placeholders = ", ".join("%s" for _ in columns)
                                cursor.execute(
                                    f"INSERT INTO {_quote(table)} ({quoted_columns}) "
                                    f"VALUES ({placeholders})",
                                    values,
                                )
                                stats["inserted"] += 1
                            stats["rows"] += 1
                    self._repair_sequences(cursor, table_rows, column_map)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA foreign_keys = ON")
        return stats

    @staticmethod
    def _repair_sequences(cursor, table_rows, column_map):
        for table in table_rows:
            if "id" not in column_map[table]:
                continue
            cursor.execute(
                f"SELECT MAX({_quote('id')}) FROM {_quote(table)}"
            )
            maximum = cursor.fetchone()[0]
            if maximum is None:
                continue
            cursor.execute(
                "UPDATE sqlite_sequence SET seq = %s WHERE name = %s",
                [maximum, table],
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO sqlite_sequence(name, seq) VALUES (%s, %s)",
                    [table, maximum],
                )

    @staticmethod
    def _print_stats(stats: Counter):
        if not stats:
            return
        summary = ", ".join(f"{key}={value}" for key, value in sorted(stats.items()))
        # Counter keys are intentionally plain English because this command is
        # also used in deployment logs.
        print(f"SQL dump import summary: {summary}")

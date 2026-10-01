"""Parsing and validation helpers for exercise-library prescriptions."""

from __future__ import annotations

import re


_PYRAMID = "pyramid"
_REVERSE_PYRAMID = "reverse_pyramid"
_TWENTY_ONE_REPS = "21_reps"
_LOW_TO_HIGH = "low_to_high"
_HIGH_TO_LOW = "high_to_low"


_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_OPTIONAL_SET_UNIT = r"(?:\s*(?:sets?|ست))?"
_OPTIONAL_REP_UNIT = r"(?:\s*(?:reps?|تکرار))?"
_RANGE_SEPARATOR = r"(?:-|–|—|تا|to)"


def parse_set_prescription(value: object) -> tuple[int, int] | None:
    """Return the inclusive minimum/maximum for a set count such as ``۳`` or ``2-3``."""
    text = str(value or "").translate(_DIGIT_MAP).strip().casefold()
    match = re.fullmatch(
        rf"(\d+)(?:\s*{_RANGE_SEPARATOR}\s*(\d+))?{_OPTIONAL_SET_UNIT}",
        text,
    )
    if not match:
        return None
    minimum = int(match.group(1))
    maximum = int(match.group(2) or minimum)
    if minimum < 1 or maximum < minimum:
        return None
    return minimum, maximum


def _rep_sequence(value: object) -> list[int] | None:
    text = str(value or "").translate(_DIGIT_MAP).strip().casefold()
    # Dashes are sequences only with three or more values, so 8-12 stays a range.
    parts = re.split(r"\s*(?:/|,|،|;|؛|\+|→|->)\s*", text)
    if len(parts) == 1:
        parts = re.split(r"\s*-\s*", text)
        if len(parts) < 3:
            return None
    if len(parts) < 2 or len(parts) > 8:
        return None
    if any(not re.fullmatch(r"\d+", part) for part in parts):
        return None
    numbers = [int(part) for part in parts]
    return numbers if all(number > 0 for number in numbers) else None


def _is_simple_rep_range(value: object) -> bool:
    text = str(value or "").translate(_DIGIT_MAP).strip().casefold()
    match = re.fullmatch(
        rf"(\d+)(?:\s*{_RANGE_SEPARATOR}\s*(\d+))?{_OPTIONAL_REP_UNIT}",
        text,
    )
    if not match:
        return False
    minimum = int(match.group(1))
    maximum = int(match.group(2) or minimum)
    return minimum > 0 and maximum >= minimum


def is_valid_repetition_prescription(value: object, method: str) -> bool:
    """Validate a rep range or the direction-specific sequence a method requires."""
    if method == _TWENTY_ONE_REPS:
        return _rep_sequence(value) == [7, 7, 7]
    if method in {
        _PYRAMID,
        _REVERSE_PYRAMID,
        _LOW_TO_HIGH,
        _HIGH_TO_LOW,
    }:
        sequence = _rep_sequence(value)
        if not sequence:
            return False
        ascending = method in {
            _REVERSE_PYRAMID,
            _LOW_TO_HIGH,
        }
        compare = (lambda first, second: first <= second) if ascending else (lambda first, second: first >= second)
        return all(compare(first, second) for first, second in zip(sequence, sequence[1:]))
    return _is_simple_rep_range(value)

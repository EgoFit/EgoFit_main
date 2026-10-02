"""Estimated heart-rate targets for general adult training guidance."""

from __future__ import annotations

SUPPORTED_AGE_RANGE = (18, 80)

TRAINING_INTENSITIES = (
    ("fat_loss", 40, 59),
    ("cardiorespiratory_endurance", 60, 79),
    ("anaerobic_power", 85, 95),
)


def estimate_max_heart_rate(age: int, gender: str) -> int | None:
    """Estimate HRmax using adult equations validated for the recorded sex."""
    try:
        age = int(age)
    except (TypeError, ValueError):
        return None

    if not SUPPORTED_AGE_RANGE[0] <= age <= SUPPORTED_AGE_RANGE[1]:
        return None

    if gender == "female":
        estimate = 206 - (0.88 * age)
    elif gender == "male":
        estimate = 208 - (0.7 * age)
    else:
        return None

    return int(round(estimate))


def calculate_target_heart_rate_zones(
    *, age: int, gender: str, resting_heart_rate_bpm: int
) -> dict | None:
    """Return estimated Karvonen/HRR targets, or None for invalid inputs.

    HRR = estimated HRmax - resting HR
    Target HR = resting HR + (% intensity x HRR)
    """
    try:
        resting_heart_rate_bpm = int(resting_heart_rate_bpm)
    except (TypeError, ValueError):
        return None

    max_heart_rate = estimate_max_heart_rate(age, gender)
    if max_heart_rate is None or not 30 <= resting_heart_rate_bpm <= 220:
        return None

    heart_rate_reserve = max_heart_rate - resting_heart_rate_bpm
    if heart_rate_reserve <= 0:
        return None

    zones = []
    for key, lower_percent, upper_percent in TRAINING_INTENSITIES:
        lower_bpm = round(resting_heart_rate_bpm + heart_rate_reserve * lower_percent / 100)
        upper_bpm = round(resting_heart_rate_bpm + heart_rate_reserve * upper_percent / 100)
        upper_bpm = max(lower_bpm, upper_bpm)
        zones.append(
            {
                "key": key,
                "lower_percent": lower_percent,
                "upper_percent": upper_percent,
                "lower_bpm": lower_bpm,
                "upper_bpm": upper_bpm,
            }
        )

    return {
        "max_heart_rate_bpm": max_heart_rate,
        "heart_rate_reserve_bpm": heart_rate_reserve,
        "zones": zones,
    }

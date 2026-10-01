from __future__ import annotations

from collections import defaultdict
import random
from typing import Any, Iterable, Mapping, Sequence

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from account.domain.workout_prescriptions import (
    is_valid_repetition_prescription,
    parse_set_prescription,
)
from account.models import (
    CorrectiveExercise,
    Exercise,
    ExerciseDifficultyLevel,
    ExerciseMovementType,
    ExerciseSecondaryMovementType,
    ExerciseSetType,
    ExerciseRepetitionType,
    ExerciseRestType,
    ExerciseTrainingMethod,
)


class AutomaticProgramService:
    """Build a conservative, editable workout payload from the exercise library.

    The generator only selects catalogued values and never invents exercise
    records. Its defaults and selection rules are part of the prescription
    contract, so changes should preserve the returned payload shape and be
    validated with ``account.tests_gym_programs``.
    """

    DIFFICULTY_ALIASES: dict[int, tuple[str, ...]] = {
        0: (
            "beginner",
            "novice",
            "basic",
            "مبتدی",
            "ابتدایی",
            "آسان",
        ),
        1: (
            "intermediate",
            "medium",
            "moderate",
            "متوسط",
            "میانی",
        ),
        2: (
            "advanced",
            "difficult",
            "hard",
            "expert",
            "پیشرفته",
            "دشوار",
            "سخت",
        ),
    }

    GOAL_ALIASES: dict[str, tuple[str, ...]] = {
        "strength": ("strength", "قدرت"),
        "volume": ("volume", "hypertrophy", "muscle gain", "حجم"),
        "endurance": ("endurance", "استقامت"),
        "fat_burning": ("fat_burning", "fat burn", "fat-burning", "چربی سوزی", "چربی‌سوزی"),
        "power": ("power", "توان"),
        "general": ("general", "عمومی", "تناسب عمومی"),
    }
    POWER_TYPE_ALIASES = ("power", "توان", "توانی", "explosive")
    COMPOUND_JOINT_ALIASES = (
        "compound",
        "multi-joint",
        "multijoint",
        "چند مفصلی",
        "چندمفصلی",
    )
    SECTION_ALIASES = {
        "chest": ("chest", "سینه"),
        "shoulders": ("shoulders", "shoulder", "سرشانه", "شانه"),
        "triceps": ("triceps", "tricep", "پشت بازو"),
        "legs": ("legs", "leg", "پا"),
        "glutes": ("glutes", "glute", "سرینی", "باسن"),
        "calves": ("calves", "calf", "ساق"),
        "abs": ("abs", "abdomen", "abdominal", "شکم"),
        "lower_back": ("lower back", "بخش پایینی پشت"),
        "lumbar": ("lumbar", "فیله", "کمر", "راست‌کننده ستون فقرات"),
        "upper_back": ("upper back", "بخش بالایی پشت"),
        "biceps": ("biceps", "bicep", "جلو بازو"),
    }
    PATTERN_ALIASES = {
        "push": ("push", "هل دادن", "هل‌دادن"),
        "pull": ("pull", "کشیدن"),
        "legs": ("legs", "leg", "پا"),
        "core": ("core", "central", "مرکزی بدن"),
    }
    METHOD_NOTES = {
        ExerciseTrainingMethod.PYRAMID: "Pyramid: بار به‌تدریج بیشتر و تکرار کمتر می‌شود.",
        ExerciseTrainingMethod.REVERSE_PYRAMID: "Reverse Pyramid: پس از ست سنگین، بار کمتر و تکرار بیشتر می‌شود.",
        ExerciseTrainingMethod.TWENTY_ONE_REPS: "21 Reps: ۷ تکرار نیمه پایین + ۷ تکرار نیمه بالا + ۷ تکرار کامل.",
        ExerciseTrainingMethod.DROP_SET: "Drop Set: پس از ست اصلی، بار کاهش می‌یابد و تکرار ادامه پیدا می‌کند.",
        ExerciseTrainingMethod.LOW_TO_HIGH: "Low To High: از تکرار کم و بار سنگین به تکرار بیشتر و بار سبک‌تر بروید.",
        ExerciseTrainingMethod.HIGH_TO_LOW: "High To Low: از تکرار زیاد و بار سبک به تکرار کمتر و بار سنگین‌تر بروید.",
    }

    @classmethod
    def build_session_targets(
        cls,
        *,
        program_type: str,
        sessions: int,
        current_targets: Sequence[dict[str, Any]] | None = None,
        selected_ids: Sequence[int] | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        session_count = int(sessions)
        if program_type == "normal":
            targets = list(current_targets or [])[:session_count]
            while len(targets) < session_count:
                targets.append({"name": f"روز {len(targets) + 1}", "targets": [], "patterns": []})
            return targets, sorted(
                {
                    str(entry.get("movement_type"))
                    for session in targets
                    for entry in session.get("targets", [])
                    if entry.get("movement_type")
                }
            )

        if program_type == "split" and session_count not in {3, 4, 5, 6}:
            raise ValidationError(_("Split فقط برای ۳ تا ۶ جلسه در هفته قالب آماده دارد."))
        if program_type == "push_pull_legs" and session_count not in {3, 6}:
            raise ValidationError(_("Push/Pull/Leg برای ۳ یا ۶ جلسه در هفته قابل استفاده است."))

        split_presets = {
            3: [
                ("سینه، سرشانه و پشت بازو", {"chest": 3, "shoulders": 3, "triceps": 2}),
                ("پا، باسن، ساق، شکم و کمر", {"legs": 3, "glutes": 1, "calves": 1, "abs": 1, "lumbar": 1}),
                ("پشت و جلو بازو", {"upper_back": 3, "lower_back": 3, "biceps": 2}),
            ],
            4: [
                ("سینه و پشت بازو", {"chest": 4, "triceps": 3, "abs": 1}),
                ("پشت و جلو بازو", {"lower_back": 4, "biceps": 3, "lumbar": 1}),
                ("پا", {"legs": 4, "glutes": 1, "calves": 1, "abs": 1}),
                ("سرشانه و پشت", {"shoulders": 4, "upper_back": 3, "lumbar": 1}),
            ],
            5: [
                ("سینه و پشت بازو", {"chest": 5, "triceps": 2}),
                ("پشت و جلو بازو", {"lower_back": 5, "biceps": 2}),
                ("پا", {"legs": 5, "glutes": 1, "calves": 2}),
                ("سرشانه، پشت بازو و شکم", {"shoulders": 5, "triceps": 1, "abs": 2}),
                ("پشت، جلو بازو و کمر", {"upper_back": 5, "biceps": 1, "lumbar": 2}),
            ],
            6: [
                ("سینه و شکم", {"chest": 6, "abs": 2}),
                ("پشت و کمر", {"lower_back": 6, "lumbar": 2}),
                ("پا", {"legs": 5, "glutes": 2, "calves": 2}),
                ("سرشانه و شکم", {"shoulders": 6, "abs": 2}),
                ("پشت و کمر", {"upper_back": 6, "lumbar": 2}),
                ("بازو", {"biceps": 4, "triceps": 4}),
            ],
        }

        if program_type == "split":
            days = [
                cls._section_target_day(name, counts)
                for name, counts in split_presets[session_count]
            ]
        elif program_type == "full_body":
            sections = ExerciseSecondaryMovementType.objects.filter(
                exercises__isnull=False
            ).distinct().order_by("pk")
            days = [
                {
                    "name": f"تمام بدن — روز {index + 1}",
                    "targets": [
                        {"movement_type": str(section.pk), "count": 1}
                        for section in sections
                    ],
                    "patterns": [],
                }
                for index in range(session_count)
            ]
            if not days or not days[0]["targets"]:
                raise ValidationError(_("برای Full Body بخش‌های هدف دارای حرکت پیدا نشدند."))
        elif program_type == "push_pull":
            days = []
            for index in range(session_count):
                push = index % 2 == 0
                pattern_key = "push" if push else "pull"
                days.append(
                    cls._pattern_target_day(
                        "Push" if push else "Pull",
                        {pattern_key: 6, "legs": 2, "core": 1},
                    )
                )
        elif program_type == "push_pull_legs":
            base_days = [
                cls._pattern_target_day(
                    "Push",
                    {"push": 6},
                    section_counts={"abs": 2},
                ),
                cls._pattern_target_day(
                    "Pull",
                    {"pull": 6},
                    section_counts={"abs": 2},
                ),
                cls._section_target_day(
                    "پا و کمر",
                    {"legs": 4, "glutes": 1, "calves": 2, "lumbar": 2},
                ),
            ]
            if session_count == 6:
                days = [
                    {
                        **day,
                        "name": f"{day['name']} — چرخه {cycle}",
                        "targets": [dict(target) for target in day["targets"]],
                        "patterns": [dict(pattern) for pattern in day["patterns"]],
                    }
                    for cycle in (1, 2)
                    for day in base_days
                ]
            else:
                days = base_days
        else:
            raise ValidationError(_("نوع برنامهٔ انتخاب‌شده پشتیبانی نمی‌شود."))

        selected_ids = sorted(
            {
                entry["movement_type"]
                for day in days
                for entry in day.get("targets", [])
            },
            key=int,
        )
        return days, selected_ids

    @classmethod
    def _section_target_day(cls, name: str, counts: Mapping[str, int]) -> dict[str, Any]:
        targets = []
        for key, count in counts.items():
            section = cls._lookup_section(key)
            targets.append({"movement_type": str(section.pk), "count": count})
        return {"name": name, "targets": targets, "patterns": []}

    @classmethod
    def _pattern_target_day(
        cls,
        name: str,
        pattern_counts: Mapping[str, int],
        *,
        section_counts: Mapping[str, int] | None = None,
    ) -> dict[str, Any]:
        targets = []
        for key, count in (section_counts or {}).items():
            section = cls._lookup_section(key)
            targets.append({"movement_type": str(section.pk), "count": count})
        patterns = []
        for key, count in pattern_counts.items():
            pattern = cls._lookup_pattern(key)
            patterns.append(
                {
                    "movement_pattern": str(pattern.pk),
                    "count": count,
                    "label": pattern.name,
                }
            )
        return {"name": name, "targets": targets, "patterns": patterns}

    @classmethod
    def _lookup_section(cls, key: str) -> ExerciseSecondaryMovementType:
        aliases = tuple(cls._normalized_label(value) for value in cls.SECTION_ALIASES[key])
        candidates = ExerciseSecondaryMovementType.objects.filter(
            exercises__isnull=False
        ).distinct().order_by("pk")
        for section in candidates:
            labels = (
                cls._normalized_label(section.name),
                cls._normalized_label(section.name_en),
            )
            if any(
                alias and any(alias == label or (len(alias) > 4 and alias in label) for label in labels)
                for alias in aliases
            ):
                return section
        raise ValidationError(
            _("بخش «%(section)s» یا حرکت‌های ثبت‌شدهٔ آن در کتابخانه پیدا نشد.")
            % {"section": key}
        )

    @classmethod
    def _lookup_pattern(cls, key: str) -> ExerciseMovementType:
        aliases = tuple(cls._normalized_label(value) for value in cls.PATTERN_ALIASES[key])
        for pattern in ExerciseMovementType.objects.order_by("pk"):
            labels = (
                cls._normalized_label(pattern.name),
                cls._normalized_label(pattern.name_en),
            )
            if any(
                alias and any(alias == label or (len(alias) > 4 and alias in label) for label in labels)
                for alias in aliases
            ):
                return pattern
        raise ValidationError(
            _("الگوی حرکت «%(pattern)s» در کتابخانه پیدا نشد.") % {"pattern": key}
        )

    def generate(
        self,
        *,
        difficulty: ExerciseDifficultyLevel | int,
        gender: str | None,
        abnormalities: Iterable[Any],
        sessions: int,
        movements: int,
        goal: str,
        training_methods: Sequence[str] | None = None,
        secondary_movement_counts: Mapping[Any, Any] | Sequence[Any] | None = None,
        session_movement_targets: Sequence[dict[str, Any]] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Generate editable daily exercise and corrective-item payloads.

        ``difficulty`` accepts either the model instance used by admin forms or
        its primary key. ``secondary_movement_counts`` and
        ``session_movement_targets`` retain both legacy and row-based input
        shapes for compatibility with saved editor payloads.
        """
        selected_ids = self._selected_movement_type_ids(
            secondary_movement_counts,
            session_movement_targets,
        )
        selected_pattern_ids = self._selected_pattern_ids(session_movement_targets)
        movement_type_map = {
            item.pk: item for item in self._secondary_movement_types(selected_ids)
        }
        pattern_type_map = {
            item.pk: item
            for item in ExerciseMovementType.objects.filter(pk__in=selected_pattern_ids)
        }
        selected_ids = [pk for pk in selected_ids if pk in movement_type_map]
        selected_pattern_ids = [pk for pk in selected_pattern_ids if pk in pattern_type_map]
        if not selected_ids and not selected_pattern_ids:
            raise ValidationError(_("برای جلسه‌ها بخش عضله یا الگوی حرکت انتخاب نشده است."))

        prescription_catalogs = self._prescription_catalogs(
            goal,
            ExerciseTrainingMethod.NORMAL,
        )
        requested_methods = list(
            dict.fromkeys(
                method
                for method in (training_methods or [])
                if method in dict(ExerciseTrainingMethod.choices)
                and method != ExerciseTrainingMethod.NORMAL
            )
        )
        method_catalogs = {}
        for method in requested_methods:
            method_catalogs[method] = self._prescription_catalogs(goal, method)
        difficulty_id = getattr(difficulty, "pk", difficulty)
        allowed_difficulty_ids = self._allowed_difficulty_level_ids(difficulty)
        exercise_filter = Q()
        if selected_ids:
            exercise_filter |= Q(secondary_movement_type_id__in=selected_ids)
        if selected_pattern_ids:
            exercise_filter |= Q(movement_type_id__in=selected_pattern_ids)
        queryset = Exercise.objects.select_related(
            "primary_muscle",
            "body_part",
            "joint_type",
            "power_type",
            "difficulty_level",
            "secondary_movement_type",
            "movement_type",
        ).filter(
            exercise_filter,
            difficulty_level_id__in=allowed_difficulty_ids,
        )
        exercises = list(queryset)
        by_target = defaultdict(list)
        preferred_by_target = defaultdict(list)
        for exercise in exercises:
            if exercise.secondary_movement_type_id:
                key = ("section", exercise.secondary_movement_type_id)
                by_target[key].append(exercise)
                if exercise.difficulty_level_id == difficulty_id:
                    preferred_by_target[key].append(exercise)
            if exercise.movement_type_id:
                key = ("pattern", exercise.movement_type_id)
                by_target[key].append(exercise)
                if exercise.difficulty_level_id == difficulty_id:
                    preferred_by_target[key].append(exercise)

        session_plans = self._session_plans(
            sessions=sessions,
            selected_ids=selected_ids,
            secondary_movement_counts=secondary_movement_counts,
            session_movement_targets=session_movement_targets,
            movement_type_map=movement_type_map,
            pattern_type_map=pattern_type_map,
        )
        days = []
        weekly_direct_sets = defaultdict(lambda: [0, 0])
        weekly_direct_section_names = {}
        has_explicit_session_targets = bool(session_movement_targets)
        exercise_by_id = {exercise.pk: exercise for exercise in exercises}
        used_exercise_ids = set()
        rotation_cursors = defaultdict(int)
        has_explicit_movement_counts = isinstance(secondary_movement_counts, dict)
        for day_number, session_plan in enumerate(session_plans, start=1):
            items = []
            session_used_exercise_ids = set()
            shortages = []
            slots = [
                ("section", movement_type_id, count)
                for movement_type_id, count in session_plan["sections"]
            ] + [
                ("pattern", movement_type_id, count)
                for movement_type_id, count in session_plan["patterns"]
            ]
            for target_kind, movement_type_id, count in slots:
                target_key = (target_kind, movement_type_id)
                preferred_pool = preferred_by_target.get(target_key, [])
                pool = by_target.get(target_key, [])
                target_label = (
                    movement_type_map[movement_type_id].name
                    if target_kind == "section" and movement_type_id in movement_type_map
                    else pattern_type_map[movement_type_id].name
                )
                added = 0
                for offset in range(count):
                    if (
                        not has_explicit_session_targets
                        and not has_explicit_movement_counts
                        and len(items) >= int(movements)
                    ):
                        shortages.append(f"{target_label}: {count - added}")
                        break
                    if not pool:
                        shortages.append(f"{target_label}: {count - added}")
                        break
                    exercise = self._pick_varied_exercise(
                        preferred_pool=preferred_pool,
                        pool=pool,
                        used_exercise_ids=used_exercise_ids,
                        session_used_ids=session_used_exercise_ids,
                        cursor=rotation_cursors[target_key],
                    )
                    if exercise is None:
                        shortages.append(f"{target_label}: {count - added}")
                        break
                    rotation_cursors[target_key] += 1
                    used_exercise_ids.add(exercise.pk)
                    session_used_exercise_ids.add(exercise.pk)
                    prescription = self._prescription_for_index(prescription_catalogs, len(items))
                    items.append(
                        {
                            "exercise": exercise.pk,
                            "exercise_name": exercise.name,
                            "goal": goal,
                            "superset_exercise": "",
                            "third_exercise": "",
                            "sets": prescription["sets"],
                            "reps": prescription["reps"],
                            "rest": prescription["rest"],
                            "superset_sets": prescription["sets"],
                            "superset_reps": prescription["reps"],
                            "superset_rest": prescription["rest"],
                            "third_sets": prescription["sets"],
                            "third_reps": prescription["reps"],
                            "third_rest": prescription["rest"],
                            "note": "",
                            "training_method": ExerciseTrainingMethod.NORMAL,
                        }
                    )

            available_methods = [method for method in requested_methods if method_catalogs.get(method)]
            if available_methods and items:
                special_count = random.randint(1, min(2, len(items)))
                for item_index in random.sample(range(len(items)), special_count):
                    method = random.choice(available_methods)
                    prescription = self._prescription_for_index(
                        method_catalogs[method],
                        item_index,
                    )
                    items[item_index].update(
                        {
                            "sets": prescription["sets"],
                            "reps": prescription["reps"],
                            "rest": prescription["rest"],
                            "superset_sets": prescription["sets"],
                            "superset_reps": prescription["reps"],
                            "superset_rest": prescription["rest"],
                            "third_sets": prescription["sets"],
                            "third_reps": prescription["reps"],
                            "third_rest": prescription["rest"],
                            "note": self.METHOD_NOTES[method],
                            "training_method": method,
                        }
                    )
            items = self._order_session_items(items, exercise_by_id)
            for item in items:
                exercise = exercise_by_id[item["exercise"]]
                if exercise.secondary_movement_type_id:
                    minimum_sets, maximum_sets = self._set_count(item.get("sets"))
                    weekly_direct_sets[exercise.secondary_movement_type_id][0] += minimum_sets
                    weekly_direct_sets[exercise.secondary_movement_type_id][1] += maximum_sets
                    weekly_direct_section_names[exercise.secondary_movement_type_id] = (
                        exercise.secondary_movement_type.name
                    )
            day_notes = f"تنظیمات هدف «{goal}»؛ قابل ویرایش توسط ادمین."
            if shortages:
                day_notes += " تعداد حرکت قابل‌تأمین نبود: " + "، ".join(shortages)
            days.append(
                {
                    "name": session_plan["name"] or f"روز {day_number}",
                    "notes": day_notes,
                    "items": items,
                }
            )

        corrective_items = []
        abnormality_ids = [item.pk for item in abnormalities]
        corrective_qs = CorrectiveExercise.objects.select_related("abnormality_type").filter(
            abnormality_type_id__in=abnormality_ids
        )
        for index, corrective in enumerate(corrective_qs[: min(len(abnormality_ids) * 2, 12)], start=1):
            corrective_items.append(
                {
                    "corrective_exercise": corrective.pk,
                    "corrective_exercise_name": corrective.name,
                    "phase": "warmup" if index % 2 else "cooldown",
                    "sets": "2",
                    "reps": "10-12",
                    "note": corrective.abnormality_type.name if corrective.abnormality_type else "",
                }
            )
        volume_warnings = []
        if goal.casefold() in {"volume", "hypertrophy", "muscle gain", "حجم"}:
            for section_id, (minimum_sets, maximum_sets) in weekly_direct_sets.items():
                if maximum_sets < 10:
                    volume_warnings.append(
                        _(
                            "حجم مستقیم هفتگی «%(section)s» حدود %(sets)s ست است؛ "
                            "برای رشد عضله، ۱۰ ست یا بیشتر یک مرجع عمومی است. "
                            "ست‌های غیرمستقیم و شرایط فرد در این برآورد نیستند."
                        )
                        % {
                            "section": weekly_direct_section_names[section_id],
                            "sets": self._format_set_range(minimum_sets, maximum_sets),
                        }
                    )
                elif minimum_sets > 20:
                    volume_warnings.append(
                        _(
                            "حجم مستقیم هفتگی «%(section)s» حدود %(sets)s ست است؛ "
                            "پس از حدود ۱۸ تا ۲۰ ست، بازده افزوده معمولاً کمتر می‌شود. "
                            "ست‌های غیرمستقیم و توان بازیابی در این برآورد نیستند."
                        )
                        % {
                            "section": weekly_direct_section_names[section_id],
                            "sets": self._format_set_range(minimum_sets, maximum_sets),
                        }
                    )
        return {
            "days": days,
            "correctives": corrective_items,
            "warnings": volume_warnings,
        }

    @staticmethod
    def _set_count(value: Any) -> tuple[int, int]:
        """Return a safe weekly-volume estimate for an exact or ranged set count."""
        return parse_set_prescription(value) or (0, 0)

    @staticmethod
    def _format_set_range(minimum: int, maximum: int) -> str:
        return str(minimum) if minimum == maximum else f"{minimum}–{maximum}"

    @classmethod
    def _prescription_catalogs(cls, goal: str, method: str) -> dict[str, list[str]]:
        catalogs = {
            "sets": cls._randomized_catalog(
                cls._lookup_values(ExerciseSetType, "set_count", goal, method)
            ),
            "reps": cls._randomized_catalog(
                cls._lookup_values(ExerciseRepetitionType, "reps", goal, method)
            ),
            "rest": cls._randomized_catalog(
                cls._lookup_values(ExerciseRestType, "rest_time", goal, method)
            ),
        }
        if method in {
            ExerciseTrainingMethod.PYRAMID,
            ExerciseTrainingMethod.REVERSE_PYRAMID,
            ExerciseTrainingMethod.TWENTY_ONE_REPS,
            ExerciseTrainingMethod.LOW_TO_HIGH,
            ExerciseTrainingMethod.HIGH_TO_LOW,
        }:
            catalogs["reps"] = [
                value
                for value in catalogs["reps"]
                if cls._valid_repetition_sequence(value, method)
            ]
        if any(not values for values in catalogs.values()):
            method_label = dict(ExerciseTrainingMethod.choices).get(method, method)
            raise ValidationError(
                _("برای هدف «%(goal)s» و روش «%(method)s» باید ست، تکرار و استراحت در کتابخانه ثبت شود.")
                % {"goal": goal, "method": method_label}
            )
        return catalogs

    @classmethod
    def _valid_repetition_sequence(cls, value: str, method: str) -> bool:
        return is_valid_repetition_prescription(value, method)

    @staticmethod
    def _pick_varied_exercise(
        *,
        preferred_pool: Sequence[Exercise],
        pool: Sequence[Exercise],
        used_exercise_ids: set[int],
        session_used_ids: set[int],
        cursor: int,
    ) -> Exercise | None:
        """Pick an unused movement for the whole program and current session.

        A movement is never prescribed twice in one generated program. This
        keeps repeated body-part sessions varied and also prevents accidental
        duplicates when a target section is repeated inside one session. If the
        library has no unused candidate, ``None`` is returned instead of filling
        a slot with a duplicate.
        """

        def is_available(item):
            return (
                item.pk not in session_used_ids
                and item.pk not in used_exercise_ids
            )

        preferred_unused = [item for item in preferred_pool if is_available(item)]
        if preferred_unused:
            return preferred_unused[cursor % len(preferred_unused)]

        unused = [item for item in pool if is_available(item)]
        if unused:
            return unused[cursor % len(unused)]

        return None

    @staticmethod
    def _randomized_catalog(values: Sequence[str]) -> list[str]:
        """Return unique catalog values in a random order."""
        randomized = list(dict.fromkeys(value for value in values if value))
        random.shuffle(randomized)
        return randomized

    @staticmethod
    def _prescription_for_index(
        catalogs: Mapping[str, Sequence[str]],
        index: int,
        previous: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Choose an independent, goal-specific prescription for each movement."""
        previous = previous or {}
        prescription = {}
        for field, values in catalogs.items():
            if not values:
                continue
            candidates = [value for value in values if value != previous.get(field)]
            prescription[field] = random.choice(candidates or list(values))
        return prescription

    @classmethod
    def _order_session_items(
        cls,
        items: Sequence[dict[str, Any]],
        exercise_by_id: Mapping[int, Exercise],
    ) -> list[dict[str, Any]]:
        """Place power work first, then group each body part compound-first."""
        body_part_order = {}
        indexed_items = []
        for item_index, item in enumerate(items):
            exercise = exercise_by_id[item["exercise"]]
            body_part_order.setdefault(exercise.body_part_id, item_index)
            indexed_items.append((item_index, item, exercise))

        indexed_items.sort(
            key=lambda entry: (
                0 if cls._is_power_exercise(entry[2]) else 1,
                body_part_order[entry[2].body_part_id],
                0 if cls._is_compound_exercise(entry[2]) else 1,
                entry[0],
            )
        )
        return [item for _item_index, item, _exercise in indexed_items]

    @classmethod
    def _is_power_exercise(cls, exercise: Exercise) -> bool:
        """Return whether an exercise has the catalogued explosive-power type."""
        return cls._label_contains(exercise.power_type, cls.POWER_TYPE_ALIASES)

    @classmethod
    def _is_compound_exercise(cls, exercise: Exercise) -> bool:
        """Return whether an exercise targets multiple joints."""
        return cls._label_contains(exercise.joint_type, cls.COMPOUND_JOINT_ALIASES)

    @classmethod
    def _label_contains(cls, value: Any, aliases: Sequence[str]) -> bool:
        text = cls._normalized_label(value)
        return any(cls._normalized_label(alias) in text for alias in aliases)

    @staticmethod
    def _normalized_label(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "name") or hasattr(value, "name_en"):
            parts = (getattr(value, "name", ""), getattr(value, "name_en", ""))
            value = " ".join(str(part) for part in parts if part)
        return (
            str(value)
            .casefold()
            .replace("ي", "ی")
            .replace("ى", "ی")
            .replace("ك", "ک")
            .replace("\u200c", "")
            .replace("-", "")
            .replace(" ", "")
        )

    @classmethod
    def _allowed_difficulty_level_ids(cls, difficulty: ExerciseDifficultyLevel | int) -> list[int]:
        """Return the selected level and all easier levels.

        The lookup table is user-editable and historically contains both Persian
        and English labels, so the rule is intentionally based on normalized
        labels rather than hard-coded database primary keys.
        """

        difficulty_id = getattr(difficulty, "pk", difficulty)
        selected_level = (
            difficulty
            if isinstance(difficulty, ExerciseDifficultyLevel)
            else ExerciseDifficultyLevel.objects.filter(pk=difficulty_id).first()
        )
        selected_rank = cls._difficulty_rank(selected_level)
        if selected_rank is None:
            return [difficulty_id]
        if selected_rank == 2:
            return list(ExerciseDifficultyLevel.objects.values_list("pk", flat=True))

        return [
            level.pk
            for level in ExerciseDifficultyLevel.objects.all()
            if (level_rank := cls._difficulty_rank(level)) is not None
            and level_rank <= selected_rank
        ] or [difficulty_id]

    @classmethod
    def _difficulty_rank(cls, difficulty_level: ExerciseDifficultyLevel | None) -> int | None:
        """Map a catalog difficulty label to the normalized 0-2 difficulty rank."""
        if not difficulty_level:
            return None
        text = " ".join(
            value
            for value in (
                getattr(difficulty_level, "name", ""),
                getattr(difficulty_level, "name_en", ""),
            )
            if value
        ).casefold()
        text = text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
        for rank in (2, 1, 0):
            if any(alias.casefold() in text for alias in cls.DIFFICULTY_ALIASES[rank]):
                return rank
        return None

    @staticmethod
    def _secondary_movement_types(
        ids: Sequence[int],
    ) -> QuerySet[ExerciseSecondaryMovementType]:
        """Load the selected target sections from the exercise library."""
        return ExerciseSecondaryMovementType.objects.filter(pk__in=ids)

    @classmethod
    def _selected_movement_type_ids(
        cls,
        secondary_movement_counts: Mapping[Any, Any] | Sequence[Any] | None,
        session_movement_targets: Sequence[dict[str, Any]] | None,
    ) -> list[int]:
        """Normalize legacy and row-based target-section inputs to primary keys."""
        selected_ids = []

        def add(value):
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return
            if parsed > 0 and parsed not in selected_ids:
                selected_ids.append(parsed)

        if isinstance(secondary_movement_counts, dict):
            for movement_type_id in secondary_movement_counts:
                add(movement_type_id)
        elif isinstance(secondary_movement_counts, (list, tuple)):
            for movement_type_id in secondary_movement_counts:
                add(movement_type_id)

        if isinstance(session_movement_targets, list):
            for session_target in session_movement_targets:
                if not isinstance(session_target, dict):
                    continue
                target_entries = cls._session_target_entries(session_target)
                if target_entries is not None:
                    for movement_type_id, _count in target_entries:
                        add(movement_type_id)
                    continue
                movement_types = session_target.get("movement_types")
                if movement_types is None:
                    movement_types = (session_target.get("counts") or {}).keys()
                for movement_type_id in movement_types or []:
                    add(movement_type_id)

        return selected_ids

    @staticmethod
    def _selected_pattern_ids(
        session_movement_targets: Sequence[dict[str, Any]] | None,
    ) -> list[int]:
        selected_ids = []
        for session in session_movement_targets or []:
            if not isinstance(session, dict):
                continue
            for entry in session.get("patterns", []):
                if not isinstance(entry, dict):
                    continue
                try:
                    pattern_id = int(entry.get("movement_pattern", entry.get("id", 0)))
                except (TypeError, ValueError):
                    continue
                if pattern_id > 0 and pattern_id not in selected_ids:
                    selected_ids.append(pattern_id)
        return selected_ids

    @classmethod
    def _session_plans(
        cls,
        *,
        sessions: int,
        selected_ids: Sequence[int],
        secondary_movement_counts: Mapping[Any, Any] | Sequence[Any] | None,
        session_movement_targets: Sequence[dict[str, Any]] | None,
        movement_type_map: Mapping[int, Any],
        pattern_type_map: Mapping[int, Any],
    ) -> list[dict[str, Any]]:
        """Build an ordered movement/count plan for each training session."""
        session_count = max(1, int(sessions))
        fallback_counts = (
            secondary_movement_counts
            if isinstance(secondary_movement_counts, dict)
            else {}
        )
        plans = []
        for index in range(session_count):
            target = (
                session_movement_targets[index]
                if isinstance(session_movement_targets, list)
                and index < len(session_movement_targets)
                and isinstance(session_movement_targets[index], dict)
                else None
            )
            if target is None:
                movement_types = list(selected_ids)
                counts = fallback_counts
            else:
                target_entries = cls._session_target_entries(target)
                if target_entries is not None:
                    movement_types = [movement_type_id for movement_type_id, _count in target_entries]
                    counts = {
                        str(movement_type_id): count
                        for movement_type_id, count in target_entries
                    }
                else:
                    movement_types = target.get("movement_types")
                    counts = target.get("counts") or {}
                    if movement_types is None:
                        movement_types = list(counts.keys())
            section_plan = []
            for movement_type_id in cls._ordered_movement_type_ids(movement_types, movement_type_map):
                count = counts.get(
                    str(movement_type_id),
                    counts.get(movement_type_id, 1),
                ) if isinstance(counts, dict) else 1
                try:
                    count = max(0, min(20, int(count or 0)))
                except (TypeError, ValueError):
                    count = 1
                if count:
                    section_plan.append((movement_type_id, count))

            pattern_plan = []
            if isinstance(target, dict):
                for pattern_id, count in cls._pattern_target_entries(target):
                    try:
                        pattern_id = int(pattern_id)
                        count = max(0, min(20, int(count or 0)))
                    except (TypeError, ValueError):
                        continue
                    if pattern_id in pattern_type_map and count:
                        pattern_plan.append((pattern_id, count))

            plans.append(
                {
                    "name": str(target.get("name") or "") if isinstance(target, dict) else "",
                    "sections": section_plan,
                    "patterns": pattern_plan,
                }
            )
        return plans

    @staticmethod
    def _session_target_entries(
        session_target: dict[str, Any],
    ) -> list[tuple[Any, Any]] | None:
        """Return row-based session targets as ``(movement_type_id, count)`` pairs.

        The editor stores each session as separate target rows. The older
        ``movement_types``/``counts`` shape remains supported for saved payloads
        and callers that use the service directly.
        """

        if not isinstance(session_target, dict) or "targets" not in session_target:
            return None
        entries = session_target.get("targets")
        if not isinstance(entries, list):
            return []
        normalized: list[tuple[Any, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            movement_type_id = entry.get(
                "movement_type",
                entry.get("movement_type_id", entry.get("target_section")),
            )
            count = entry.get(
                "count",
                entry.get("movement_count", entry.get("movements", 0)),
            )
            normalized.append((movement_type_id, count))
        return normalized

    @staticmethod
    def _pattern_target_entries(
        session_target: dict[str, Any],
    ) -> list[tuple[Any, Any]]:
        entries = session_target.get("patterns", [])
        if not isinstance(entries, list):
            return []
        normalized = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pattern_id = entry.get("movement_pattern", entry.get("id"))
            normalized.append((pattern_id, entry.get("count", 0)))
        return normalized

    @classmethod
    def _ordered_movement_type_ids(
        cls,
        ids: Sequence[Any] | None,
        movement_type_map: Mapping[int, Any],
    ) -> list[int]:
        """Preserve requested section order while placing abdominal work last."""
        ordered = []
        for value in ids or []:
            try:
                movement_type_id = int(value)
            except (TypeError, ValueError):
                continue
            if movement_type_id in movement_type_map and movement_type_id not in ordered:
                ordered.append(movement_type_id)
        return sorted(
            ordered,
            key=lambda movement_type_id: (
                cls._is_abdominal_movement_type(movement_type_map[movement_type_id]),
                ordered.index(movement_type_id),
            ),
        )

    @staticmethod
    def _is_abdominal_movement_type(movement_type: Any) -> bool:
        """Return whether a movement section represents abdominal work."""
        text = " ".join(
            value
            for value in (
                getattr(movement_type, "name", ""),
                getattr(movement_type, "name_en", ""),
            )
            if value
        ).casefold()
        return any(
            token in text
            for token in ("شکم", "abdomen", "abdominal", "abs")
        )

    @classmethod
    def _lookup_values(
        cls,
        model: Any,
        field: str,
        goal: str,
        method: str = ExerciseTrainingMethod.NORMAL,
    ) -> list[str]:
        """Load catalog values matching the requested goal and training method."""
        aliases = cls.GOAL_ALIASES.get(goal, (goal,))
        values = []
        for alias in aliases:
            values.extend(
                getattr(item, field)
                for item in model.objects.filter(goal__iexact=alias, method=method).order_by("pk")
            )

        # General programs commonly use the intentionally blank catalog goal.
        if not values and goal == "general":
            values.extend(
                getattr(item, field)
                for item in model.objects.filter(goal="", method=method).order_by("pk")
            )
        return list(dict.fromkeys(value for value in values if value))

    @classmethod
    def _lookup_value(cls, model: Any, field: str, goal: str, fallback: str) -> str:
        """Resolve the first goal-specific prescription text with a fallback."""
        values = cls._lookup_values(model, field, goal)
        return values[0] if values else fallback

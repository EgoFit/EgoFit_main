from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from django.db.models import QuerySet

from account.models import (
    CorrectiveExercise,
    Exercise,
    ExerciseDifficultyLevel,
    ExerciseSecondaryMovementType,
    ExerciseSetType,
    ExerciseRepetitionType,
    ExerciseRestType,
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

    GOAL_DEFAULTS: dict[str, tuple[str, str, str]] = {
        "strength": ("4", "4-6", "120 ثانیه"),
        "volume": ("4", "8-12", "60-90 ثانیه"),
        "endurance": ("3", "15-20", "30-45 ثانیه"),
        "fat_burning": ("3", "12-15", "30-60 ثانیه"),
        "power": ("4", "3-5", "120-180 ثانیه"),
        "general": ("3", "8-12", "60 ثانیه"),
    }
    GOAL_ALIASES: dict[str, tuple[str, ...]] = {
        "strength": ("strength", "قدرت"),
        "volume": ("volume", "hypertrophy", "muscle gain", "حجم"),
        "endurance": ("endurance", "استقامت"),
        "fat_burning": ("fat_burning", "fat burn", "fat-burning", "چربی سوزی", "چربی‌سوزی"),
        "power": ("power", "توان"),
        "general": ("general", "عمومی", "تناسب عمومی"),
    }

    def generate(
        self,
        *,
        difficulty: ExerciseDifficultyLevel | int,
        gender: str | None,
        abnormalities: Iterable[Any],
        sessions: int,
        movements: int,
        goal: str,
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
        movement_type_map = {
            item.pk: item for item in self._secondary_movement_types(selected_ids)
        }
        selected_ids = [pk for pk in selected_ids if pk in movement_type_map]
        if not selected_ids:
            return {"days": [], "correctives": []}

        fallback_sets, fallback_reps, fallback_rest = self.GOAL_DEFAULTS.get(goal, self.GOAL_DEFAULTS["general"])
        sets = self._lookup_value(ExerciseSetType, "set_count", goal, fallback_sets)
        reps = self._lookup_value(ExerciseRepetitionType, "reps", goal, fallback_reps)
        rest = self._lookup_value(ExerciseRestType, "rest_time", goal, fallback_rest)
        difficulty_id = getattr(difficulty, "pk", difficulty)
        allowed_difficulty_ids = self._allowed_difficulty_level_ids(difficulty)
        queryset = Exercise.objects.select_related(
            "primary_muscle",
            "difficulty_level",
            "secondary_movement_type",
        ).filter(
            secondary_movement_type_id__in=selected_ids,
            difficulty_level_id__in=allowed_difficulty_ids,
        )
        exercises = list(queryset)
        by_movement_type = defaultdict(list)
        preferred_by_movement_type = defaultdict(list)
        for exercise in exercises:
            by_movement_type[exercise.secondary_movement_type_id].append(exercise)
            if exercise.difficulty_level_id == difficulty_id:
                preferred_by_movement_type[exercise.secondary_movement_type_id].append(exercise)

        session_plans = self._session_plans(
            sessions=sessions,
            selected_ids=selected_ids,
            secondary_movement_counts=secondary_movement_counts,
            session_movement_targets=session_movement_targets,
            movement_type_map=movement_type_map,
        )
        days = []
        has_explicit_session_targets = bool(session_movement_targets)
        used_exercise_ids_by_muscle = defaultdict(set)
        rotation_cursors = defaultdict(int)
        for day_number, session_plan in enumerate(session_plans, start=1):
            items = []
            session_used_exercise_ids = set()
            for movement_type_id, count in session_plan:
                # Prefer the requested level when it exists for a movement. Easier
                # levels remain available as a safe fallback for sparse libraries.
                preferred_pool = preferred_by_movement_type.get(movement_type_id, [])
                pool = by_movement_type.get(movement_type_id, [])
                for offset in range(count):
                    if not has_explicit_session_targets and len(items) >= int(movements):
                        break
                    if not pool:
                        break
                    exercise = self._pick_varied_exercise(
                        preferred_pool=preferred_pool,
                        pool=pool,
                        used_ids_by_muscle=used_exercise_ids_by_muscle,
                        session_used_ids=session_used_exercise_ids,
                        cursor=rotation_cursors[movement_type_id],
                    )
                    if exercise is None:
                        break
                    rotation_cursors[movement_type_id] += 1
                    used_exercise_ids_by_muscle[exercise.primary_muscle_id].add(exercise.pk)
                    session_used_exercise_ids.add(exercise.pk)
                    items.append(
                        {
                            "exercise": exercise.pk,
                            "exercise_name": exercise.name,
                            "superset_exercise": "",
                            "third_exercise": "",
                            "sets": sets,
                            "reps": reps,
                            "rest": rest,
                            "superset_sets": sets,
                            "superset_reps": reps,
                            "superset_rest": rest,
                            "third_sets": sets,
                            "third_reps": reps,
                            "third_rest": rest,
                            "note": "",
                        }
                    )
            if not items:
                continue
            days.append(
                {
                    "name": f"روز {day_number}",
                    "notes": f"تنظیمات هدف «{goal}»؛ قابل ویرایش توسط ادمین.",
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
        return {"days": days, "correctives": corrective_items}

    @staticmethod
    def _pick_varied_exercise(
        *,
        preferred_pool: Sequence[Exercise],
        pool: Sequence[Exercise],
        used_ids_by_muscle: Mapping[int, set[int]],
        session_used_ids: set[int],
        cursor: int,
    ) -> Exercise | None:
        """Pick an unused movement for its muscle and the current session.

        Target sections can point to the same primary muscle, so weekly variety
        is tracked by muscle rather than by the selected target-section ID.
        Repeating a movement in one session is never allowed. If the library
        has no unused candidate, ``None`` is returned instead of prescribing a
        duplicate.
        """

        def is_available(item):
            return (
                item.pk not in session_used_ids
                and item.pk not in used_ids_by_muscle.get(item.primary_muscle_id, set())
            )

        preferred_unused = [item for item in preferred_pool if is_available(item)]
        if preferred_unused:
            return preferred_unused[cursor % len(preferred_unused)]

        unused = [item for item in pool if is_available(item)]
        if unused:
            return unused[cursor % len(unused)]

        return None

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

    @classmethod
    def _session_plans(
        cls,
        *,
        sessions: int,
        selected_ids: Sequence[int],
        secondary_movement_counts: Mapping[Any, Any] | Sequence[Any] | None,
        session_movement_targets: Sequence[dict[str, Any]] | None,
        movement_type_map: Mapping[int, Any],
    ) -> list[list[tuple[int, int]]]:
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
                if not movement_types:
                    movement_types = list(selected_ids)
                    counts = fallback_counts

            plan = []
            for movement_type_id in cls._ordered_movement_type_ids(
                movement_types,
                movement_type_map,
            ):
                count = counts.get(
                    str(movement_type_id),
                    counts.get(movement_type_id, 1),
                ) if isinstance(counts, dict) else 1
                try:
                    count = max(0, min(20, int(count or 0)))
                except (TypeError, ValueError):
                    count = 1
                if count:
                    plan.append((movement_type_id, count))
            plans.append(plan)
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
    def _lookup_value(cls, model: Any, field: str, goal: str, fallback: str) -> str:
        """Resolve goal-specific prescription text with a safe fallback value."""
        aliases = cls.GOAL_ALIASES.get(goal, (goal,))
        queryset = model.objects.all()
        for alias in aliases:
            item = queryset.filter(goal__iexact=alias).order_by("pk").first()
            if item:
                return getattr(item, field)

        # General programs commonly use the intentionally blank catalog goal.
        if goal == "general":
            item = queryset.filter(goal="").order_by("pk").first()
            if item:
                return getattr(item, field)
        return fallback

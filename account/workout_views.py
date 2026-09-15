from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import re

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from account.models import (
    CorrectiveExercise,
    Exercise,
    WorkoutPerformanceRecord,
    WorkoutProgram,
    WorkoutProgramDay,
    WorkoutProgramExercise,
    WorkoutProgramFeedback,
    WorkoutProgramPayment,
)
from account.portal_mixins import UserPortalRequiredMixin
from account.services.gym_program_pdf import build_program_pdf
from account.services.gym_program_service import GymProgramService
from account.utils import normalize_digits
from account.view_mixins import AccountPageMixin


gym_program_service = GymProgramService()


def _has_workout_program_access(user, program) -> bool:
    return bool(
        program
        and (
            not program.requires_payment
            or WorkoutProgramPayment.objects.filter(
                program=program,
                user=user,
                status=WorkoutProgramPayment.Status.PAID,
            ).exists()
        )
    )

class ProfileWorkoutProgramsView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/profile-workout-programs.html"
    active_section = "workout"
    account_title = _("برنامه بدنسازی")
    account_description = _("برنامه تمرینی تجویز‌شده، حرکت‌ها و نکات مربی را آنلاین دنبال کنید.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        programs = list(gym_program_service.get_program_queryset().filter(
            user=self.request.user,
            is_published=True,
        ))
        feedbacks = list(
            WorkoutProgramFeedback.objects.filter(
                program_id__in=[program.pk for program in programs]
            ).select_related("day")
        )
        feedback_by_day = {
            feedback.day_id: feedback
            for feedback in feedbacks
            if feedback.day_id is not None
        }
        legacy_feedback_by_program = {}
        latest_feedback_by_program = {}
        for feedback in sorted(
            feedbacks,
            key=lambda item: item.submitted_at,
            reverse=True,
        ):
            latest_feedback_by_program.setdefault(feedback.program_id, feedback)
            if feedback.day_id is None:
                legacy_feedback_by_program.setdefault(feedback.program_id, feedback)

        for program in programs:
            program.can_access = _has_workout_program_access(self.request.user, program)
            corrective_items = list(program.corrective_items.all())
            program.warmup_correctives = [
                item for item in corrective_items if item.phase == "warmup"
            ]
            program.cooldown_correctives = [
                item for item in corrective_items if item.phase == "cooldown"
            ]
            program.user_feedback = latest_feedback_by_program.get(program.pk)
            for day_index, day in enumerate(program.days.all()):
                day.user_feedback = feedback_by_day.get(day.pk)
                if day.user_feedback is None and day_index == 0:
                    day.user_feedback = legacy_feedback_by_program.get(program.pk)
            self._attach_performance_context(program)
        context["programs"] = programs
        return context
    @staticmethod
    def _attach_performance_context(program):
        days = list(program.days.all())
        groups_by_day = {
            day.pk: ProfileWorkoutProgramsView._build_performance_groups(
                list(day.items.all())
            )
            for day in days
        }
        exercise_ids = {
            group["exercise"].pk
            for groups in groups_by_day.values()
            for group in groups
        }
        records = list(
            WorkoutPerformanceRecord.objects.filter(
                user=program.user,
                exercise_id__in=exercise_ids,
            )
        )
        records_by_movement = defaultdict(list)
        for record in records:
            records_by_movement[
                (
                    record.exercise_id,
                    ProfileWorkoutProgramsView._normalize_repetition_key(
                        record.repetitions
                    ),
                )
            ].append(record)

        mode_units = {
            WorkoutPerformanceRecord.Mode.WEIGHT: _("کیلوگرم"),
            WorkoutPerformanceRecord.Mode.BODY_WEIGHT: _("کیلوگرم"),
            WorkoutPerformanceRecord.Mode.TIME: _("ثانیه"),
        }
        mode_choices = WorkoutPerformanceRecord.Mode.choices
        mode_values = {mode_value for mode_value, _ in mode_choices}
        for day in days:
            for item in day.items.all():
                item.performance_movements = []

        for day in days:
            day.performance_movements = []
            for group in groups_by_day[day.pk]:
                exercise = group["exercise"]
                repetitions = group["repetitions"]
                movement_records = records_by_movement.get(
                    (
                        exercise.pk,
                        ProfileWorkoutProgramsView._normalize_repetition_key(
                            repetitions
                        ),
                    ),
                    [],
                )
                latest_record = max(
                    movement_records,
                    key=lambda record: record.updated_at,
                    default=None,
                )
                modes = []
                for mode_value, mode_label in mode_choices:
                    mode_records = [
                        record
                        for record in movement_records
                        if record.mode == mode_value
                    ]
                    values_by_set = {
                        record.set_number: record.value
                        for record in mode_records
                    }
                    best_value = max(
                        (record.value for record in mode_records),
                        default=None,
                    )
                    modes.append(
                        {
                            "value": mode_value,
                            "label": mode_label,
                            "unit": mode_units[mode_value],
                            "step": "1" if mode_value == WorkoutPerformanceRecord.Mode.TIME else "0.01",
                            "best": best_value,
                            "sets": [
                                {
                                    "number": set_number,
                                    "value": values_by_set.get(set_number),
                                }
                                for set_number in range(1, group["set_count"] + 1)
                            ],
                        }
                )
                saved_mode = next(
                    (
                        source["item"].performance_modes.get(source["slot"])
                        for source in group["sources"]
                        if isinstance(source["item"].performance_modes, dict)
                        and source["item"].performance_modes.get(source["slot"]) in mode_values
                    ),
                    None,
                )
                movement_context = {
                    "exercise": exercise,
                    "slot": group["sources"][0]["slot"],
                    "input_prefix": group["input_prefix"],
                    "selected_mode": (
                        saved_mode
                        or (
                            latest_record.mode
                            if latest_record
                            else WorkoutPerformanceRecord.Mode.WEIGHT
                        )
                    ),
                    "modes": modes,
                    "repetitions": repetitions,
                }
                day.performance_movements.append(movement_context)
                for source in group["sources"]:
                    source_saved_modes = source["item"].performance_modes
                    source_selected_mode = (
                        source_saved_modes.get(source["slot"])
                        if isinstance(source_saved_modes, dict)
                        and source_saved_modes.get(source["slot"]) in mode_values
                        else movement_context["selected_mode"]
                    )
                    source_set_count = gym_program_service.parse_set_count(
                        source["sets"]
                    )
                    source_modes = [
                        {
                            **mode,
                            "sets": mode["sets"][:source_set_count],
                        }
                        for mode in movement_context["modes"]
                    ]
                    source["item"].performance_movements.append(
                        {
                            **movement_context,
                            "slot": source["slot"],
                            "input_prefix": (
                                f"performance_{source['item'].pk}_{source['slot']}"
                            ),
                            "selected_mode": source_selected_mode,
                            "modes": source_modes,
                        }
                    )

    @staticmethod
    def _normalize_repetition_key(repetitions):
        normalized = normalize_digits(repetitions or "").strip()
        parts = re.findall(r"\d+", normalized)
        if not parts:
            return normalized
        return "-".join(parts)

    @staticmethod
    def _build_performance_groups(items):
        groups = {}
        for item in items:
            movement_slots = (
                ("main", item.exercise, item.sets, item.reps, item.rest),
                (
                    "superset",
                    item.superset_exercise,
                    item.superset_sets if item.superset_sets is not None else item.sets,
                    item.superset_reps if item.superset_reps is not None else item.reps,
                    item.superset_rest if item.superset_rest is not None else item.rest,
                ),
                (
                    "third",
                    item.third_exercise,
                    item.third_sets if item.third_sets is not None else item.sets,
                    item.third_reps if item.third_reps is not None else item.reps,
                    item.third_rest if item.third_rest is not None else item.rest,
                ),
            )
            for slot, exercise, sets, reps, rest in movement_slots:
                if exercise is None:
                    continue
                repetitions = str(reps or "").strip()
                key = (
                    exercise.pk,
                    ProfileWorkoutProgramsView._normalize_repetition_key(
                        repetitions
                    ),
                )
                group = groups.setdefault(
                    key,
                    {
                        "exercise": exercise,
                        "repetitions": repetitions,
                        "set_count": 1,
                        "sources": [],
                        "input_prefix": f"performance_{item.pk}_{slot}",
                    },
                )
                group["set_count"] = max(
                    group["set_count"],
                    gym_program_service.parse_set_count(sets),
                )
                group["sources"].append(
                    {
                        "item": item,
                        "slot": slot,
                        "sets": sets,
                        "reps": repetitions,
                        "rest": rest,
                    }
                )
        return list(groups.values())


class ProfileWorkoutProgramPerformanceView(UserPortalRequiredMixin, View):
    """Save workout set values and optional difficulty feedback for the owner."""

    def post(self, request, pk):
        program = get_object_or_404(
            gym_program_service.get_program_queryset(),
            pk=pk,
            user=request.user,
            is_published=True,
        )
        if not _has_workout_program_access(request.user, program):
            messages.info(request, _("برای مشاهده این برنامه ابتدا هزینه آن را پرداخت کنید."))
            return redirect("register:profile_workout_programs")
        day_id = (request.POST.get("day_id") or "").strip()
        selected_day = None
        if day_id:
            selected_day = get_object_or_404(
                WorkoutProgramDay,
                pk=day_id,
                program=program,
            )
            item_queryset = selected_day.items
        else:
            item_queryset = WorkoutProgramExercise.objects.filter(day__program=program)
        items = list(
            item_queryset.select_related(
                "exercise",
                "superset_exercise",
                "third_exercise",
            )
        )
        valid_modes = set(WorkoutPerformanceRecord.Mode.values)
        performance_values = []
        original_modes = {
            item.pk: item.performance_modes
            if isinstance(item.performance_modes, dict)
            else {}
            for item in items
        }
        selected_modes_by_item = {
            item_id: dict(saved_modes)
            for item_id, saved_modes in original_modes.items()
        }
        errors = []

        for group in ProfileWorkoutProgramsView._build_performance_groups(items):
            posted_sources = [
                (
                    source,
                    f"performance_{source['item'].pk}_{source['slot']}",
                )
                for source in group["sources"]
                if request.POST.get(
                    f"performance_{source['item'].pk}_{source['slot']}_mode"
                )
            ]
            if len(posted_sources) > 1:
                entries = [
                    (
                        source,
                        prefix,
                        gym_program_service.parse_set_count(source["sets"]),
                    )
                    for source, prefix in posted_sources
                ]
            else:
                entries = [
                    (
                        group["sources"][0],
                        group["input_prefix"],
                        group["set_count"],
                    )
                ]

            for source, prefix, set_count in entries:
                mode = (request.POST.get(f"{prefix}_mode") or "").strip()
                if not mode:
                    continue
                if mode not in valid_modes:
                    errors.append(_("نحوه ثبت عملکرد یکی از حرکت‌ها معتبر نیست."))
                    continue

                for selected_source in (
                    group["sources"] if len(posted_sources) <= 1 else [source]
                ):
                    selected_modes_by_item[selected_source["item"].pk][
                        selected_source["slot"]
                    ] = mode

                for set_number in range(1, set_count + 1):
                    raw_value = request.POST.get(
                        f"{prefix}_{mode}_set_{set_number}"
                    )
                    if not (raw_value or "").strip():
                        continue
                    try:
                        value = self._parse_performance_value(raw_value)
                    except ValueError as exc:
                        errors.append(
                            _("%(exercise)s، ست %(set)s: %(error)s")
                            % {
                                "exercise": group["exercise"].name,
                                "set": set_number,
                                "error": str(exc),
                            }
                        )
                        continue
                    performance_values.append(
                        {
                            "user": request.user,
                            "exercise": group["exercise"],
                            "program": program,
                            "program_exercise": source["item"],
                            "repetitions": normalize_digits(group["repetitions"]).strip(),
                            "mode": mode,
                            "set_number": set_number,
                            "value": value,
                        }
                    )

        mode_selections = {
            item_id: selected_modes
            for item_id, selected_modes in selected_modes_by_item.items()
            if selected_modes != original_modes[item_id]
        }

        difficulty_raw = (request.POST.get("difficulty") or "").strip()
        difficulty = None
        if difficulty_raw:
            try:
                difficulty = int(normalize_digits(difficulty_raw))
            except (TypeError, ValueError):
                errors.append(_("سطح دشواری باید عددی بین صفر تا ۱۰ باشد."))
            else:
                if difficulty < 0 or difficulty > 10:
                    errors.append(_("سطح دشواری باید عددی بین صفر تا ۱۰ باشد."))

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("register:profile_workout_programs")

        with transaction.atomic():
            saved_count = 0
            if mode_selections:
                items_by_id = {item.pk: item for item in items}
                for item_id, selected_modes in mode_selections.items():
                    item = items_by_id[item_id]
                    item.performance_modes = selected_modes
                    item.save(update_fields=["performance_modes"])

            for payload in performance_values:
                lookup = {
                    "user": payload["user"],
                    "exercise": payload["exercise"],
                    "repetitions": payload["repetitions"],
                    "mode": payload["mode"],
                    "set_number": payload["set_number"],
                }
                record, created = (
                    WorkoutPerformanceRecord.objects.select_for_update().get_or_create(
                        **lookup,
                        defaults={
                            "program": payload["program"],
                            "program_exercise": payload["program_exercise"],
                            "value": payload["value"],
                        },
                    )
                )
                if not created and payload["value"] > record.value:
                    record.value = payload["value"]
                    record.program = payload["program"]
                    record.program_exercise = payload["program_exercise"]
                    record.save(
                        update_fields=[
                            "value",
                            "program",
                            "program_exercise",
                            "updated_at",
                        ]
                    )
                saved_count += 1

            if difficulty is not None:
                WorkoutProgramFeedback.objects.update_or_create(
                    program=program,
                    day=selected_day,
                    defaults={"difficulty": difficulty},
                )

        if saved_count:
            messages.success(
                request,
                _("%(count)s مقدار عملکرد با موفقیت ثبت شد.")
                % {"count": saved_count},
            )
        if difficulty is not None:
            messages.success(request, _("بازخورد سطح دشواری برنامه ثبت شد."))
        if not saved_count and difficulty is None:
            messages.info(request, _("مقداری برای ثبت انتخاب نشده است."))
        return redirect("register:profile_workout_programs")

    @staticmethod
    def _parse_performance_value(raw_value):
        normalized = normalize_digits(raw_value).strip()
        normalized = normalized.replace(",", ".").replace("٫", ".")
        if not re.fullmatch(r"\d+(?:\.\d{1,2})?", normalized):
            raise ValueError(_("مقدار باید یک عدد مثبت باشد."))
        try:
            value = Decimal(normalized)
        except InvalidOperation:
            raise ValueError(_("مقدار باید یک عدد مثبت باشد."))
        if value <= 0:
            raise ValueError(_("مقدار باید بیشتر از صفر باشد."))
        if value > Decimal("999999.99"):
            raise ValueError(_("مقدار واردشده بیش از حد مجاز است."))
        return value


class ProfileWorkoutProgramPdfView(UserPortalRequiredMixin, View):
    def get(self, request, pk):
        program = get_object_or_404(
            gym_program_service.get_program_queryset(),
            pk=pk,
            user=request.user,
            is_published=True,
        )
        if not _has_workout_program_access(request.user, program):
            messages.info(request, _("برای دریافت این برنامه ابتدا هزینه آن را پرداخت کنید."))
            return redirect("register:profile_workout_programs")
        response = HttpResponse(
            build_program_pdf(program, request=request),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'attachment; filename="workout-program-{program.pk}.pdf"'
        return response


class ProfileWorkoutMovementView(AccountPageMixin, UserPortalRequiredMixin, TemplateView):
    template_name = "account/workout-movement-detail.html"
    active_section = "workout"
    account_title = _("نمایش حرکت")
    account_description = _("ویدیوی حرکت انتخاب‌شده از کتابخانه ایگوفیت.")

    def dispatch(self, request, *args, **kwargs):
        self.movement_kind = kwargs.get("kind")
        self.movement_id = kwargs.get("movement_id")
        self.return_program = None
        requested_program_id = request.GET.get("program")
        try:
            requested_program_id = int(requested_program_id)
        except (TypeError, ValueError):
            requested_program_id = None

        if self.movement_kind == "exercise":
            movement_queryset = Exercise.objects.select_related(
                "primary_muscle",
                "secondary_muscle",
                "body_part",
            )
            if requested_program_id:
                requested_program = WorkoutProgram.objects.filter(
                    pk=requested_program_id,
                    user=request.user,
                    is_published=True,
                ).first()
                if requested_program and _has_workout_program_access(request.user, requested_program):
                    movement_queryset = movement_queryset.filter(
                        Q(program_items__day__program=requested_program)
                        | Q(superset_program_items__day__program=requested_program)
                        | Q(third_program_items__day__program=requested_program)
                    ).distinct()
                    self.return_program = requested_program

            self.movement = get_object_or_404(
                movement_queryset.filter(
                    (
                        Q(
                            program_items__day__program__user=request.user,
                            program_items__day__program__is_published=True,
                            program_items__day__program__requires_payment=False,
                        )
                        | Q(
                            program_items__day__program__user=request.user,
                            program_items__day__program__is_published=True,
                            program_items__day__program__payments__user=request.user,
                            program_items__day__program__payments__status=WorkoutProgramPayment.Status.PAID,
                        )
                        | Q(
                            superset_program_items__day__program__user=request.user,
                            superset_program_items__day__program__is_published=True,
                            superset_program_items__day__program__requires_payment=False,
                        )
                        | Q(
                            superset_program_items__day__program__user=request.user,
                            superset_program_items__day__program__is_published=True,
                            superset_program_items__day__program__payments__user=request.user,
                            superset_program_items__day__program__payments__status=WorkoutProgramPayment.Status.PAID,
                        )
                        | Q(
                            third_program_items__day__program__user=request.user,
                            third_program_items__day__program__is_published=True,
                            third_program_items__day__program__requires_payment=False,
                        )
                        | Q(
                            third_program_items__day__program__user=request.user,
                            third_program_items__day__program__is_published=True,
                            third_program_items__day__program__payments__user=request.user,
                            third_program_items__day__program__payments__status=WorkoutProgramPayment.Status.PAID,
                        )
                    ),
                ).distinct(),
                pk=self.movement_id,
            )
            if self.return_program is None:
                self.return_program = (
                    WorkoutProgram.objects.filter(
                        user=request.user,
                        is_published=True,
                    ).filter(
                        Q(requires_payment=False)
                        | Q(payments__user=request.user, payments__status=WorkoutProgramPayment.Status.PAID)
                    )
                    .filter(
                        Q(days__items__exercise_id=self.movement.pk)
                        | Q(days__items__superset_exercise_id=self.movement.pk)
                        | Q(days__items__third_exercise_id=self.movement.pk)
                    )
                    .order_by("pk")
                    .first()
                )
        elif self.movement_kind == "corrective":
            movement_queryset = CorrectiveExercise.objects.select_related(
                "equipment",
                "abnormality_type",
            )
            if requested_program_id:
                requested_program = WorkoutProgram.objects.filter(
                    pk=requested_program_id,
                    user=request.user,
                    is_published=True,
                ).first()
                if requested_program and _has_workout_program_access(request.user, requested_program):
                    movement_queryset = movement_queryset.filter(
                        program_items__program=requested_program
                    ).distinct()
                    self.return_program = requested_program

            self.movement = get_object_or_404(
                movement_queryset.filter(
                    Q(
                        program_items__program__user=request.user,
                        program_items__program__is_published=True,
                        program_items__program__requires_payment=False,
                    )
                    | Q(
                        program_items__program__user=request.user,
                        program_items__program__is_published=True,
                        program_items__program__payments__user=request.user,
                        program_items__program__payments__status=WorkoutProgramPayment.Status.PAID,
                    ),
                ).distinct(),
                pk=self.movement_id,
            )
            if self.return_program is None:
                self.return_program = (
                    WorkoutProgram.objects.filter(
                        user=request.user,
                        is_published=True,
                        corrective_items__corrective_exercise_id=self.movement.pk,
                    ).filter(
                        Q(requires_payment=False)
                        | Q(payments__user=request.user, payments__status=WorkoutProgramPayment.Status.PAID)
                    )
                    .order_by("pk")
                    .first()
                )
        else:
            return redirect("register:profile_workout_programs")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["movement"] = self.movement
        context["movement_kind"] = self.movement_kind
        context["return_program"] = self.return_program
        return context

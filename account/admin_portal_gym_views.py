from __future__ import annotations

import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.http import Http404
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from account.admin_forms import (
    AutomaticProgrammingForm,
    CorrectiveExerciseForm,
    ExerciseForm,
    LibrarySearchForm,
    MuscleForm,
    WorkoutProgramForm,
    WorkoutProgramPayloadForm,
    build_lookup_form,
)
from account.admin_portal_views import AdminPageMixin, AdminUserMixin
from account.models import (
    CorrectiveExercise,
    Exercise,
    ExerciseAbnormalityType,
    ExerciseBodyPart,
    ExerciseDifficultyLevel,
    ExerciseEquipmentType,
    ExerciseExecutionEquipmentType,
    ExerciseJointType,
    ExerciseMovementType,
    ExercisePowerType,
    ExercisePressureType,
    ExerciseRepetitionType,
    ExerciseRestType,
    ExerciseSecondaryMovementType,
    ExerciseSetType,
    ExerciseSportType,
    Muscle,
    WorkoutProgram,
    WorkoutProgramFeedback,
)
from account.services.gym_library_service import GymLibraryService
from account.services.gym_program_pdf import build_program_pdf
from account.services.gym_program_service import GymProgramService
from account.services.automatic_program_service import AutomaticProgramService

gym_library_service = GymLibraryService()
gym_program_service = GymProgramService()
automatic_program_service = AutomaticProgramService()

DEFAULT_LOOKUP_FIELDS = ("name", "name_en")
GYM_PAGE_SIZE = 20
GYM_PAGE_SIZES = (10, 15, 20)


def paginate_gym_queryset(request, queryset):
    """Return the requested gym page together with standard pagination context."""
    try:
        page_size = int(request.GET.get("page_size", GYM_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = GYM_PAGE_SIZE
    if page_size not in GYM_PAGE_SIZES:
        page_size = GYM_PAGE_SIZE
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    return {
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "page_size": page_size,
        "page_sizes": GYM_PAGE_SIZES,
    }

LOOKUP_REGISTRY = {
    "body-part": {"model": ExerciseBodyPart, "title": _("بخش بدن")},
    "movement-type": {"model": ExerciseMovementType, "title": _("نوع حرکت")},
    "joint-type": {"model": ExerciseJointType, "title": _("نوع مفصل")},
    "power-type": {"model": ExercisePowerType, "title": _("نوع قدرت")},
    "difficulty-level": {"model": ExerciseDifficultyLevel, "title": _("سطح دشواری")},
    "equipment-type": {"model": ExerciseEquipmentType, "title": _("تجهیزات")},
    "execution-equipment-type": {"model": ExerciseExecutionEquipmentType, "title": _("نوع تجهیزات اجرایی")},
    "secondary-movement-type": {"model": ExerciseSecondaryMovementType, "title": _("نوع حرکت دوم")},
    "abnormality-type": {"model": ExerciseAbnormalityType, "title": _("ناهنجاری")},
    "pressure-type": {"model": ExercisePressureType, "title": _("نوع فشار")},
    "sport-type": {"model": ExerciseSportType, "title": _("نوع ورزش")},
    "set-type": {"model": ExerciseSetType, "title": _("نوع ست"), "fields": ("set_count", "goal")},
    "repetition-type": {"model": ExerciseRepetitionType, "title": _("نوع تکرار"), "fields": ("reps", "goal")},
    "rest-type": {"model": ExerciseRestType, "title": _("نوع استراحت"), "fields": ("rest_time", "goal")},
}


class GymLibraryView(AdminPageMixin, TemplateView):
    template_name = "admin_portal/gym/library.html"
    active_section = "library"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(gym_library_service.get_dashboard_context())
        return context


class AutomaticProgrammingView(AdminPageMixin, View):
    """Generate an editable program payload and optionally publish it to a user."""

    template_name = "admin_portal/gym/automatic_programming.html"
    active_section = "automatic"

    def get(self, request):
        return render(request, self.template_name, self._context(AutomaticProgrammingForm()))

    def post(self, request):
        form = AutomaticProgrammingForm(request.POST)
        action = request.POST.get("action", "generate")
        preview = None
        if form.is_valid():
            if action == "save":
                payload_form = WorkoutProgramPayloadForm(request.POST)
                program_data = request.POST.copy()
                if not program_data.get("start_date"):
                    program_data["start_date"] = timezone.localdate().isoformat()
                # This action is explicitly labelled "save and send to user".
                # A checkbox is omitted from POST when it is unchecked, which
                # would otherwise turn the saved program into a draft that the
                # user portal correctly hides.
                program_data["is_published"] = "on"
                program_form = WorkoutProgramForm(program_data)
                if payload_form.is_valid() and program_form.is_valid():
                    try:
                        program = gym_program_service.save_program(
                            program_form=program_form,
                            target_user=form.cleaned_data["user"],
                            prescribed_by=request.user,
                            days_payload=payload_form.cleaned_data["days_json"],
                            correctives_payload=payload_form.cleaned_data.get("correctives_json") or [],
                        )
                    except ValidationError as exc:
                        form.add_error(None, exc)
                    else:
                        messages.success(request, _("برنامه خودکار برای کاربر منتشر شد."))
                        return redirect("register:admin_program_list", user_id=program.user_id)
                else:
                    for error in list(payload_form.errors.values()) + list(program_form.errors.values()):
                        form.add_error(None, error)
                    preview = self._decode(request.POST.get("days_json"), request.POST.get("correctives_json"))
            else:
                movement_type_counts = (
                    form.cleaned_data.get("secondary_movement_counts_json") or {}
                )
                session_movement_targets = (
                    form.cleaned_data.get("session_movement_targets_json") or []
                )
                selected = {
                    str(item.pk): movement_type_counts.get(str(item.pk), 1)
                    for item in form.cleaned_data["target_secondary_movement_types"]
                }
                preview = automatic_program_service.generate(
                    difficulty=form.cleaned_data["difficulty"],
                    gender=form.cleaned_data.get("gender"),
                    abnormalities=form.cleaned_data.get("abnormalities"),
                    sessions=form.cleaned_data["sessions_per_week"],
                    movements=form.cleaned_data["movements_per_session"],
                    goal=form.cleaned_data["goal"],
                    secondary_movement_counts=selected,
                    session_movement_targets=session_movement_targets,
                )
                messages.info(request, _("پیش‌نمایش ساخته شد؛ قبل از انتشار حرکت‌ها را بررسی و ویرایش کنید."))
        return render(request, self.template_name, self._context(form, preview))

    @staticmethod
    def _decode(days_json, correctives_json):
        try:
            days = json.loads(days_json or "[]")
            correctives = json.loads(correctives_json or "[]")
            return {"days": days if isinstance(days, list) else [], "correctives": correctives if isinstance(correctives, list) else []}
        except (TypeError, ValueError):
            return {"days": [], "correctives": []}

    def _context(self, form, preview=None):
        return {
            "form": form,
            "preview": preview or {"days": [], "correctives": []},
            "exercise_catalog": [
                {
                    "id": item.pk,
                    "name": item.name,
                    "secondary_movement_type": (
                        item.secondary_movement_type.name
                        if item.secondary_movement_type
                        else ""
                    ),
                    "difficulty_level": (
                        item.difficulty_level.name
                        if item.difficulty_level
                        else ""
                    ),
                }
                for item in Exercise.objects.select_related(
                    "primary_muscle", "secondary_movement_type", "difficulty_level"
                ).all()
            ],
            "corrective_catalog": [
                {"id": item.pk, "name": item.name}
                for item in CorrectiveExercise.objects.all()
            ],
            "active_section": self.active_section,
            "page_title": _("برنامه‌ریزی خودکار"),
            "default_start_date": (
                self.request.POST.get("start_date")
                or timezone.localdate().isoformat()
            ),
        }


class AdminProgramMixin(AdminUserMixin):
    active_section = "records"

    def _get_program(self, pk=None):
        if not pk:
            return None
        return get_object_or_404(
            gym_program_service.get_program_queryset(),
            pk=pk,
            user=self.target_user,
        )


class AdminProgramListView(AdminProgramMixin, TemplateView):
    template_name = "admin_portal/gym/program_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        programs_page = paginate_gym_queryset(
            self.request,
            gym_program_service.get_program_queryset().filter(user=self.target_user).order_by("-created_at", "-pk"),
        )
        programs = list(programs_page["page_obj"].object_list)
        feedback_by_day = {}
        legacy_feedback_by_program = {}
        for feedback in WorkoutProgramFeedback.objects.filter(
            program_id__in=[program.pk for program in programs]
        ).select_related("day").order_by("-submitted_at", "-pk"):
            if feedback.day_id is None:
                legacy_feedback_by_program.setdefault(feedback.program_id, feedback)
            else:
                feedback_by_day.setdefault((feedback.program_id, feedback.day_id), feedback)

        for program in programs:
            program.session_feedbacks = [
                feedback
                for day in program.days.all()
                if (feedback := feedback_by_day.get((program.pk, day.pk))) is not None
            ]
            program.legacy_feedback = legacy_feedback_by_program.get(program.pk)
        context["programs"] = programs
        context.update(programs_page)
        return context


class AdminProgramFormView(AdminProgramMixin, View):
    template_name = "admin_portal/gym/program_form.html"

    def get(self, request, user_id, pk=None):
        program = self._get_program(pk)
        return render(
            request,
            self.template_name,
            self._context(
                WorkoutProgramForm(instance=program),
                WorkoutProgramPayloadForm(),
                program,
            ),
        )

    def post(self, request, user_id, pk=None):
        program = self._get_program(pk)
        form = WorkoutProgramForm(request.POST, instance=program)
        payload_form = WorkoutProgramPayloadForm(request.POST)
        if form.is_valid() and payload_form.is_valid():
            try:
                gym_program_service.save_program(
                    program_form=form,
                    target_user=self.target_user,
                    prescribed_by=request.user,
                    days_payload=payload_form.cleaned_data["days_json"],
                    correctives_payload=payload_form.cleaned_data.get("correctives_json") or [],
                )
            except ValidationError as exc:
                for error in exc.messages:
                    form.add_error(None, error)
            else:
                messages.success(
                    request,
                    _("برنامه بدنسازی با موفقیت %(action)s شد.")
                    % {"action": _("ویرایش") if program else _("ثبت")},
                )
                return redirect("register:admin_program_list", user_id=self.target_user.pk)

        return render(request, self.template_name, self._context(form, payload_form, program))

    def _context(self, form, payload_form, program):
        raw_payload = {
            "days": [],
            "correctives": [],
        }
        if program is not None and not payload_form.is_bound:
            raw_payload = gym_program_service.serialize_program(program)
        elif payload_form.is_bound:
            raw_payload = {
                "days": self._decode_payload(payload_form.data.get("days_json"), []),
                "correctives": self._decode_payload(payload_form.data.get("correctives_json"), []),
            }
        return {
            "form": form,
            "payload_form": payload_form,
            "program": program,
            "target_user": self.target_user,
            "exercise_catalog": [
                {
                    "id": exercise.pk,
                    "name": exercise.name,
                    "muscle": exercise.primary_muscle.name,
                }
                for exercise in Exercise.objects.select_related("primary_muscle").all()
            ],
            "set_catalog": [
                {"value": item.set_count, "label": str(item)}
                for item in ExerciseSetType.objects.all()
            ],
            "repetition_catalog": [
                {"value": item.reps, "label": str(item)}
                for item in ExerciseRepetitionType.objects.all()
            ],
            "rest_catalog": [
                {"value": item.rest_time, "label": str(item)}
                for item in ExerciseRestType.objects.all()
            ],
            "corrective_catalog": [
                {"id": corrective.pk, "name": corrective.name}
                for corrective in CorrectiveExercise.objects.all()
            ],
            "program_payload": raw_payload,
            "active_section": self.active_section,
            "page_title": _("ویرایش برنامه بدنسازی") if program else _("افزودن برنامه بدنسازی"),
        }

    @staticmethod
    def _decode_payload(value, default):
        if not value:
            return default
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return default
        return decoded if isinstance(decoded, list) else default


class AdminProgramDeleteView(AdminProgramMixin, View):
    def post(self, request, user_id, pk):
        program = self._get_program(pk)
        program.delete()
        messages.success(request, _("برنامه بدنسازی حذف شد."))
        return redirect("register:admin_program_list", user_id=self.target_user.pk)


class AdminProgramPdfView(AdminProgramMixin, View):
    def get(self, request, user_id, pk):
        program = self._get_program(pk)
        response = HttpResponse(
            build_program_pdf(program, request=request),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'attachment; filename="workout-program-{program.pk}.pdf"'
        return response


class MuscleListView(AdminPageMixin, TemplateView):
    template_name = "admin_portal/gym/muscle_list.html"
    active_section = "library"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("query") or "").strip()
        muscles_page = paginate_gym_queryset(
            self.request, gym_library_service.search_muscles(query).order_by("name", "pk")
        )
        context.update(
            {
                "form": LibrarySearchForm(initial={"query": query}),
                "search_query": query,
                "muscles": muscles_page["page_obj"].object_list,
            }
        )
        context.update(muscles_page)
        return context


class MuscleFormView(AdminPageMixin, View):
    template_name = "admin_portal/gym/muscle_form.html"
    active_section = "library"

    def get(self, request, pk=None):
        instance = get_object_or_404(Muscle, pk=pk) if pk else None
        form = MuscleForm(instance=instance)
        return render(request, self.template_name, self._context(form, instance))

    def post(self, request, pk=None):
        instance = get_object_or_404(Muscle, pk=pk) if pk else None
        form = MuscleForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            gym_library_service.save_muscle(form)
            return redirect("register:admin_muscle_list")
        return render(request, self.template_name, self._context(form, instance))

    def _context(self, form, instance):
        return {
            "form": form,
            "muscle": instance,
            "active_section": self.active_section,
            "page_title": _("ویرایش عضله") if instance else _("افزودن عضله"),
        }


class MuscleDeleteView(AdminPageMixin, View):
    def post(self, request, pk):
        muscle = get_object_or_404(Muscle, pk=pk)
        gym_library_service.delete_muscle(muscle)
        return redirect("register:admin_muscle_list")


class ExerciseListView(AdminPageMixin, TemplateView):
    template_name = "admin_portal/gym/exercise_list.html"
    active_section = "library"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("query") or "").strip()
        exercises_page = paginate_gym_queryset(
            self.request, gym_library_service.search_exercises(query).order_by("name", "pk")
        )
        context.update(
            {
                "form": LibrarySearchForm(initial={"query": query}),
                "search_query": query,
                "exercises": exercises_page["page_obj"].object_list,
            }
        )
        context.update(exercises_page)
        return context


class ExerciseFormView(AdminPageMixin, View):
    template_name = "admin_portal/gym/exercise_form.html"
    active_section = "library"

    def get(self, request, pk=None):
        instance = get_object_or_404(Exercise, pk=pk) if pk else None
        form = ExerciseForm(instance=instance)
        return render(request, self.template_name, self._context(form, instance))

    def post(self, request, pk=None):
        instance = get_object_or_404(Exercise, pk=pk) if pk else None
        form = ExerciseForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            gym_library_service.save_exercise(form)
            return redirect("register:admin_exercise_list")
        return render(request, self.template_name, self._context(form, instance))

    def _context(self, form, instance):
        return {
            "form": form,
            "exercise": instance,
            "active_section": self.active_section,
            "page_title": _("ویرایش حرکت") if instance else _("افزودن حرکت"),
        }


class ExerciseDeleteView(AdminPageMixin, View):
    def post(self, request, pk):
        exercise = get_object_or_404(Exercise, pk=pk)
        gym_library_service.delete_exercise(exercise)
        return redirect("register:admin_exercise_list")


class CorrectiveExerciseListView(AdminPageMixin, TemplateView):
    template_name = "admin_portal/gym/corrective_list.html"
    active_section = "library"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("query") or "").strip()
        correctives_page = paginate_gym_queryset(
            self.request, gym_library_service.search_correctives(query).order_by("name", "pk")
        )
        context.update(
            {
                "form": LibrarySearchForm(initial={"query": query}),
                "search_query": query,
                "correctives": correctives_page["page_obj"].object_list,
            }
        )
        context.update(correctives_page)
        return context


class CorrectiveExerciseFormView(AdminPageMixin, View):
    template_name = "admin_portal/gym/corrective_form.html"
    active_section = "library"

    def get(self, request, pk=None):
        instance = get_object_or_404(CorrectiveExercise, pk=pk) if pk else None
        form = CorrectiveExerciseForm(instance=instance)
        return render(request, self.template_name, self._context(form, instance))

    def post(self, request, pk=None):
        instance = get_object_or_404(CorrectiveExercise, pk=pk) if pk else None
        form = CorrectiveExerciseForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            gym_library_service.save_corrective(form)
            return redirect("register:admin_corrective_list")
        return render(request, self.template_name, self._context(form, instance))

    def _context(self, form, instance):
        return {
            "form": form,
            "corrective": instance,
            "active_section": self.active_section,
            "page_title": _("ویرایش حرکت اصلاحی") if instance else _("افزودن حرکت اصلاحی"),
        }


class CorrectiveExerciseDeleteView(AdminPageMixin, View):
    def post(self, request, pk):
        corrective = get_object_or_404(CorrectiveExercise, pk=pk)
        gym_library_service.delete_corrective(corrective)
        return redirect("register:admin_corrective_list")


class LookupKeyMixin(AdminPageMixin):
    active_section = "library"

    def dispatch(self, request, *args, **kwargs):
        self.lookup_key = kwargs["key"]
        self.lookup_cfg = LOOKUP_REGISTRY.get(self.lookup_key)
        if not self.lookup_cfg:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lookup_key"] = self.lookup_key
        context["lookup_title"] = self.lookup_cfg["title"]
        return context

    @property
    def lookup_fields(self):
        return self.lookup_cfg.get("fields", DEFAULT_LOOKUP_FIELDS)


class LookupListView(LookupKeyMixin, TemplateView):
    template_name = "admin_portal/gym/lookup_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fields = self.lookup_fields
        items_page = paginate_gym_queryset(
            self.request,
            gym_library_service.list_lookup(self.lookup_cfg["model"]).order_by("pk"),
        )
        context["items"] = [
            {
                "pk": obj.pk,
                "primary": getattr(obj, fields[0]),
                "secondary": getattr(obj, fields[1]) if len(fields) > 1 else "",
            }
            for obj in items_page["page_obj"].object_list
        ]
        context.update(items_page)
        context["page_title"] = self.lookup_cfg["title"]
        return context


class LookupFormView(LookupKeyMixin, View):
    template_name = "admin_portal/gym/lookup_form.html"

    def get(self, request, key, pk=None):
        instance = get_object_or_404(self.lookup_cfg["model"], pk=pk) if pk else None
        form = build_lookup_form(self.lookup_cfg["model"], fields=self.lookup_fields, instance=instance)
        return render(request, self.template_name, self._context(form, instance))

    def post(self, request, key, pk=None):
        instance = get_object_or_404(self.lookup_cfg["model"], pk=pk) if pk else None
        form = build_lookup_form(self.lookup_cfg["model"], fields=self.lookup_fields, data=request.POST, instance=instance)
        if form.is_valid():
            gym_library_service.save_lookup(form)
            return redirect("register:admin_lookup_list", key=self.lookup_key)
        return render(request, self.template_name, self._context(form, instance))

    def _context(self, form, instance):
        return {
            "form": form,
            "item": instance,
            "lookup_key": self.lookup_key,
            "lookup_title": self.lookup_cfg["title"],
            "active_section": self.active_section,
            "page_title": _("ویرایش %(title)s") % {"title": self.lookup_cfg["title"]} if instance else _("افزودن %(title)s") % {"title": self.lookup_cfg["title"]},
        }


class LookupDeleteView(LookupKeyMixin, View):
    def post(self, request, key, pk):
        success, error_message = gym_library_service.delete_lookup(self.lookup_cfg["model"], pk)
        if not success:
            messages.error(request, error_message)
        return redirect("register:admin_lookup_list", key=self.lookup_key)

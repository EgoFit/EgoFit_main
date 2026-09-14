from __future__ import annotations

from django.db.models import ProtectedError, Q
from django.utils.translation import gettext_lazy as _

from account.models import CorrectiveExercise, Exercise, Muscle

EXERCISE_LOOKUP_SELECT_RELATED = (
    "primary_muscle",
    "secondary_muscle",
    "body_part",
    "movement_type",
    "joint_type",
    "power_type",
    "difficulty_level",
    "equipment_type",
)


class GymLibraryService:
    def get_dashboard_context(self) -> dict:
        return {
            "muscle_count": Muscle.objects.count(),
            "exercise_count": Exercise.objects.count(),
            "corrective_count": CorrectiveExercise.objects.count(),
        }

    def search_muscles(self, query: str):
        queryset = Muscle.objects.all()
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset

    def search_exercises(self, query: str):
        queryset = Exercise.objects.select_related(*EXERCISE_LOOKUP_SELECT_RELATED)
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(name_en__icontains=query))
        return queryset

    def search_correctives(self, query: str):
        queryset = CorrectiveExercise.objects.select_related("equipment", "abnormality_type")
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset

    def save_muscle(self, form) -> Muscle:
        return form.save()

    def save_exercise(self, form) -> Exercise:
        return form.save()

    def save_corrective(self, form) -> CorrectiveExercise:
        return form.save()

    def delete_muscle(self, muscle: Muscle) -> None:
        muscle.delete()

    def delete_exercise(self, exercise: Exercise) -> None:
        exercise.delete()

    def delete_corrective(self, corrective: CorrectiveExercise) -> None:
        corrective.delete()

    def list_lookup(self, model):
        return model.objects.all()

    def save_lookup(self, form):
        return form.save()

    def delete_lookup(self, model, pk: int) -> tuple[bool, str | None]:
        instance = model.objects.filter(pk=pk).first()
        if instance is None:
            return True, None
        try:
            instance.delete()
        except ProtectedError:
            return False, _("این مقدار برای یک یا چند حرکت تمرینی استفاده شده و قابل حذف نیست.")
        return True, None

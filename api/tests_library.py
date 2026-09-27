from django.urls import reverse

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
    ExerciseSecondaryMovementType,
    Muscle,
)
from api.tests_shared import ApiTestCase


class LibraryApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.muscle = Muscle.objects.create(name="API سینه", name_en="API Chest")
        self.body_part = ExerciseBodyPart.objects.create(name="API بالاتنه", name_en="API Upper body")
        self.movement_type = ExerciseMovementType.objects.create(name="API هل دادن", name_en="API Push")
        self.joint_type = ExerciseJointType.objects.create(name="API چندمفصلی", name_en="API Multi-joint")
        self.power_type = ExercisePowerType.objects.create(name="API قدرتی", name_en="API Strength")
        self.difficulty = ExerciseDifficultyLevel.objects.create(name="API متوسط", name_en="API Intermediate")
        self.equipment = ExerciseEquipmentType.objects.create(name="API هالتر", name_en="API Barbell")
        self.execution_equipment = ExerciseExecutionEquipmentType.objects.create(name="API هالتر آزاد", name_en="API Free barbell")
        self.secondary_movement = ExerciseSecondaryMovementType.objects.create(name="API سینه", name_en="API Chest")
        self.abnormality = ExerciseAbnormalityType.objects.create(name="API گرد پشتی", name_en="API Kyphosis")
        self.pressure = ExercisePressureType.objects.create(name="API وزنه", name_en="API Weight")
        self.exercise = Exercise.objects.create(
            name="API پرس سینه هالتر",
            name_en="API Barbell Bench Press",
            primary_muscle=self.muscle,
            body_part=self.body_part,
            movement_type=self.movement_type,
            joint_type=self.joint_type,
            power_type=self.power_type,
            difficulty_level=self.difficulty,
            equipment_type=self.equipment,
            execution_equipment_type=self.execution_equipment,
            secondary_movement_type=self.secondary_movement,
            pressure_type=self.pressure,
            description="حرکت پایه API سینه",
        )
        self.corrective = CorrectiveExercise.objects.create(
            name="API کشش سینه",
            equipment=self.equipment,
            abnormality_type=self.abnormality,
            description="حرکت اصلاحی API",
        )

    def test_catalog_and_filters_cover_library_resources(self):
        catalog = self.client.get(reverse("api:library:catalog"))
        filters = self.client.get(reverse("api:library:filters"))

        self.assertEqual(catalog.status_code, 200)
        catalog_keys = {item["key"] for item in catalog.json()["data"]["resources"]}
        self.assertIn("exercises", catalog_keys)
        self.assertIn("corrective-exercises", catalog_keys)
        self.assertIn("muscles", catalog_keys)
        self.assertIn("set-types", catalog_keys)
        self.assertEqual(filters.status_code, 200)
        self.assertIn("body-parts", filters.json()["data"]["lookups"])
        self.assertIn(
            "API سینه",
            [item["name"] for item in filters.json()["data"]["muscles"]],
        )

    def test_exercise_list_supports_search_filters_and_pagination(self):
        response = self.client.get(
            reverse("api:library:exercise_list"),
            {"q": "Bench", "body_part": self.body_part.pk, "page_size": 1},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["items"][0]["id"], self.exercise.pk)
        self.assertEqual(payload["items"][0]["primary_muscle"]["id"], self.muscle.pk)

    def test_exercise_detail_and_corrective_detail_include_media_contract(self):
        exercise = self.client.get(
            reverse("api:library:exercise_detail", kwargs={"pk": self.exercise.pk})
        )
        corrective = self.client.get(
            reverse("api:library:corrective_exercise_detail", kwargs={"pk": self.corrective.pk})
        )

        self.assertEqual(exercise.status_code, 200)
        self.assertEqual(exercise.json()["data"]["media"], {"primary": None, "preview": None, "videos": []})
        self.assertEqual(corrective.status_code, 200)
        self.assertEqual(corrective.json()["data"]["equipment"]["id"], self.equipment.pk)
        self.assertEqual(corrective.json()["data"]["media"]["videos"], [])

    def test_generic_lookup_endpoint_supports_all_lookup_tables(self):
        response = self.client.get(
            reverse("api:library:lookup_list", kwargs={"lookup": "body-parts"}),
            {"q": "API بالا"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["items"][0]["id"], self.body_part.pk)

        set_types = self.client.get(
            reverse("api:library:lookup_list", kwargs={"lookup": "set-types"}),
            {"q": "۳"},
        )
        self.assertEqual(set_types.status_code, 200)

    def test_library_api_is_read_only_and_rejects_unknown_resources(self):
        create = self.client.post(reverse("api:library:exercise_list"), data={"name": "نباید ساخته شود"})
        unknown = self.client.get(
            reverse("api:library:lookup_list", kwargs={"lookup": "unknown-table"})
        )

        self.assertEqual(create.status_code, 405)
        self.assertEqual(unknown.status_code, 404)
        self.assertFalse(Exercise.objects.filter(name="نباید ساخته شود").exists())

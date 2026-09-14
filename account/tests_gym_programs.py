import json
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.services.automatic_program_service import AutomaticProgramService
from account.models import (
    CorrectiveExercise,
    Exercise,
    ExerciseAbnormalityType,
    ExerciseBodyPart,
    ExerciseDifficultyLevel,
    ExerciseEquipmentType,
    ExerciseJointType,
    ExerciseMovementType,
    ExercisePowerType,
    ExerciseRepetitionType,
    ExerciseRestType,
    ExerciseSecondaryMovementType,
    ExerciseSetType,
    Muscle,
    User,
    WorkoutProgram,
    WorkoutProgramCorrective,
    WorkoutProgramDay,
    WorkoutProgramExercise,
    WorkoutPerformanceRecord,
    WorkoutProgramFeedback,
    Notification,
)


class GymProgramPortalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(
            phone="09129990001",
            fullname="gym_admin",
            is_admin=True,
        )
        self.client_user = User.objects.create(
            phone="09129990002",
            fullname="gym_client",
        )
        muscle, _ = Muscle.objects.get_or_create(name="سینه")
        body_part, _ = ExerciseBodyPart.objects.get_or_create(name="بالاتنه")
        movement_type, _ = ExerciseMovementType.objects.get_or_create(name="پوش")
        joint_type, _ = ExerciseJointType.objects.get_or_create(name="چند مفصلی")
        power_type, _ = ExercisePowerType.objects.get_or_create(name="قدرتی")
        difficulty, _ = ExerciseDifficultyLevel.objects.get_or_create(name="مبتدی")
        equipment, _ = ExerciseEquipmentType.objects.get_or_create(name="هالتر")
        self.exercise_one = Exercise.objects.create(
            name="پرس سینه هالتر",
            primary_muscle=muscle,
            body_part=body_part,
            movement_type=movement_type,
            joint_type=joint_type,
            power_type=power_type,
            difficulty_level=difficulty,
            equipment_type=equipment,
        )
        self.exercise_two = Exercise.objects.create(
            name="پرس سینه دمبل",
            primary_muscle=muscle,
            body_part=body_part,
            movement_type=movement_type,
            joint_type=joint_type,
            power_type=power_type,
            difficulty_level=difficulty,
            equipment_type=equipment,
        )
        self.exercise_three = Exercise.objects.create(
            name="قفسه سینه دستگاه",
            primary_muscle=muscle,
            body_part=body_part,
            movement_type=movement_type,
            joint_type=joint_type,
            power_type=power_type,
            difficulty_level=difficulty,
            equipment_type=equipment,
        )
        ExerciseSetType.objects.get_or_create(set_count="۳", goal="")
        ExerciseRepetitionType.objects.get_or_create(reps="۸ تا ۱۲", goal="")
        ExerciseRestType.objects.get_or_create(rest_time="۶۰ ثانیه", goal="")
        abnormality, _ = ExerciseAbnormalityType.objects.get_or_create(name="گرد پشتی")
        self.corrective = CorrectiveExercise.objects.create(
            name="کشش سینه",
            equipment=equipment,
            abnormality_type=abnormality,
        )

    def test_admin_can_create_program_with_superset_and_corrective_movement(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_program_add", args=[self.client_user.pk]),
            {
                "title": "برنامه حجم ماه اول",
                "start_date": "2026-09-01",
                "end_date": "2026-10-10",
                "is_published": "on",
                "notes": "تمرین با تمرکز بر فرم صحیح",
                "supplements_note": "آب کافی مصرف شود.",
                "warmup_notes": "",
                "cooldown_notes": "",
                "days_json": json.dumps(
                    [
                        {
                            "name": "روز سینه",
                            "notes": "استراحت بین ست‌ها رعایت شود.",
                            "items": [
                                {
                                    "exercise": self.exercise_one.pk,
                                    "superset_exercise": self.exercise_two.pk,
                                    "third_exercise": self.exercise_three.pk,
                                    "sets": "۳",
                                    "reps": "۸ تا ۱۲",
                                    "rest": "۶۰ ثانیه",
                                    "superset_sets": "۲",
                                    "superset_reps": "۱۰",
                                    "superset_rest": "۳۰ ثانیه",
                                    "third_sets": "۱",
                                    "third_reps": "۱۲",
                                    "third_rest": "۴۵ ثانیه",
                                    "note": "کنترل حرکت",
                                }
                            ],
                        }
                    ]
                ),
                "correctives_json": json.dumps(
                    [
                        {
                            "corrective_exercise": self.corrective.pk,
                            "phase": "warmup",
                            "sets": "۲",
                            "reps": "۱۰ تکرار",
                            "note": "بدون درد اجرا شود",
                        }
                    ]
                ),
            },
        )

        program = WorkoutProgram.objects.get(user=self.client_user)
        self.assertRedirects(
            response,
            reverse("register:admin_program_list", args=[self.client_user.pk]),
        )
        item = WorkoutProgramExercise.objects.get(day__program=program)
        self.assertEqual(item.exercise_id, self.exercise_one.pk)
        self.assertEqual(item.superset_exercise_id, self.exercise_two.pk)
        self.assertEqual(item.third_exercise_id, self.exercise_three.pk)
        self.assertEqual(item.superset_sets, "۲")
        self.assertEqual(item.superset_reps, "۱۰")
        self.assertEqual(item.superset_rest, "۳۰ ثانیه")
        self.assertEqual(item.third_sets, "۱")
        self.assertEqual(item.third_reps, "۱۲")
        self.assertEqual(item.third_rest, "۴۵ ثانیه")
        self.assertEqual(program.corrective_items.get().corrective_exercise_id, self.corrective.pk)
        self.assertEqual(program.prescribed_by_id, self.admin.pk)

    @patch("account.services.whatsapp_service.WhatsAppService.send_news_if_available", return_value="sent")
    def test_published_program_creates_athlete_news_notification(self, mocked_send):
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("register:admin_program_add", args=[self.client_user.pk]),
                {
                    "title": "برنامه خبری",
                    "start_date": "2026-09-01",
                    "is_published": "on",
                    "notes": "",
                    "supplements_note": "",
                    "warmup_notes": "",
                    "cooldown_notes": "",
                    "days_json": json.dumps(
                        [
                            {
                                "name": "روز اول",
                                "notes": "",
                                "items": [
                                    {
                                        "exercise": self.exercise_one.pk,
                                        "sets": "۳",
                                        "reps": "۱۰",
                                        "rest": "۶۰",
                                    }
                                ],
                            }
                        ]
                    ),
                    "correctives_json": "[]",
                },
            )

        self.assertRedirects(
            response,
            reverse("register:admin_program_list", args=[self.client_user.pk]),
        )
        notification = Notification.objects.get(user=self.client_user)
        self.assertEqual(notification.title, "برنامه بدنسازی جدید")
        self.assertIn("برنامه خبری", notification.message)
        mocked_send.assert_called_once()

    @patch("account.services.whatsapp_service.WhatsAppService.send_news_if_available", return_value="sent")
    def test_unpublished_program_does_not_create_athlete_news_notification(self, mocked_send):
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("register:admin_program_add", args=[self.client_user.pk]),
                {
                    "title": "پیش‌نویس برنامه",
                    "start_date": "2026-09-01",
                    "notes": "",
                    "supplements_note": "",
                    "warmup_notes": "",
                    "cooldown_notes": "",
                    "days_json": json.dumps(
                        [
                            {
                                "name": "روز اول",
                                "notes": "",
                                "items": [
                                    {
                                        "exercise": self.exercise_one.pk,
                                        "sets": "۳",
                                        "reps": "۱۰",
                                        "rest": "۶۰",
                                    }
                                ],
                            }
                        ]
                    ),
                    "correctives_json": "[]",
                },
            )

        self.assertRedirects(
            response,
            reverse("register:admin_program_list", args=[self.client_user.pk]),
        )
        self.assertFalse(Notification.objects.filter(user=self.client_user).exists())
        mocked_send.assert_not_called()

    def test_automatic_program_is_published_to_user_with_default_start_date(self):
        secondary_type = ExerciseSecondaryMovementType.objects.create(name="سینه خودکار")
        self.exercise_one.secondary_movement_type = secondary_type
        self.exercise_one.save(update_fields=["secondary_movement_type"])
        preview = AutomaticProgramService().generate(
            difficulty=self.exercise_one.difficulty_level,
            gender="",
            abnormalities=[],
            sessions=1,
            movements=1,
            goal="general",
            secondary_movement_counts={str(secondary_type.pk): 1},
        )

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_automatic_programming"),
            {
                "user": self.client_user.pk,
                "difficulty": self.exercise_one.difficulty_level.pk,
                "gender": "",
                "sessions_per_week": "1",
                "movements_per_session": "1",
                "goal": "general",
                "target_secondary_movement_types": [secondary_type.pk],
                "secondary_movement_counts_json": json.dumps({str(secondary_type.pk): 1}),
                "title": "برنامه خودکار منتشرشده",
                "is_published": "on",
                "start_date": "",
                "end_date": "",
                "notes": "",
                "warmup_notes": "",
                "cooldown_notes": "",
                "action": "save",
                "days_json": json.dumps(preview["days"]),
                "correctives_json": json.dumps(preview["correctives"]),
            },
        )

        program = WorkoutProgram.objects.get(title="برنامه خودکار منتشرشده")
        self.assertRedirects(
            response,
            reverse("register:admin_program_list", args=[self.client_user.pk]),
        )
        self.assertTrue(program.is_published)
        self.assertEqual(program.user_id, self.client_user.pk)
        self.assertEqual(program.start_date, timezone.localdate())
        self.assertFalse(program.requires_payment)
        self.assertEqual(program.price, 0)

        self.client.force_login(self.client_user)
        user_response = self.client.get(reverse("register:profile_workout_programs"))
        self.assertContains(user_response, program.title)

    def test_automatic_program_can_be_saved_as_paid_with_price(self):
        secondary_type = ExerciseSecondaryMovementType.objects.create(name="برنامه پولی خودکار")
        self.exercise_one.secondary_movement_type = secondary_type
        self.exercise_one.save(update_fields=["secondary_movement_type"])
        preview = AutomaticProgramService().generate(
            difficulty=self.exercise_one.difficulty_level,
            gender="",
            abnormalities=[],
            sessions=1,
            movements=1,
            goal="general",
            secondary_movement_counts={str(secondary_type.pk): 1},
        )

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_automatic_programming"),
            {
                "user": self.client_user.pk,
                "difficulty": self.exercise_one.difficulty_level.pk,
                "gender": "",
                "sessions_per_week": "1",
                "movements_per_session": "1",
                "goal": "general",
                "target_secondary_movement_types": [secondary_type.pk],
                "secondary_movement_counts_json": json.dumps({str(secondary_type.pk): 1}),
                "session_movement_targets_json": "[]",
                "title": "برنامه خودکار پولی",
                "is_published": "on",
                "requires_payment": "on",
                "price": "180000",
                "start_date": "2026-09-03",
                "end_date": "",
                "notes": "",
                "supplements_note": "",
                "warmup_notes": "",
                "cooldown_notes": "",
                "action": "save",
                "days_json": json.dumps(preview["days"]),
                "correctives_json": json.dumps(preview["correctives"]),
            },
        )

        program = WorkoutProgram.objects.get(title="برنامه خودکار پولی")
        self.assertRedirects(
            response,
            reverse("register:admin_program_list", args=[self.client_user.pk]),
        )
        self.assertTrue(program.requires_payment)
        self.assertEqual(program.price, 180000)

        self.client.force_login(self.client_user)
        user_response = self.client.get(reverse("register:profile_workout_programs"))
        self.assertContains(user_response, "نیازمند پرداخت")
        self.assertContains(user_response, "180000")

    def test_automatic_send_publishes_program_when_checkbox_is_not_submitted(self):
        secondary_type = ExerciseSecondaryMovementType.objects.create(name="ارسال خودکار")
        self.exercise_one.secondary_movement_type = secondary_type
        self.exercise_one.save(update_fields=["secondary_movement_type"])

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_automatic_programming"),
            {
                "user": self.client_user.pk,
                "difficulty": self.exercise_one.difficulty_level.pk,
                "gender": "",
                "sessions_per_week": "1",
                "movements_per_session": "1",
                "goal": "general",
                "target_secondary_movement_types": [secondary_type.pk],
                "secondary_movement_counts_json": json.dumps({str(secondary_type.pk): 1}),
                "session_movement_targets_json": "[]",
                "title": "برنامه ارسال خودکار",
                "start_date": "2026-09-03",
                "end_date": "",
                "notes": "",
                "supplements_note": "",
                "warmup_notes": "",
                "cooldown_notes": "",
                "action": "save",
                "days_json": json.dumps(
                    [
                        {
                            "name": "روز اول",
                            "items": [
                                {
                                    "exercise": self.exercise_one.pk,
                                    "sets": "۳",
                                    "reps": "۱۰",
                                }
                            ],
                        }
                    ]
                ),
                "correctives_json": "[]",
                # Deliberately omit is_published, as an unchecked checkbox does
                # in a browser form submission.
            },
        )

        program = WorkoutProgram.objects.get(title="برنامه ارسال خودکار")
        self.assertRedirects(
            response,
            reverse("register:admin_program_list", args=[self.client_user.pk]),
        )
        self.assertTrue(program.is_published)

        self.client.force_login(self.client_user)
        user_response = self.client.get(reverse("register:profile_workout_programs"))
        self.assertContains(user_response, program.title)
        plans_response = self.client.get(reverse("register:profile_plans"))
        self.assertContains(plans_response, program.title)

    def test_automatic_program_uses_session_targets_difficulty_and_abdomen_order(self):
        chest_type = ExerciseSecondaryMovementType.objects.create(name="سینه جلسه‌ای")
        abdomen_type = ExerciseSecondaryMovementType.objects.create(name="شکم جلسه‌ای")
        advanced, _ = ExerciseDifficultyLevel.objects.get_or_create(name="پیشرفته")
        advanced_chest = Exercise.objects.create(
            name="پرس سینه سطح انتخابی",
            primary_muscle=self.exercise_one.primary_muscle,
            body_part=self.exercise_one.body_part,
            movement_type=self.exercise_one.movement_type,
            joint_type=self.exercise_one.joint_type,
            power_type=self.exercise_one.power_type,
            difficulty_level=advanced,
            equipment_type=self.exercise_one.equipment_type,
            secondary_movement_type=chest_type,
        )
        easier_chest = Exercise.objects.create(
            name="پرس سینه سطح دیگر",
            primary_muscle=self.exercise_one.primary_muscle,
            body_part=self.exercise_one.body_part,
            movement_type=self.exercise_one.movement_type,
            joint_type=self.exercise_one.joint_type,
            power_type=self.exercise_one.power_type,
            difficulty_level=self.exercise_one.difficulty_level,
            equipment_type=self.exercise_one.equipment_type,
            secondary_movement_type=chest_type,
        )
        abdomen = Exercise.objects.create(
            name="کرانچ سطح انتخابی",
            primary_muscle=self.exercise_one.primary_muscle,
            body_part=self.exercise_one.body_part,
            movement_type=self.exercise_one.movement_type,
            joint_type=self.exercise_one.joint_type,
            power_type=self.exercise_one.power_type,
            difficulty_level=advanced,
            equipment_type=self.exercise_one.equipment_type,
            secondary_movement_type=abdomen_type,
        )

        preview = AutomaticProgramService().generate(
            difficulty=advanced,
            gender="",
            abnormalities=[],
            sessions=2,
            movements=1,
            goal="general",
            secondary_movement_counts={
                str(chest_type.pk): 1,
                str(abdomen_type.pk): 1,
            },
            session_movement_targets=[
                {
                    "movement_types": [abdomen_type.pk, chest_type.pk],
                    "counts": {
                        str(abdomen_type.pk): 1,
                        str(chest_type.pk): 1,
                    },
                },
                {
                    "movement_types": [chest_type.pk],
                    "counts": {str(chest_type.pk): 2},
                },
            ],
        )

        self.assertEqual(
            [item["exercise"] for item in preview["days"][0]["items"]],
            [advanced_chest.pk, abdomen.pk],
        )
        self.assertEqual(len(preview["days"][1]["items"]), 1)
        self.assertEqual(preview["days"][1]["items"][0]["exercise"], easier_chest.pk)

    def test_automatic_program_varies_repeated_body_part_sessions_before_repeating(self):
        chest_type = ExerciseSecondaryMovementType.objects.create(name="سینه تنوع هفتگی")
        exercises = [self.exercise_one, self.exercise_two, self.exercise_three]
        for exercise in exercises:
            exercise.secondary_movement_type = chest_type
            exercise.save(update_fields=["secondary_movement_type"])

        preview = AutomaticProgramService().generate(
            difficulty=self.exercise_one.difficulty_level,
            gender="",
            abnormalities=[],
            sessions=3,
            movements=1,
            goal="volume",
            secondary_movement_counts={str(chest_type.pk): 1},
            session_movement_targets=[
                {"movement_types": [chest_type.pk], "counts": {str(chest_type.pk): 1}},
                {"movement_types": [chest_type.pk], "counts": {str(chest_type.pk): 1}},
                {"movement_types": [chest_type.pk], "counts": {str(chest_type.pk): 1}},
            ],
        )

        selected_ids = [day["items"][0]["exercise"] for day in preview["days"]]
        self.assertEqual(len(selected_ids), 3)
        self.assertEqual(len(set(selected_ids)), 3)

    def test_automatic_program_skips_a_slot_when_exercise_pool_is_exhausted(self):
        chest_type = ExerciseSecondaryMovementType.objects.create(name="سینه ظرفیت محدود")
        self.exercise_one.secondary_movement_type = chest_type
        self.exercise_one.save(update_fields=["secondary_movement_type"])

        preview = AutomaticProgramService().generate(
            difficulty=self.exercise_one.difficulty_level,
            gender="",
            abnormalities=[],
            sessions=2,
            movements=1,
            goal="general",
            secondary_movement_counts={str(chest_type.pk): 1},
            session_movement_targets=[
                {"movement_types": [chest_type.pk], "counts": {str(chest_type.pk): 1}},
                {"movement_types": [chest_type.pk], "counts": {str(chest_type.pk): 1}},
            ],
        )

        self.assertEqual(len(preview["days"]), 1)
        self.assertEqual(preview["days"][0]["items"][0]["exercise"], self.exercise_one.pk)

    def test_automatic_program_does_not_repeat_a_movement_inside_one_session(self):
        chest_type = ExerciseSecondaryMovementType.objects.create(name="سینه بدون تکرار جلسه")
        self.exercise_one.secondary_movement_type = chest_type
        self.exercise_one.save(update_fields=["secondary_movement_type"])

        preview = AutomaticProgramService().generate(
            difficulty=self.exercise_one.difficulty_level,
            gender="",
            abnormalities=[],
            sessions=1,
            movements=2,
            goal="general",
            secondary_movement_counts={str(chest_type.pk): 2},
            session_movement_targets=[
                {"movement_types": [chest_type.pk], "counts": {str(chest_type.pk): 2}},
            ],
        )

        item_ids = [item["exercise"] for item in preview["days"][0]["items"]]
        self.assertEqual(item_ids, [self.exercise_one.pk])

    def test_automatic_program_allows_only_selected_or_easier_difficulty_levels(self):
        movement_type = ExerciseSecondaryMovementType.objects.create(name="سطح‌بندی جلسه‌ای")
        intermediate, _ = ExerciseDifficultyLevel.objects.get_or_create(name="متوسط")
        advanced, _ = ExerciseDifficultyLevel.objects.get_or_create(name="پیشرفته")

        intermediate_exercise = Exercise.objects.create(
            name="حرکت متوسط",
            primary_muscle=self.exercise_one.primary_muscle,
            body_part=self.exercise_one.body_part,
            movement_type=self.exercise_one.movement_type,
            joint_type=self.exercise_one.joint_type,
            power_type=self.exercise_one.power_type,
            difficulty_level=intermediate,
            equipment_type=self.exercise_one.equipment_type,
            secondary_movement_type=movement_type,
        )
        beginner_exercise = Exercise.objects.create(
            name="حرکت مبتدی",
            primary_muscle=self.exercise_one.primary_muscle,
            body_part=self.exercise_one.body_part,
            movement_type=self.exercise_one.movement_type,
            joint_type=self.exercise_one.joint_type,
            power_type=self.exercise_one.power_type,
            difficulty_level=self.exercise_one.difficulty_level,
            equipment_type=self.exercise_one.equipment_type,
            secondary_movement_type=movement_type,
        )
        service = AutomaticProgramService()
        base_kwargs = {
            "gender": "",
            "abnormalities": [],
            "sessions": 1,
            "movements": 3,
            "goal": "general",
            "secondary_movement_counts": {str(movement_type.pk): 3},
        }

        advanced_preview = service.generate(difficulty=advanced, **base_kwargs)
        advanced_exercise_ids = [
            item["exercise"] for item in advanced_preview["days"][0]["items"]
        ]
        self.assertIn(
            beginner_exercise.pk,
            advanced_exercise_ids,
        )
        self.assertIn(
            intermediate_exercise.pk,
            advanced_exercise_ids,
        )

        advanced_exercise = Exercise.objects.create(
            name="حرکت پیشرفته",
            primary_muscle=self.exercise_one.primary_muscle,
            body_part=self.exercise_one.body_part,
            movement_type=self.exercise_one.movement_type,
            joint_type=self.exercise_one.joint_type,
            power_type=self.exercise_one.power_type,
            difficulty_level=advanced,
            equipment_type=self.exercise_one.equipment_type,
            secondary_movement_type=movement_type,
        )
        self.assertNotIn(
            advanced_exercise.pk,
            [
                item["exercise"]
                for item in service.generate(
                    difficulty=intermediate,
                    **base_kwargs,
                )["days"][0]["items"]
            ],
        )

        beginner_preview = service.generate(
            difficulty=self.exercise_one.difficulty_level,
            **base_kwargs,
        )
        self.assertTrue(
            all(
                item["exercise"] == beginner_exercise.pk
                for item in beginner_preview["days"][0]["items"]
            )
        )

    def test_automatic_program_uses_database_goal_aliases(self):
        secondary_type = ExerciseSecondaryMovementType.objects.create(name="هدف حجم")
        self.exercise_one.secondary_movement_type = secondary_type
        self.exercise_one.save(update_fields=["secondary_movement_type"])
        ExerciseSetType.objects.create(set_count="DB-SET", goal="hypertrophy")
        ExerciseRepetitionType.objects.create(reps="DB-REPS", goal="hypertrophy")
        ExerciseRestType.objects.create(rest_time="DB-REST", goal="hypertrophy")

        preview = AutomaticProgramService().generate(
            difficulty=self.exercise_one.difficulty_level,
            gender="",
            abnormalities=[],
            sessions=1,
            movements=1,
            goal="volume",
            secondary_movement_counts={str(secondary_type.pk): 1},
        )

        item = preview["days"][0]["items"][0]
        self.assertEqual(item["sets"], "DB-SET")
        self.assertEqual(item["reps"], "DB-REPS")
        self.assertEqual(item["rest"], "DB-REST")

    def test_automatic_view_accepts_per_session_targets_and_searches_athletes(self):
        secondary_type = ExerciseSecondaryMovementType.objects.create(name="هدف جلسه")
        self.exercise_one.secondary_movement_type = secondary_type
        self.exercise_one.save(update_fields=["secondary_movement_type"])
        self.client_user.first_name = "علی"
        self.client_user.last_name = "ورزشکار"
        self.client_user.save(update_fields=["first_name", "last_name"])

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_automatic_programming"),
            {
                "user": self.client_user.pk,
                "difficulty": self.exercise_one.difficulty_level.pk,
                "gender": "",
                "sessions_per_week": "2",
                "movements_per_session": "1",
                "goal": "general",
                "target_secondary_movement_types": [secondary_type.pk],
                "secondary_movement_counts_json": json.dumps({str(secondary_type.pk): 1}),
                "session_movement_targets_json": json.dumps(
                    [
                        {
                            "movement_types": [str(secondary_type.pk)],
                            "counts": {str(secondary_type.pk): 1},
                        },
                        {
                            "movement_types": [str(secondary_type.pk)],
                            "counts": {str(secondary_type.pk): 1},
                        },
                    ]
                ),
                "title": "برنامه جلسه‌ای",
                "action": "generate",
            },
        )

        self.assertEqual(response.status_code, 200)
        # The second session has no unused movement left, so the service must
        # not prescribe the same exercise again just to fill the slot.
        self.assertEqual(len(response.context["preview"]["days"]), 1)
        self.assertContains(response, "automatic-athlete-search")
        self.assertContains(response, self.client_user.phone)
        self.assertContains(response, "id_session_movement_targets_json")
        self.assertContains(response, "علی ورزشکار")

    def test_admin_program_editor_reads_movements_from_database(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("register:admin_program_add", args=[self.client_user.pk])
        )

        self.assertEqual(response.status_code, 200)
        exercise_names = {item["name"] for item in response.context["exercise_catalog"]}
        corrective_names = {item["name"] for item in response.context["corrective_catalog"]}
        self.assertIn(self.exercise_one.name, exercise_names)
        self.assertIn(self.exercise_two.name, exercise_names)
        self.assertIn(self.exercise_three.name, exercise_names)
        self.assertIn(self.corrective.name, corrective_names)
        self.assertEqual(response.context["set_catalog"][0]["value"], "۳")
        self.assertIn({"value": "۸ تا ۱۲", "label": "۸ تا ۱۲"}, response.context["repetition_catalog"])
        self.assertIn({"value": "۶۰ ثانیه", "label": "۶۰ ثانیه"}, response.context["rest_catalog"])
        self.assertContains(response, "برنامه برای ورزشکار")

    def test_invalid_superset_is_rejected_without_creating_program(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("register:admin_program_add", args=[self.client_user.pk]),
            {
                "title": "برنامه نامعتبر",
                "start_date": "2026-09-01",
                "is_published": "on",
                "days_json": json.dumps(
                    [
                        {
                            "name": "روز اول",
                            "items": [
                                {
                                    "exercise": self.exercise_one.pk,
                                    "superset_exercise": self.exercise_one.pk,
                                    "sets": "۳",
                                    "reps": "۱۰",
                                }
                            ],
                        }
                    ]
                ),
                "correctives_json": "[]",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(WorkoutProgram.objects.filter(title="برنامه نامعتبر").exists())
        self.assertContains(response, "متفاوت باشد")

    def test_user_sees_published_program_table_and_movement_links(self):
        program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه قابل مشاهده",
            start_date=date(2026, 9, 1),
            is_published=True,
        )
        day = WorkoutProgramDay.objects.create(program=program, name="روز اول", order=1)
        WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            superset_exercise=self.exercise_two,
            third_exercise=self.exercise_three,
            sets="۳",
            reps="۱۰",
            rest="۶۰",
        )
        WorkoutProgramCorrective.objects.create(
            program=program,
            corrective_exercise=self.corrective,
            phase="cooldown",
            reps="۳۰ ثانیه",
        )
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("register:profile_workout_programs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, program.title)
        self.assertContains(response, self.exercise_one.name)
        self.assertContains(response, self.exercise_two.name)
        self.assertContains(response, self.exercise_three.name)
        self.assertContains(response, self.corrective.name)
        self.assertContains(
            response,
            reverse(
                "register:profile_workout_movement",
                args=["exercise", self.exercise_one.pk],
            ),
        )
        self.assertContains(response, "برنامه بدنسازی")

    def test_draft_program_is_hidden_from_user(self):
        WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="پیش‌نویس مربی",
            start_date=date(2026, 9, 1),
            is_published=False,
        )
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("register:profile_workout_programs"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "پیش‌نویس مربی")

    def test_user_can_open_linked_movement_but_not_unlinked_movement(self):
        program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه حرکت",
            start_date=date(2026, 9, 1),
            is_published=True,
        )
        day = WorkoutProgramDay.objects.create(program=program, name="روز اول", order=1)
        WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۳",
            reps="۱۰",
        )
        self.client.force_login(self.client_user)

        response = self.client.get(
            reverse(
                "register:profile_workout_movement",
                args=["exercise", self.exercise_one.pk],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.exercise_one.name)

        WorkoutProgramExercise.objects.filter(day=day).update(superset_exercise=self.exercise_two)
        response = self.client.get(
            reverse(
                "register:profile_workout_movement",
                args=["exercise", self.exercise_two.pk],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.exercise_two.name)

        WorkoutProgramExercise.objects.filter(day=day).update(third_exercise=self.exercise_three)
        response = self.client.get(
            reverse(
                "register:profile_workout_movement",
                args=["exercise", self.exercise_three.pk],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.exercise_three.name)

        response = self.client.get(
            reverse(
                "register:profile_workout_movement",
                args=["exercise", "999999"],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_pdf_download_is_available_to_admin_and_owner(self):
        program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه PDF",
            start_date=date(2026, 9, 1),
            is_published=True,
        )
        day = WorkoutProgramDay.objects.create(program=program, name="روز اول", order=1)
        WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۳",
            reps="۱۰",
        )

        self.client.force_login(self.admin)
        admin_response = self.client.get(
            reverse("register:admin_program_pdf", args=[self.client_user.pk, program.pk])
        )
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(admin_response["Content-Type"], "application/pdf")
        self.assertTrue(admin_response.content.startswith(b"%PDF"))

        self.client.force_login(self.client_user)
        user_response = self.client.get(
            reverse("register:profile_workout_program_pdf", args=[program.pk])
        )
        self.assertEqual(user_response.status_code, 200)
        self.assertEqual(user_response["Content-Type"], "application/pdf")
        self.assertTrue(user_response.content.startswith(b"%PDF"))

    def test_pdf_move_name_links_to_stored_exercise_media(self):
        Exercise.objects.filter(pk=self.exercise_one.pk).update(
            media="exercises/pdf-bench-press.mp4"
        )

        program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه لینک حرکت",
            start_date=date(2026, 9, 1),
            is_published=True,
        )
        day = WorkoutProgramDay.objects.create(program=program, name="روز اول", order=1)
        WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۳",
            reps="۱۰",
        )
        self.client.force_login(self.client_user)

        response = self.client.get(
            reverse("register:profile_workout_program_pdf", args=[program.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"http://testserver/media-files/exercises/pdf-bench-press.mp4",
            response.content,
        )

    def test_user_can_save_best_set_values_and_program_difficulty(self):
        program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه ثبت رکورد",
            start_date=date(2026, 9, 1),
            is_published=True,
        )
        day = WorkoutProgramDay.objects.create(program=program, name="روز اول", order=1)
        item = WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۳",
            reps="۱۰",
        )
        self.client.force_login(self.client_user)

        response = self.client.post(
            reverse(
                "register:profile_workout_program_performance",
                args=[program.pk],
            ),
            {
                f"performance_{item.pk}_main_mode": "weight",
                f"performance_{item.pk}_main_weight_set_1": "40",
                f"performance_{item.pk}_main_weight_set_2": "45",
                "difficulty": "8",
            },
        )

        self.assertRedirects(response, reverse("register:profile_workout_programs"))
        self.assertEqual(
            WorkoutPerformanceRecord.objects.filter(
                user=self.client_user,
                exercise=self.exercise_one,
                repetitions="10",
                mode=WorkoutPerformanceRecord.Mode.WEIGHT,
            ).count(),
            2,
        )
        self.assertEqual(
            WorkoutPerformanceRecord.objects.get(
                user=self.client_user,
                exercise=self.exercise_one,
                repetitions="10",
                mode=WorkoutPerformanceRecord.Mode.WEIGHT,
                set_number=2,
            ).value,
            45,
        )
        self.assertEqual(
            WorkoutProgramFeedback.objects.get(program=program).difficulty,
            8,
        )

        self.client.post(
            reverse(
                "register:profile_workout_program_performance",
                args=[program.pk],
            ),
            {
                f"performance_{item.pk}_main_mode": "weight",
                f"performance_{item.pk}_main_weight_set_1": "35",
                f"performance_{item.pk}_main_weight_set_2": "44",
                "difficulty": "6",
            },
        )
        self.assertEqual(
            WorkoutPerformanceRecord.objects.get(
                user=self.client_user,
                exercise=self.exercise_one,
                repetitions="10",
                mode=WorkoutPerformanceRecord.Mode.WEIGHT,
                set_number=1,
            ).value,
            40,
        )
        self.assertEqual(
            WorkoutPerformanceRecord.objects.get(
                user=self.client_user,
                exercise=self.exercise_one,
                repetitions="10",
                mode=WorkoutPerformanceRecord.Mode.WEIGHT,
                set_number=2,
            ).value,
            45,
        )
        self.assertEqual(
            WorkoutProgramFeedback.objects.get(program=program).difficulty,
            6,
        )

        self.client.post(
            reverse(
                "register:profile_workout_program_performance",
                args=[program.pk],
            ),
            {
                f"performance_{item.pk}_main_mode": "body_weight",
                f"performance_{item.pk}_main_body_weight_set_1": "۷۵",
                "difficulty": "6",
            },
        )
        self.client.post(
            reverse(
                "register:profile_workout_program_performance",
                args=[program.pk],
            ),
            {
                f"performance_{item.pk}_main_mode": "time",
                f"performance_{item.pk}_main_time_set_1": "۶۰",
                "difficulty": "6",
            },
        )
        self.assertEqual(
            WorkoutPerformanceRecord.objects.get(
                user=self.client_user,
                exercise=self.exercise_one,
                repetitions="10",
                mode=WorkoutPerformanceRecord.Mode.BODY_WEIGHT,
                set_number=1,
            ).value,
            75,
        )
        self.assertEqual(
            WorkoutPerformanceRecord.objects.get(
                user=self.client_user,
                exercise=self.exercise_one,
                repetitions="10",
                mode=WorkoutPerformanceRecord.Mode.TIME,
                set_number=1,
            ).value,
            60,
        )

    def test_performance_mode_is_saved_per_movement_instance(self):
        program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه حالت‌های جداگانه",
            start_date=date(2026, 9, 1),
            is_published=True,
        )
        day = WorkoutProgramDay.objects.create(program=program, name="روز اول", order=1)
        first_item = WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۱",
            reps="۱۰",
        )
        second_item = WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۱",
            reps="۱۰",
        )
        self.client.force_login(self.client_user)

        response = self.client.post(
            reverse(
                "register:profile_workout_program_performance",
                args=[program.pk],
            ),
            {
                f"performance_{first_item.pk}_main_mode": "weight",
                f"performance_{first_item.pk}_main_weight_set_1": "40",
                f"performance_{second_item.pk}_main_mode": "time",
                f"performance_{second_item.pk}_main_time_set_1": "60",
            },
        )

        self.assertRedirects(response, reverse("register:profile_workout_programs"))
        first_item.refresh_from_db()
        second_item.refresh_from_db()
        self.assertEqual(first_item.performance_modes, {"main": "weight"})
        self.assertEqual(second_item.performance_modes, {"main": "time"})

        response = self.client.get(reverse("register:profile_workout_programs"))
        self.assertEqual(response.status_code, 200)
        rendered_program = next(
            rendered_program
            for rendered_program in response.context["programs"]
            if rendered_program.pk == program.pk
        )
        rendered_modes = {
            movement["input_prefix"]: movement["selected_mode"]
            for item in rendered_program.days.all()[0].items.all()
            for movement in item.performance_movements
        }
        self.assertEqual(rendered_modes[f"performance_{first_item.pk}_main"], "weight")
        self.assertEqual(rendered_modes[f"performance_{second_item.pk}_main"], "time")

    def test_same_movement_and_repetition_target_has_one_performance_row_per_day(self):
        program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه حرکت تکراری",
            start_date=date(2026, 9, 1),
            is_published=True,
        )
        day = WorkoutProgramDay.objects.create(program=program, name="روز اول", order=1)
        first_item = WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۲",
            reps="۱۰",
        )
        WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۳",
            reps="۱۰",
        )
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("register:profile_workout_programs"))
        self.assertEqual(response.status_code, 200)
        rendered_program = next(
            rendered_program
            for rendered_program in response.context["programs"]
            if rendered_program.pk == program.pk
        )
        self.assertEqual(
            len(rendered_program.days.all()[0].performance_movements),
            1,
        )
        self.assertContains(
            response,
            f'data-performance-key="performance_{first_item.pk}_main"',
            count=1,
        )
        self.assertContains(
            response,
            "برای این حرکت فقط یک ردیف و به تعداد ست برنامه ثبت می‌شود.",
        )

        response = self.client.post(
            reverse(
                "register:profile_workout_program_performance",
                args=[program.pk],
            ),
            {
                "day_id": str(day.pk),
                f"performance_{first_item.pk}_main_mode": "weight",
                f"performance_{first_item.pk}_main_weight_set_1": "40",
                f"performance_{first_item.pk}_main_weight_set_2": "45",
                "difficulty": "7",
            },
        )

        self.assertRedirects(response, reverse("register:profile_workout_programs"))
        self.assertEqual(
            WorkoutPerformanceRecord.objects.filter(
                user=self.client_user,
                exercise=self.exercise_one,
                repetitions="10",
                mode=WorkoutPerformanceRecord.Mode.WEIGHT,
            ).count(),
            2,
        )
        self.assertEqual(
            WorkoutProgramFeedback.objects.get(
                program=program,
                day=day,
            ).difficulty,
            7,
        )

    def test_same_repetition_text_variants_are_grouped_to_one_performance_row(self):
        program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه حرکت با فرمت تکرار متفاوت",
            start_date=date(2026, 9, 1),
            is_published=True,
        )
        day = WorkoutProgramDay.objects.create(program=program, name="روز اول", order=1)
        WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۲",
            reps="10 - 12",
        )
        WorkoutProgramExercise.objects.create(
            day=day,
            exercise=self.exercise_one,
            sets="۲",
            reps="10-12",
        )
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("register:profile_workout_programs"))
        self.assertEqual(response.status_code, 200)
        rendered_program = next(
            rendered_program
            for rendered_program in response.context["programs"]
            if rendered_program.pk == program.pk
        )
        self.assertEqual(
            len(rendered_program.days.all()[0].performance_movements),
            1,
        )

    def test_previous_record_for_repetition_target_is_shown_on_later_program(self):
        program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه سابق",
            start_date=date(2026, 8, 1),
            is_published=True,
        )
        old_day = WorkoutProgramDay.objects.create(program=program, name="روز اول", order=1)
        WorkoutProgramExercise.objects.create(
            day=old_day,
            exercise=self.exercise_one,
            sets="۲",
            reps="۸",
        )
        WorkoutPerformanceRecord.objects.create(
            user=self.client_user,
            exercise=self.exercise_one,
            program=program,
            repetitions="۸",
            mode=WorkoutPerformanceRecord.Mode.WEIGHT,
            set_number=1,
            value=50,
        )

        later_program = WorkoutProgram.objects.create(
            user=self.client_user,
            prescribed_by=self.admin,
            title="برنامه جدید",
            start_date=date(2026, 9, 1),
            is_published=True,
        )
        later_day = WorkoutProgramDay.objects.create(
            program=later_program,
            name="روز جدید",
            order=1,
        )
        WorkoutProgramExercise.objects.create(
            day=later_day,
            exercise=self.exercise_one,
            sets="۲",
            reps="۸",
        )
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("register:profile_workout_programs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "رکورد قبلی برای این تعداد تکرار")
        self.assertContains(response, "50")

"""
One-off, idempotent importer for the legacy MySQL databases:
  - FitnessApp  (Tkinter coaching app: clients, measurements, skinfolds, coach-requests, PDFs)
  - gymdb       (project-05 gym library: muscles, exercises, equipment/pressure/set/rep/rest lookups)

Reads everything READ-ONLY from MySQL and writes into the Django DB.
Credentials come from env vars (no secret stored in the repo):
    LEGACY_DB_HOST (default el-capitan.liara.cloud), LEGACY_DB_PORT (31460),
    LEGACY_DB_USER (root), LEGACY_DB_PASSWORD (required)

Usage:
    LEGACY_DB_PASSWORD=... python manage.py import_legacy_data            # full run
    LEGACY_DB_PASSWORD=... python manage.py import_legacy_data --dry-run  # rolls back, no media written
    LEGACY_DB_PASSWORD=... python manage.py import_legacy_data --limit 5  # only first N clients
"""
from __future__ import annotations

import os
from datetime import datetime, time

import jdatetime
import pymysql
import pymysql.cursors
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from account.models import (
    BodyCircumferenceMeasurement,
    CaliperMeasurement,
    ClientDocument,
    CoachRequest,
    Exercise,
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
    ExerciseSetType,
    ExerciseSportType,
    Muscle,
    User,
)
from account.utils import calculate_age_from_jalali, normalize_phone_number

ACTIVITY_MAP = {
    "Sedentry (Low then 5000 step/day)": "sedentary",
    "Low Active (5000 - 7500 step/day)": "low_active",
    "Moderate Active (7500 - 10000 step/day)": "moderate_active",
    "Active (10000 - 12500 step/day)": "active",
    "High Active (More then 12500 step/day)": "high_active",
}
VALID_BLOOD = {c[0] for c in User.BloodGroupChoices.choices}
BODY_PART_MAP = {"upper": "بالاتنه", "lower": "پایین‌تنه"}
JOINT_MAP = {"single": "تک‌مفصلی", "multi": "چندمفصلی"}
POWER_MAP = {"power": "توانی", "strength": "قدرتی"}
DIFFICULTY_MAP = {"beginner": "مبتدی", "intermediate": "متوسط", "advanced": "پیشرفته"}
MOVEMENT_MAP = {"pull": "کشیدن", "push": "هل دادن", "leg": "پا", "core": "مرکزی بدن", "full_body": "تمام بدن"}

# (source column -> circumference field)
CIRC_MAP = {
    "height": "height_cm", "weight": "weight_kg", "chest": "chest_cm", "shoulder": "shoulders_cm",
    "waist": "waist_cm", "abdomen": "abdomen_cm", "wrist": "wrist_cm", "forearm": "forearm_cm",
    "arm_relaxed": "arm_rest_cm", "arm_flexed": "arm_flexed_cm", "hip": "hips_cm", "thigh": "thigh_cm",
    "calf": "calf_cm", "sit_height": "sit_height_cm", "Lwrist": "wrist_left_cm", "Lforearm": "forearm_left_cm",
    "Larm_relaxed": "arm_rest_left_cm", "Larm_flexed": "arm_flexed_left_cm", "Lthigh": "thigh_left_cm",
    "Lcalf": "calf_left_cm", "arm_length": "arm_length_cm", "shoulder_width": "shoulder_width_cm",
    "hip_width": "hip_width_cm", "elbow_width": "elbow_width_cm", "knee_width": "knee_width_cm",
}
CALIPER_MAP = {
    "chest_mm": "chest_armpit_men_mm", "axillar_mm": "axilla_mm", "subscapular_mm": "subscapular_mm",
    "abdominal_mm": "abdominal_mm", "suprailliac_mm": "suprailiac_mm", "lumbar_mm": "chest_mm",
    "biceps_mm": "biceps_mm", "triceps_mm": "triceps_mm", "thigh_mm": "thigh_mm", "calf_mm": "calf_mm",
}


def _norm(s):
    return (s or "").replace("‌", "").replace(" ", "").strip()


def _jalali_from_dt(dt):
    """source datetime stores Jalali Y/M/D -> ('YYYY/MM/DD', gregorian-aware-datetime) or (None, None)."""
    if not dt:
        return None, None
    try:
        jd = jdatetime.date(dt.year, dt.month, dt.day)
        greg = jd.togregorian()
        aware = timezone.make_aware(datetime.combine(greg, time.min))
        return f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}", aware
    except Exception:
        return None, None


class Command(BaseCommand):
    help = "Import legacy FitnessApp + gymdb MySQL data into the Django DB (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Roll back at the end; skip media writes.")
        parser.add_argument("--limit", type=int, default=0, help="Only import first N PersonalInfo clients (0 = all).")

    def handle(self, *args, **opts):
        self.dry_run = opts["dry_run"]
        self.limit = opts["limit"]
        host = os.environ.get("LEGACY_DB_HOST", "el-capitan.liara.cloud")
        port = int(os.environ.get("LEGACY_DB_PORT", "31460"))
        user = os.environ.get("LEGACY_DB_USER", "root")
        password = os.environ.get("LEGACY_DB_PASSWORD")
        if not password:
            raise CommandError("Set LEGACY_DB_PASSWORD (and optionally LEGACY_DB_HOST/PORT/USER).")

        self._conn_kwargs = dict(host=host, port=port, user=user, password=password,
                                 charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, connect_timeout=20,
                                 read_timeout=60, write_timeout=60)

        self.stats = {}
        # Each section uses its own short-lived MySQL connections (read fully, then close) and
        # fetches blobs one row at a time, so a dropped connection on a huge result set can't happen.
        steps = [
            self.import_gym_lookups, self.import_muscles, self.import_exercises,
            self.import_admins, self.import_clients, self.import_anthropometry,
            self.import_skinfolds, self.import_coach_requests, self.import_pdfiles,
        ]
        if self.dry_run:
            with transaction.atomic():
                for step in steps:
                    step()
                transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("DRY-RUN: rolled back (media writes skipped)."))
        else:
            for step in steps:
                with transaction.atomic():  # per-section; idempotent re-runs resume safely
                    step()
                self.stdout.write(f"  ✓ {step.__name__}")
        self.stdout.write(self.style.SUCCESS("Done. Stats: " + ", ".join(f"{k}={v}" for k, v in self.stats.items())))

    # ---- helpers ----
    def _q(self, db, sql, params=None):
        """Open a fresh short-lived connection, fully fetch, close."""
        conn = pymysql.connect(database=db, **self._conn_kwargs)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.fetchall()
        finally:
            conn.close()

    def _blob(self, db, sql, params):
        rows = self._q(db, sql, params)
        return rows[0] if rows else None

    def _bump(self, key, n=1):
        self.stats[key] = self.stats.get(key, 0) + n

    def _resolve_lookup(self, model, fa_name):
        """Find an existing lookup row by ZWNJ/space-insensitive name, else create it."""
        for obj in model.objects.all():
            if _norm(obj.name) == _norm(fa_name):
                return obj
        return model.objects.create(name=fa_name)

    # ---- gymdb ----
    def import_gym_lookups(self):
        self.eq_var = {}   # variable_equipment.id -> ExerciseEquipmentType
        self.eq_fix = {}   # fixed_equipment.id -> ExerciseExecutionEquipmentType
        self.pressure = {}  # pressure_type.id -> ExercisePressureType
        for r in self._q("gymdb", "SELECT id,name_fa,name_en FROM variable_equipment"):
            obj, _ = ExerciseEquipmentType.objects.get_or_create(name=r["name_fa"], defaults={"name_en": r["name_en"] or ""})
            self.eq_var[r["id"]] = obj
        for r in self._q("gymdb", "SELECT id,name_fa,name_en FROM fixed_equipment"):
            obj, _ = ExerciseExecutionEquipmentType.objects.get_or_create(name=r["name_fa"], defaults={"name_en": r["name_en"] or ""})
            self.eq_fix[r["id"]] = obj
        for r in self._q("gymdb", "SELECT id,pressure_type_fa,pressure_type_en FROM pressure_type"):
            obj, _ = ExercisePressureType.objects.get_or_create(name=r["pressure_type_fa"], defaults={"name_en": r["pressure_type_en"] or ""})
            self.pressure[r["id"]] = obj
        for r in self._q("gymdb", "SELECT id,name_fa,name_en FROM exercise_types"):
            ExerciseSportType.objects.get_or_create(name=r["name_fa"], defaults={"name_en": r["name_en"] or ""})
        for r in self._q("gymdb", "SELECT id,set_num,set_goal FROM set_type"):
            ExerciseSetType.objects.get_or_create(set_count=r["set_num"], goal=r["set_goal"] or "")
        for r in self._q("gymdb", "SELECT id,repetaion,repetaion_goal FROM repetaion_type"):
            ExerciseRepetitionType.objects.get_or_create(reps=r["repetaion"], goal=r["repetaion_goal"] or "")
        for r in self._q("gymdb", "SELECT id,rest,rest_goal FROM rest_type"):
            ExerciseRestType.objects.get_or_create(rest_time=r["rest"], goal=r["rest_goal"] or "")
        self._bump("equipment", len(self.eq_var))
        self._bump("execution_equipment", len(self.eq_fix))
        self._bump("pressure_type", len(self.pressure))

    def import_muscles(self):
        self.muscles = {}  # muscle_id -> Muscle
        rows = self._q("gymdb", "SELECT muscle_id,name_fa,name_en,origin,insertion,nerve,function_note,image_filename FROM muscles")
        for r in rows:
            obj, created = Muscle.objects.get_or_create(
                name=r["name_fa"],
                defaults={
                    "name_en": r["name_en"] or "", "origin": r["origin"] or "", "insertion": r["insertion"] or "",
                    "nerve": r["nerve"] or "", "function_note": r["function_note"] or "",
                },
            )
            self.muscles[r["muscle_id"]] = obj
            if created:
                self._bump("muscles_created")
            if not self.dry_run and not obj.image:
                blob = self._blob("gymdb", "SELECT image_data FROM muscles WHERE muscle_id=%s", (r["muscle_id"],))
                if blob and blob["image_data"]:
                    fname = r["image_filename"] or f"muscle_{r['muscle_id']}.png"
                    obj.image.save(fname, ContentFile(blob["image_data"]), save=True)
                    self._bump("muscle_images")

    def import_exercises(self):
        rows = self._q("gymdb", "SELECT exercise_id,name_fa,name_en,pressure_type_id,variable_equipment_id,fixed_equipment_id,"
                            "primary_muscle_id,secondary_muscle_id,media_filename,body_part,joint_type,power_type,"
                            "difficulty_level,movement_type FROM exercises")
        for r in rows:
            primary = self.muscles.get(r["primary_muscle_id"])
            if primary is None:
                self._bump("exercises_skipped_no_muscle")
                continue
            equipment = self.eq_var.get(r["variable_equipment_id"])
            if equipment is None:  # equipment_type is required; fall back to a generic row
                equipment = self._resolve_lookup(ExerciseEquipmentType, "سایر")
            defaults = {
                "name_en": r["name_en"] or "",
                "primary_muscle": primary,
                "secondary_muscle": self.muscles.get(r["secondary_muscle_id"]),
                "body_part": self._resolve_lookup(ExerciseBodyPart, BODY_PART_MAP.get(r["body_part"], "بالاتنه")),
                "movement_type": self._resolve_lookup(ExerciseMovementType, MOVEMENT_MAP.get(r["movement_type"], "کشیدن")),
                "joint_type": self._resolve_lookup(ExerciseJointType, JOINT_MAP.get(r["joint_type"], "تک‌مفصلی")),
                "power_type": self._resolve_lookup(ExercisePowerType, POWER_MAP.get(r["power_type"], "قدرتی")),
                "difficulty_level": self._resolve_lookup(ExerciseDifficultyLevel, DIFFICULTY_MAP.get(r["difficulty_level"], "متوسط")),
                "equipment_type": equipment,
                "execution_equipment_type": self.eq_fix.get(r["fixed_equipment_id"]),
                "pressure_type": self.pressure.get(r["pressure_type_id"]),
            }
            obj, created = Exercise.objects.get_or_create(name=r["name_fa"], defaults=defaults)
            if created:
                self._bump("exercises_created")
            if not self.dry_run and not obj.media:
                blob = self._blob("gymdb", "SELECT media_data FROM exercises WHERE exercise_id=%s", (r["exercise_id"],))
                if blob and blob["media_data"]:
                    fname = r["media_filename"] or f"exercise_{r['exercise_id']}.mp4"
                    obj.media.save(fname, ContentFile(blob["media_data"]), save=True)
                    self._bump("exercise_media")

    # ---- FitnessApp ----
    def import_admins(self):
        self.primary_coach = None
        for r in self._q("FitnessApp", "SELECT id,phone,password_hash FROM admin_panel_adminuser ORDER BY id"):
            phone = normalize_phone_number(r["phone"])
            if len(phone) != 11:
                continue
            obj = User.objects.filter(phone=phone).first()
            if obj is None:
                obj = User(phone=phone, fullname=self._unique_fullname(f"مربی {phone[-4:]}"), is_admin=True)
                obj.password = r["password_hash"]  # already a Django pbkdf2 hash
                obj.save()
                self._bump("admins_created")
            else:
                if not obj.is_admin:
                    obj.is_admin = True
                    obj.save(update_fields=["is_admin"])
            if self.primary_coach is None:
                self.primary_coach = obj

    def _unique_fullname(self, base):
        base = (base or "").strip() or "بدون‌نام"
        candidate = base
        i = 0
        while User.objects.filter(fullname=candidate).exists():
            i += 1
            candidate = f"{base} ({i})"
        return candidate

    def import_clients(self):
        self.user_by_phone = {}
        sql = "SELECT id,first_name,first_name_fa,last_name,last_name_fa,phone,blood_group,gender,birth_date,activity_level,password FROM PersonalInfo ORDER BY id"
        if self.limit:
            sql += f" LIMIT {self.limit}"
        for r in self._q("FitnessApp", sql):
            phone = normalize_phone_number(r["phone"])
            if len(phone) != 11 or not phone.isdigit():
                self._bump("clients_skipped_bad_phone")
                continue
            first = (r["first_name_fa"] or r["first_name"] or "").strip()
            last = (r["last_name_fa"] or r["last_name"] or "").strip()
            fullname = f"{first} {last}".strip()
            blood = r["blood_group"] if r["blood_group"] in VALID_BLOOD else None
            gender = {"male": "male", "female": "female"}.get((r["gender"] or "").strip().lower())
            activity = ACTIVITY_MAP.get(r["activity_level"])
            birth_jalali = (r["birth_date"] or "").replace("-", "/").strip() or None
            age = calculate_age_from_jalali(birth_jalali)

            obj = User.objects.filter(phone=phone).first()
            if obj is None:
                obj = User(phone=phone, fullname=self._unique_fullname(fullname or phone))
                is_new = True
            else:
                is_new = False
                if fullname and _norm(obj.fullname) != _norm(fullname):
                    obj.fullname = self._unique_fullname(fullname)
            obj.first_name = first
            obj.last_name = last
            if blood:
                obj.blood_group = blood
            if gender:
                obj.gender = gender
            if activity:
                obj.activity_level = activity
            if birth_jalali:
                obj.birth_date_jalali = birth_jalali
            if age is not None:
                obj.age = age
            # never clobber an existing usable (app-set) password
            if r["password"] and (is_new or not obj.has_usable_password()):
                obj.set_password(str(r["password"]))
            obj.save()
            self.user_by_phone[phone] = obj
            self._bump("clients_created" if is_new else "clients_updated")

    def _user_for(self, phone):
        phone = normalize_phone_number(phone)
        u = self.user_by_phone.get(phone)
        if u is None:
            u = User.objects.filter(phone=phone).first()
            if u:
                self.user_by_phone[phone] = u
        return u

    def import_anthropometry(self):
        latest = {}  # user.pk -> (jalali_str, height, weight) of the most recent row
        for r in self._q("FitnessApp", "SELECT * FROM AnthropometryMeasurements"):
            user = self._user_for(r["phone"])
            if user is None:
                self._bump("circ_skipped_no_user")
                continue
            jalali, greg = _jalali_from_dt(r["entry_data_date"])
            fields = {}
            for src, dst in CIRC_MAP.items():
                val = r.get(src)
                if val is None:
                    continue
                fields[dst] = int(round(float(val))) if dst in ("height_cm", "weight_kg") else val
            fields["user"] = user
            fields["measured_at_jalali"] = jalali
            obj, created = BodyCircumferenceMeasurement.objects.update_or_create(
                legacy_id=r["measurement_id"], defaults=fields
            )
            if greg:
                BodyCircumferenceMeasurement.objects.filter(pk=obj.pk).update(recorded_at=greg)
            self._bump("circumference_created" if created else "circumference_updated")
            key = jalali or ""
            if user.pk not in latest or key >= latest[user.pk][0]:
                latest[user.pk] = (key, fields.get("height_cm"), fields.get("weight_kg"))
        # sync each user's latest height/weight onto the profile
        for pk, (_, h, w) in latest.items():
            updates = {}
            if h is not None:
                updates["height_cm"] = h
            if w is not None:
                updates["weight_kg"] = w
            if updates:
                User.objects.filter(pk=pk).update(**updates)

    def import_skinfolds(self):
        for r in self._q("FitnessApp", "SELECT * FROM SkinfoldMeasurements"):
            user = self._user_for(r["phone"])
            if user is None:
                self._bump("caliper_skipped_no_user")
                continue
            jalali, greg = _jalali_from_dt(r["entry_data_date"])
            fields = {dst: r.get(src) for src, dst in CALIPER_MAP.items() if r.get(src) is not None}
            fields["user"] = user
            fields["measured_at_jalali"] = jalali
            obj, created = CaliperMeasurement.objects.update_or_create(legacy_id=r["skinfold_id"], defaults=fields)
            if greg:
                CaliperMeasurement.objects.filter(pk=obj.pk).update(recorded_at=greg)
            self._bump("caliper_created" if created else "caliper_updated")

    def import_coach_requests(self):
        valid_sessions = {c[0] for c in CoachRequest.SessionsPerWeek.choices}
        for r in self._q("FitnessApp", "SELECT user_id,phone,sessions_per_week,wants_diet,wants_workout,pain_notes,"
                             "illness_notes,diet_restrictions,is_read,registration_date FROM CoachRequests"):
            user = self._user_for(r["phone"])
            if user is None:
                self._bump("coachreq_skipped_no_user")
                continue
            if CoachRequest.objects.filter(user=user, created_at=r["registration_date"]).exists():
                continue
            sessions = r["sessions_per_week"] if r["sessions_per_week"] in valid_sessions else CoachRequest.SessionsPerWeek.COACH_DISCRETION
            cr = CoachRequest.objects.create(
                user=user, sessions_per_week=sessions,
                wants_diet=bool(r["wants_diet"]), wants_workout=bool(r["wants_workout"]),
                pain_notes=r["pain_notes"] or "", illness_notes=r["illness_notes"] or "",
                diet_restrictions=r["diet_restrictions"] or "",
                status=CoachRequest.Status.HANDLED if r["is_read"] else CoachRequest.Status.PENDING,
            )
            reg = r["registration_date"]
            if reg:
                if timezone.is_naive(reg):
                    reg = timezone.make_aware(reg)
                CoachRequest.objects.filter(pk=cr.pk).update(created_at=reg)
            self._bump("coach_requests_created")

    def import_pdfiles(self):
        ids = [r["id"] for r in self._q("FitnessApp", "SELECT id FROM pdfiles ORDER BY id")]
        for pid in ids:
            row = self._q("FitnessApp", f"SELECT id,phone,name_file,file_type,data_file,entry_data_date FROM pdfiles WHERE id={pid}")[0]
            user = self._user_for(row["phone"])
            if user is None:
                self._bump("pdf_skipped_no_user")
                continue
            jalali, greg = _jalali_from_dt(row["entry_data_date"])
            title = row["name_file"] or f"file_{row['id']}"
            existing = ClientDocument.objects.filter(legacy_id=row["id"]).first()
            if existing:
                self._bump("pdf_existing")
                continue
            doc = ClientDocument(user=user, uploaded_by=self.primary_coach, title=title[:120], legacy_id=row["id"])
            if not self.dry_run and row["data_file"]:
                doc.file.save(title, ContentFile(row["data_file"]), save=False)
            elif self.dry_run:
                doc.file.name = f"legacy/{title}"  # placeholder so save() validates in dry-run
            doc.save()
            if greg:
                ClientDocument.objects.filter(pk=doc.pk).update(uploaded_at=greg)
            self._bump("documents_created")

"""Import the curated movement list into the exercise library.

The source list is intentionally kept as a human-editable text file.  This
command turns its section/level structure into the normalized Exercise and
lookup records used by the admin exercise library.  Re-running it updates
matching records instead of creating a second copy.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from account.models import (
    Exercise,
    ExerciseBodyPart,
    ExerciseDifficultyLevel,
    ExerciseEquipmentType,
    ExerciseJointType,
    ExerciseMovementType,
    ExercisePowerType,
    Muscle,
)


LEVELS = {
    "مبتدی": "beginner",
    "متوسط": "intermediate",
    "پیشرفته": "advanced",
}

SECTION_CONFIG = {
    "سینه": ("سینه‌ای بزرگ", "بالاتنه", "هل دادن", "چندمفصلی"),
    "پشت و عضلات زیربغل": ("لاتيسموس دورسي (زيربغل)", "بالاتنه", "کشیدن", "چندمفصلی"),
    "عضلات کول و بخش فوقانی پشت": ("ذوزنقه‌ای (تراپز)", "بالاتنه", "کشیدن", "چندمفصلی"),
    "سرشانه": ("دلتوئيد (سرشانه)", "بالاتنه", "هل دادن", "چندمفصلی"),
    "عضلات دوسربازویی": ("دوسر بازویی (جلو بازو)", "بالاتنه", "کشیدن", "تک‌مفصلی"),
    "عضلات سه‌سر بازویی": ("سه‌سر بازویی (پشت بازو)", "بالاتنه", "هل دادن", "تک‌مفصلی"),
    "ساعد، مچ و قدرت گرفتن": ("خم‌کننده شعاعی مچ دست", "بالاتنه", "کشیدن", "تک‌مفصلی"),
    "چهارسر ران": ("راست رانی", "پایین‌تنه", "پا", "چندمفصلی"),
    "همسترینگ یا پشت ران": ("دوسر رانی", "پایین‌تنه", "پا", "چندمفصلی"),
    "سرینی یا باسن": ("سرینی بزرگ (باسن)", "پایین‌تنه", "پا", "چندمفصلی"),
    "داخل و خارج ران": ("نزدیک‌کننده دراز ران", "پایین‌تنه", "پا", "تک‌مفصلی"),
    "ساق پا و عضله جلوی ساق": ("دوقلوی ساق پا", "پایین‌تنه", "پا", "تک‌مفصلی"),
    "شکم؛ راست شکمی": ("راست شکمی", "بالاتنه", "مرکزی بدن", "تک‌مفصلی"),
    "عضلات مایل شکم، عمقی و ثبات مرکزی": ("مایل خارجی شکم", "بالاتنه", "مرکزی بدن", "چندمفصلی"),
    "فیله و راست‌کننده‌های ستون فقرات": ("راست‌کننده ستون فقرات", "بالاتنه", "مرکزی بدن", "چندمفصلی"),
    "گردن": ("جناغی-چنبری-پستانی", "بالاتنه", "مرکزی بدن", "تک‌مفصلی"),
    "حرکات تمام‌بدن و قدرتی": ("راست‌کننده ستون فقرات", "بالاتنه", "تمام بدن", "چندمفصلی"),
    "حرکات هوازی و آمادگی جسمانی قابل فیلم‌برداری": ("راست رانی", "پایین‌تنه", "تمام بدن", "چندمفصلی"),
}

EQUIPMENT_RULES = (
    ("وزن بدن", "وزن بدن"),
    ("بدون ابزار", "وزن بدن"),
    ("دمبل", "دمبل"),
    ("هالتر", "هالتر"),
    ("میله EZ", "وزنه آزاد"),
    ("کتل", "کتل بل"),
    ("کابل", "کابل"),
    ("کش", "کش"),
    ("TRX", "تی آر ایکس"),
    ("تی آر ایکس", "تی آر ایکس"),
    ("دستگاه", "دستگاه ثابت"),
    ("اسمیت", "دستگاه ثابت"),
    ("ماشین", "دستگاه ثابت"),
    ("توپ پزشکی", "مدیسن بال"),
    ("مدیسن بال", "مدیسن بال"),
    ("اسلم", "اسلم بال"),
    ("توپ سوئیسی", "سایر"),
    ("توپ", "سایر"),
    ("حلقه", "سایر"),
    ("میله", "سایر"),
    ("پارالل", "سایر"),
    ("باکس", "سایر"),
    ("نیمکت", "سایر"),
    ("سورتمه", "سایر"),
    ("طناب", "سایر"),
    ("گریپر", "سایر"),
    ("اب", "سایر"),
)

PHRASE_TRANSLATIONS = {
    "پوش‌آپ": "Push-up",
    "پرس سینه": "Bench Press",
    "بالا سینه": "Incline Press",
    "پایین سینه": "Decline Press",
    "فلای": "Fly",
    "کراس‌اور": "Cable Crossover",
    "دیپ": "Dip",
    "پرتاب سینه‌ای": "Chest Pass",
    "لت‌پول‌داون": "Lat Pulldown",
    "پول‌داون": "Pulldown",
    "پول‌اور": "Pullover",
    "بارفیکس": "Pull-up",
    "چین‌آپ": "Chin-up",
    "قایقی": "Seated Row",
    "روئینگ": "Row",
    "پارویی": "Row",
    "شراگ": "Shrug",
    "فیس‌پول": "Face Pull",
    "فلای معکوس": "Reverse Fly",
    "وال‌اسلاید": "Wall Slide",
    "نشر جانب": "Lateral Raise",
    "نشر جلو": "Front Raise",
    "نشر خم": "Rear Delt Raise",
    "پرس سرشانه": "Shoulder Press",
    "پرس نظامی": "Military Press",
    "آرنولد پرس": "Arnold Press",
    "پوش‌پرس": "Push Press",
    "جرک": "Jerk",
    "جلو بازو": "Biceps Curl",
    "چکشی": "Hammer Curl",
    "لاری": "Preacher Curl",
    "تمرکزی": "Concentration Curl",
    "زاتمن": "Zottman Curl",
    "درگ": "Drag Curl",
    "پشت بازو": "Triceps Extension",
    "کیک‌بک": "Kickback",
    "اسکال‌کراشر": "Skull Crusher",
    "رولینگ": "Rolling Extension",
    "مچ‌خم": "Wrist Curl",
    "فارمر": "Farmer Carry",
    "ددهنگ": "Dead Hang",
    "اسکوات": "Squat",
    "لانج": "Lunge",
    "اسپلیت اسکوات": "Split Squat",
    "استپ‌آپ": "Step-up",
    "پرس پا": "Leg Press",
    "جلوپا": "Leg Extension",
    "هاک اسکوات": "Hack Squat",
    "پشت پا": "Leg Curl",
    "پل باسن": "Glute Bridge",
    "هیپ تراست": "Hip Thrust",
    "هیپ‌هینج": "Hip Hinge",
    "ددلیفت": "Deadlift",
    "گودمورنینگ": "Good Morning",
    "نوردیک": "Nordic Curl",
    "سوئینگ": "Kettlebell Swing",
    "کابل پول‌ترو": "Cable Pull-through",
    "داخل ران": "Adduction",
    "خارج ران": "Abduction",
    "کازاک": "Cossack Squat",
    "کپنهاگن پلانک": "Copenhagen Plank",
    "ساق": "Calf Raise",
    "تیبیالیس": "Tibialis Raise",
    "طناب‌زدن": "Jump Rope",
    "کرانچ": "Crunch",
    "پلانک": "Plank",
    "ددباگ": "Dead Bug",
    "بالا آوردن": "Leg Raise",
    "چرخش": "Rotation",
    "پالوف پرس": "Pallof Press",
    "وودچاپ": "Wood Chop",
    "روسین توئیست": "Russian Twist",
    "بردداگ": "Bird Dog",
    "سوپرمن": "Superman",
    "بک‌اکستنشن": "Back Extension",
    "کلین": "Clean",
    "اسنچ": "Snatch",
    "تراستر": "Thruster",
    "برپی": "Burpee",
    "ماسل‌آپ": "Muscle-up",
    "ترکیش گت‌آپ": "Turkish Get-up",
    "راه‌رفتن": "Walk",
    "دویدن": "Running",
    "دوچرخه": "Bike",
    "الپتیکال": "Elliptical",
    "مارچ": "March",
    "بتل‌روپ": "Battle Rope",
    "اسپرینت": "Sprint",
    "پریدن": "Jump",
    "پرش": "Jump",
    "حمل": "Carry",
}

EXACT_TRANSLATIONS = {
    "آویزان ماندن با حوله": "Towel Hang",
    "آویزان ماندن تک دست": "One-arm Hang",
    "آویزان ماندن کمکی": "Assisted Hang",
    "آپ رایت رو با دامنه کنترل شده": "Controlled Upright Row",
    "ابداکشن ایستاده با کش": "Standing Band Abduction",
    "ابداکشن خوابیده پهلو": "Side-lying Hip Abduction",
    "ابداکشن دستگاه": "Machine Hip Abduction",
    "ابداکشن کابل": "Cable Hip Abduction",
    "اداکشن ایستاده با کش": "Standing Band Adduction",
    "اداکشن خوابیده پهلو": "Side-lying Hip Adduction",
    "اداکشن کابل": "Cable Hip Adduction",
    "اسکیترباند جانبی": "Lateral Skater Band",
    "اکستنشن ایزومتریک": "Isometric Neck Extension",
    "اکستنشن با هارنس سبک": "Light Harness Neck Extension",
    "اکستنشن گردن با کش": "Band Neck Extension",
    "باتم آپ کتل بل پرس": "Bottoms-up Kettlebell Press",
    "بادی ساو": "Body Saw",
    "براد جامپ": "Broad Jump",
    "تمرین گردن با هارنس و بار تدریجی": "Progressive Harness Neck Training",
    "تنفس دیافراگمی و بریس شکمی": "Diaphragmatic Breathing and Abdominal Brace",
    "خم جانبی گردن با کش": "Band Neck Lateral Flexion",
    "خم کردن جانبی ایزومتریک": "Isometric Neck Lateral Flexion",
    "دانکی کالف ریز": "Donkey Calf Raise",
    "دانکی کیک": "Donkey Kick",
    "دراگون فلگ": "Dragon Flag",
    "دورسی فلکشن با کش": "Band Dorsiflexion",
    "راک پول سنگین": "Heavy Rack Pull",
    "ریورس هایپر سنگین": "Heavy Reverse Hyperextension",
    "ریورس هایپراکستنشن": "Reverse Hyperextension",
    "سورتمه هل دادن": "Sled Push",
    "طناب نوردی": "Rope Climb",
    "طناب نوردی بدون کمک پا": "Legless Rope Climb",
    "فایرهایدرنت": "Fire Hydrant",
    "فرانت لور": "Front Lever",
    "فرانت لور رو": "Front Lever Row",
    "فراگ پامپ": "Frog Pump",
    "فشار دادن توپ یا گریپر سبک": "Light Ball or Gripper Squeeze",
    "فلکشن ایزومتریک گردن": "Isometric Neck Flexion",
    "فلکشن گردن با کش سبک": "Light Band Neck Flexion",
    "لندماین روتیشن": "Landmine Rotation",
    "لندماین رین بو": "Landmine Rainbow",
    "مانستر واک": "Monster Walk",
    "نگه داشتن دمبل درجا": "Dumbbell Static Hold",
    "هالو راک وزنه دار": "Weighted Hollow Rock",
    "های رو کابل": "Cable High Row",
    "همر کرل": "Hammer Curl",
    "هیپ هایک": "Hip Hike",
    "پرس حلقه در حالت وارونه": "Inverted Ring Press",
    "پرس لندماین تک دست": "Single-arm Landmine Press",
    "پرس پشت گردن فقط برای افراد دارای تحرک مناسب": "Behind-the-neck Press",
    "پرس کتل بل دوبل": "Double Kettlebell Press",
    "پشت مچ هالتر": "Barbell Reverse Wrist Curl",
    "پلیت پینچ": "Plate Pinch",
    "پلیت پینچ سنگین": "Heavy Plate Pinch",
    "پول آپ انفجاری سینه تا میله": "Explosive Chest-to-bar Pull-up",
    "کتل بل رو": "Kettlebell Row",
    "کشتی گیر بریج فقط با آموزش تخصصی": "Wrestler Bridge",
    "گریپر سنگین": "Heavy Gripper",
    "گلوت هم ریز کامل": "Full Glute-ham Raise",
    "گلوت هم ریز کمکی": "Assisted Glute-ham Raise",
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("‌", " ")).strip()


def _lookup(mapping, name: str):
    """Resolve names despite the source/database using different ZWNJ forms."""
    if name in mapping:
        return mapping[name]
    wanted = _clean(name)
    for key, value in mapping.items():
        if _clean(key) == wanted:
            return value
    raise KeyError(name)


def _english_name(name: str, section: str) -> str:
    base = _clean(name.split("—", 1)[0])
    if base in EXACT_TRANSLATIONS:
        return EXACT_TRANSLATIONS[base]
    if "/" in base:
        aliases = [part.strip() for part in base.split("/")]
        latin = next((part for part in reversed(aliases) if re.search(r"[A-Za-z]", part)), None)
        if latin:
            return latin
    translated = base
    for source, target in sorted(PHRASE_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        translated = translated.replace(_clean(source), target)
    translated = re.sub(r"[،،,:؛()]+", " ", translated)
    translated = re.sub(r"\s+", " ", translated).strip(" -")
    translated = re.sub(r"[آ-ی]", "", translated)
    translated = re.sub(r"\s+", " ", translated).strip()
    if not translated:
        translated = f"{section} Exercise"
    return translated[:160]


def _equipment(raw: str) -> str:
    normalized = raw.replace("‌", " ")
    if not normalized.strip():
        return "وزن بدن"
    for needle, value in EQUIPMENT_RULES:
        if needle in normalized:
            return value
    return "سایر"


def parse_source(path: Path):
    current_section = None
    current_level = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = _clean(raw_line)
        if line.startswith("# "):
            current_section = re.sub(r"^#\s*[۰-۹0-9]+\.\s*", "", line).strip()
            current_level = None
            continue
        if line.startswith("## "):
            current_level = line[3:].strip()
            continue
        if not line.startswith("-") or current_section not in SECTION_CONFIG or current_level not in LEVELS:
            continue
        payload = _clean(line[1:])
        if not payload or not payload.strip("-").strip():
            continue
        if "—" not in payload:
            name, raw_equipment = payload, ""
        else:
            name, raw_equipment = [part.strip() for part in payload.split("—", 1)]
        yield {
            "name": name,
            "name_en": _english_name(name, current_section),
            "raw_equipment": raw_equipment,
            "section": current_section,
            "level": current_level,
        }


class Command(BaseCommand):
    help = "Import MovementList.txt into the normalized exercise library."

    def add_arguments(self, parser):
        parser.add_argument("--source", default="MovementList.txt")
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.is_absolute():
            source = Path.cwd() / source
        if not source.exists():
            raise CommandError(f"Movement list not found: {source}")

        lookup = {}
        for model in (Muscle, ExerciseBodyPart, ExerciseMovementType, ExerciseJointType, ExercisePowerType, ExerciseDifficultyLevel, ExerciseEquipmentType):
            lookup[model] = {obj.name: obj for obj in model.objects.all()}

        created = updated = 0
        rows = list(parse_source(source))
        for row in rows:
            muscle_name, body_name, movement_name, joint_name = SECTION_CONFIG[row["section"]]
            difficulty_name = row["level"]
            defaults = {
                "name_en": row["name_en"],
                "primary_muscle": _lookup(lookup[Muscle], muscle_name),
                "body_part": _lookup(lookup[ExerciseBodyPart], body_name),
                "movement_type": _lookup(lookup[ExerciseMovementType], movement_name),
                "joint_type": _lookup(lookup[ExerciseJointType], joint_name),
                "power_type": _lookup(lookup[ExercisePowerType], "توانی" if row["level"] == "پیشرفته" else "قدرتی"),
                "difficulty_level": _lookup(lookup[ExerciseDifficultyLevel], difficulty_name),
                "equipment_type": _lookup(lookup[ExerciseEquipmentType], _equipment(row["raw_equipment"])),
                "description": (
                    f"کتابخانه حرکات ایگوفیت؛ گروه هدف: {row['section']}. "
                    f"تجهیزات استفاده‌شده: {row['raw_equipment'] or 'بدون ابزار مشخص'}؛ "
                    f"سطح: {row['level']}."
                ),
            }
            exercise = Exercise.objects.filter(
                name=row["name"],
                difficulty_level=defaults["difficulty_level"],
                primary_muscle=defaults["primary_muscle"],
            ).first()
            if exercise:
                for key, value in defaults.items():
                    setattr(exercise, key, value)
                exercise.save(update_fields=list(defaults))
                updated += 1
            else:
                Exercise.objects.create(name=row["name"], **defaults)
                created += 1

        if options["dry_run"]:
            transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(
            f"Parsed {len(rows)} movements; created {created}, updated {updated}"
            + (" (dry run; rolled back)" if options["dry_run"] else ".")
        ))

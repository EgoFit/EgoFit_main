from django.db import migrations


CATEGORIES = (
    ("سینه", "Chest"),
    ("بخش بالایی پشت", "Upper Back"),
    ("بخش پایینی پشت", "Lower Back & Core"),
    ("شانه", "Shoulders"),
    ("جلو بازو", "Biceps"),
    ("پشت بازو", "Triceps"),
    ("پا", "Legs"),
    ("ساق", "Calves"),
    ("سرینی", "Glutes"),
    ("ساعد", "Forearms"),
)


MUSCLE_CATEGORY = (
    ("سه‌سر بازویی", "پشت بازو"),
    ("دوسر بازویی", "جلو بازو"),
    ("بازویی-زندی", "جلو بازو"),
    ("راست‌کننده ستون فقرات", "بخش پایینی پشت"),
    ("جناغی-چنبری", "بخش پایینی پشت"),
    ("چرخاننده گرد ساعد", "ساعد"),
    ("نزدیک‌کننده", "پا"),
    ("نیم‌تاندونی", "پا"),
    ("نیم‌غشایی", "پا"),
    ("دوقلوی ساق", "ساق"),
    ("عرضی شکمی", "بخش پایینی پشت"),
    ("تانسور فاسیا", "پا"),
    ("شانه‌ای ران", "پا"),
    ("راست شکمی", "بخش پایینی پشت"),
    ("راست رانی", "پا"),
    ("دوسر رانی", "پا"),
    ("ذوزنقه‌ای", "بخش بالایی پشت"),
    ("لاتيسموس", "بخش بالایی پشت"),
    ("دلتوئيد", "شانه"),
    ("سرینی", "سرینی"),
    ("سینه", "سینه"),
    ("مایل", "بخش پایینی پشت"),
    ("بازویی", "جلو بازو"),
    ("مچ", "ساعد"),
    ("انگشتان", "ساعد"),
    ("پهن", "پا"),
    ("لوزی", "بخش بالایی پشت"),
    ("نعلی", "ساق"),
    ("درشت‌نی", "ساق"),
    ("نازک‌نی", "ساق"),
    ("خیاطه", "پا"),
    ("لطیفه", "پا"),
    ("پری فورمیس", "سرینی"),
    ("گرد بزرگ", "بخش بالایی پشت"),
    ("فوق خاری", "شانه"),
    ("تحت خاری", "شانه"),
    ("ساب‌اسکاپولاریس", "شانه"),
)


def fix_category_assignments(apps, schema_editor):
    Exercise = apps.get_model("account", "Exercise")
    ExerciseBodyPart = apps.get_model("account", "ExerciseBodyPart")
    ExerciseSecondaryMovementType = apps.get_model(
        "account", "ExerciseSecondaryMovementType"
    )
    body_part_categories = {item.name: item for item in ExerciseBodyPart.objects.all()}
    secondary_movement_categories = {
        name: ExerciseSecondaryMovementType.objects.update_or_create(
            name=name, defaults={"name_en": name_en}
        )[0]
        for name, name_en in CATEGORIES
    }

    for exercise in Exercise.objects.select_related("primary_muscle"):
        category_name = next(
            (target for keyword, target in MUSCLE_CATEGORY if keyword in exercise.primary_muscle.name),
            "بخش پایینی پشت",
        )
        exercise.body_part_id = body_part_categories[category_name].pk
        exercise.secondary_movement_type_id = secondary_movement_categories[category_name].pk
        exercise.save(update_fields=["body_part", "secondary_movement_type"])


class Migration(migrations.Migration):
    dependencies = [("account", "0061_categorize_bodybuilding_exercises")]

    operations = [migrations.RunPython(fix_category_assignments, migrations.RunPython.noop)]

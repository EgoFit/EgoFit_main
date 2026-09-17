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


MUSCLE_CATEGORY = {
    "سینه": "سینه",
    "ذوزنقه‌ای": "بخش بالایی پشت",
    "لاتيسموس": "بخش بالایی پشت",
    "لوزی": "بخش بالایی پشت",
    "گرد بزرگ": "بخش بالایی پشت",
    "راست‌کننده ستون فقرات": "بخش پایینی پشت",
    "راست شکمی": "بخش پایینی پشت",
    "مایل": "بخش پایینی پشت",
    "عرضی شکمی": "بخش پایینی پشت",
    "جناغی-چنبری": "بخش پایینی پشت",
    "دلتوئيد": "شانه",
    "فوق خاری": "شانه",
    "تحت خاری": "شانه",
    "ساب‌اسکاپولاریس": "شانه",
    "دوسر بازویی": "جلو بازو",
    "بازویی": "جلو بازو",
    "بازویی-زندی": "جلو بازو",
    "سه‌سر بازویی": "پشت بازو",
    "راست رانی": "پا",
    "دوسر رانی": "پا",
    "نیم‌تاندونی": "پا",
    "نیم‌غشایی": "پا",
    "نزدیک‌کننده": "پا",
    "پهن": "پا",
    "خیاطه": "پا",
    "تانسور فاسیا": "پا",
    "شانه‌ای ران": "پا",
    "لطیفه": "پا",
    "دوقلوی ساق": "ساق",
    "نعلی": "ساق",
    "درشت‌نی": "ساق",
    "نازک‌نی": "ساق",
    "سرینی": "سرینی",
    "پری فورمیس": "سرینی",
    "مچ": "ساعد",
    "انگشتان": "ساعد",
    "چرخاننده گرد ساعد": "ساعد",
}


def categorize_exercises(apps, schema_editor):
    Exercise = apps.get_model("account", "Exercise")
    ExerciseBodyPart = apps.get_model("account", "ExerciseBodyPart")

    categories = {
        name: ExerciseBodyPart.objects.update_or_create(
            name=name, defaults={"name_en": name_en}
        )[0]
        for name, name_en in CATEGORIES
    }

    for exercise in Exercise.objects.select_related("primary_muscle"):
        muscle_name = exercise.primary_muscle.name
        category_name = next(
            (target for keyword, target in MUSCLE_CATEGORY.items() if keyword in muscle_name),
            "بخش پایینی پشت",
        )
        exercise.body_part_id = categories[category_name].pk
        exercise.save(update_fields=["body_part"])


class Migration(migrations.Migration):
    dependencies = [("account", "0060_unique_active_access_payments")]

    operations = [migrations.RunPython(categorize_exercises, migrations.RunPython.noop)]

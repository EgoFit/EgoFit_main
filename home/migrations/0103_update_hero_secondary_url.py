from django.db import migrations


def update_hero_secondary_url(apps, schema_editor):
    HomePage = apps.get_model("home", "HomePage")
    HomePage.objects.filter(hero_secondary_url="/contact_us/").update(hero_secondary_url="/series/")


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0102_alter_homepage_article_button_label_and_more"),
    ]

    operations = [
        migrations.RunPython(update_hero_secondary_url, migrations.RunPython.noop),
    ]

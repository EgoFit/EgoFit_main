from django.db import migrations


NAV_LINKS = [
    ("صفحه اصلی", "/", 0),
    ("مقالات آموزشی", "/blog/", 1),
    ("درباره ما", "/about_us/", 2),
    ("تماس با ما", "/contact_us/", 3),
    ("آرشیو دوره‌ها", "/series/", 4),
]


def seed_navigation_links(apps, schema_editor):
    NavigationLink = apps.get_model("home", "NavigationLink")
    if NavigationLink.objects.exists():
        return
    for label, url, sort_order in NAV_LINKS:
        NavigationLink.objects.create(label=label, url=url, sort_order=sort_order)


def remove_navigation_links(apps, schema_editor):
    NavigationLink = apps.get_model("home", "NavigationLink")
    NavigationLink.objects.filter(url__in=[url for _, url, _ in NAV_LINKS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0104_bloglistingpage_contactpage_navigationlink_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_navigation_links, remove_navigation_links),
    ]

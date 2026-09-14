from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import models
from django.utils.text import slugify

from account.models import User
from cart.models import DiscountCode
from home.models import (
    AboutPage,
    Activity,
    Advantage,
    ArticleBlogModel,
    Category,
    CategoryBlog,
    Community,
    Counseling,
    DownContent,
    Episode,
    Footer,
    HomePage,
    HomePageFeaturePoint,
    HomePageHighlightCard,
    HomePageMetric,
    HomePageTrustItem,
    Season,
    SeriesModel,
)
from home.services.series_service import SeriesService
from home.signals import HOME_PAGE_CACHE_PREFIX


def _demo_image_source() -> Path:
    media_root = Path(settings.MEDIA_ROOT)
    for candidate in (
        media_root / "series_courses" / "free-course.png",
        media_root / "series_courses" / "paid-course.png",
    ):
        if candidate.exists():
            return candidate

    target = media_root / "series_courses" / "demo-placeholder.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return target


def _copy_demo_image(relative_path: str) -> str:
    target = Path(settings.MEDIA_ROOT) / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(_demo_image_source(), target)
    return relative_path.replace("\\", "/")


def _save_model(instance) -> None:
    models.Model.save(instance)


@contextmanager
def _skip_series_notifications():
    original = SeriesService.create_series_notifications_on_commit

    def noop(*args, **kwargs):
        return None

    SeriesService.create_series_notifications_on_commit = staticmethod(noop)
    try:
        yield
    finally:
        SeriesService.create_series_notifications_on_commit = original


class Command(BaseCommand):
    help = "Seed demo categories, courses, blog posts, and homepage CMS content."

    DEMO_MARKER_SLUG = "tanasob-andam"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-run seeding even if demo data already exists.",
        )

    def handle(self, *args, **options):
        if not options["force"] and Category.objects.filter(slug=self.DEMO_MARKER_SLUG).exists():
            self.stdout.write(self.style.WARNING("Demo data already exists. Use --force to seed again."))
            return

        with _skip_series_notifications():
            instructors = self._create_instructors()
            course_categories = self._create_course_categories()
            blog_categories = self._create_blog_categories()
            courses = self._create_courses(instructors, course_categories)
            self._create_seasons_and_episodes(courses)
            self._create_articles(instructors, blog_categories)
            self._create_cms_content()
            self._create_discount_codes()

        cache.delete(f"{HOME_PAGE_CACHE_PREFIX}:home:v1")
        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))

    def _create_instructors(self) -> list[User]:
        specs = [
            ("مدرس دمو علی", "09123456781"),
            ("مدرس دمو سارا", "09123456782"),
            ("مدرس دمو محمد", "09123456783"),
        ]
        instructors = []
        for fullname, phone in specs:
            user, _ = User.objects.get_or_create(
                fullname=fullname,
                defaults={"phone": phone},
            )
            instructors.append(user)
        return instructors

    def _create_course_categories(self) -> dict[str, Category]:
        items = [
            ("تناسب اندام", "tanasob-andam"),
            ("بدنسازی", "badnesazi"),
            ("تغذیه ورزشی", "taghzie-varzeshi"),
            ("یوگا و مدیتیشن", "yoga-meditation"),
            ("آمادگی جسمانی", "amadegi-jesmani"),
            ("وزنه‌برداری", "vazne-bardari"),
        ]
        return {
            slug: Category.objects.get_or_create(slug=slug, defaults={"title": title})[0]
            for title, slug in items
        }

    def _create_blog_categories(self) -> dict[str, CategoryBlog]:
        items = [
            ("آموزش", "amoozesh"),
            ("تغذیه", "taghzie-blog"),
            ("اخبار", "akhbar"),
            ("تمرینات", "tamarinat"),
        ]
        return {
            slug: CategoryBlog.objects.get_or_create(slug=slug, defaults={"title": title})[0]
            for title, slug in items
        }

    def _create_courses(
        self,
        instructors: list[User],
        categories: dict[str, Category],
    ) -> list[SeriesModel]:
        course_specs = [
            ("بدنسازی مقدماتی", "badnesazi", True, False, "850000", "690000", 3, 12),
            ("تغذیه ورزشی حرفه‌ای", "taghzie-varzeshi", True, False, "720000", "590000", 2, 8),
            ("یوگا برای مبتدیان", "yoga-meditation", True, True, "0", "0", 2, 6),
            ("آمادگی جسمانی خانگی", "amadegi-jesmani", False, True, "0", "0", 4, 10),
            ("وزنه‌برداری المپیکی", "vazne-bardari", True, False, "980000", "820000", 3, 14),
            ("تناسب اندام بانوان", "tanasob-andam", True, False, "650000", "520000", 2, 9),
            ("HIIT و چربی‌سوزی", "tanasob-andam", True, True, "0", "0", 3, 7),
            ("کشش و انعطاف‌پذیری", "yoga-meditation", True, False, "480000", "390000", 2, 5),
        ]

        courses = []
        for index, (title, category_slug, completed, free, main_price, discount_price, seasons, hours) in enumerate(course_specs):
            existing = SeriesModel.objects.filter(title=title).first()
            if existing:
                courses.append(existing)
                continue

            author = instructors[index % len(instructors)]
            category = categories[category_slug]
            image_path = _copy_demo_image(f"series_courses/demo-{slugify(title) or index}.png")
            course = SeriesModel(
                title=title,
                image=image_path,
                is_compeleted=completed,
                language_kinds=category,
                seseaons=seasons,
                hours=hours,
                author=author,
                main_price=main_price,
                discount_price=discount_price,
                free=free,
                description=f"دوره {title} با تمرکز بر اصول علمی و برنامه‌ریزی عملی.",
                introdution_course=f"در این دوره با مبانی {title} آشنا می‌شوید.",
                course_extra_des1="ویدیوهای آموزشی با کیفیت HD",
                course_extra_des2="پشتیبانی مدرس در طول دوره",
            )
            _save_model(course)
            courses.append(course)
            self.stdout.write(f"  + course #{course.pk}")
        return courses

    def _create_seasons_and_episodes(self, courses: list[SeriesModel]) -> None:
        for course in courses:
            season_count = course.seseaons or 2
            for season_number in range(1, season_count + 1):
                season, _ = Season.objects.get_or_create(
                    series=course,
                    number=season_number,
                    defaults={"title": f"فصل {season_number}"},
                )
                for episode_number in range(1, 4):
                    Episode.objects.get_or_create(
                        season=season,
                        episode_number=episode_number,
                        defaults={
                            "title": f"جلسه {episode_number}",
                            "duration": "12:30",
                            "duration_seconds": 750,
                        },
                    )

    def _create_articles(
        self,
        instructors: list[User],
        categories: dict[str, CategoryBlog],
    ) -> None:
        article_specs = [
            ("۱۰ نکته برای شروع بدنسازی", "amoozesh", "badnesazi-shoro", 5),
            ("رژیم غذایی مناسب ورزشکاران", "taghzie-blog", "regime-varzeshkaran", 7),
            ("فواید یوگا برای سلامت روان", "amoozesh", "yoga-salamat-ravan", 4),
            ("جدیدترین متدهای تمرین HIIT", "tamarinat", "hiit-jadid", 6),
            ("اهمیت گرم کردن قبل از تمرین", "amoozesh", "garm-kardan", 3),
            ("مصرف پروتئین: چقدر و چه زمانی؟", "taghzie-blog", "protein-zaman", 8),
            ("افتتاح کلاس‌های جدید پاییز", "akhbar", "kelas-paeiz", 2),
            ("تمرینات خانگی بدون تجهیزات", "tamarinat", "tamarin-khane", 5),
        ]

        for index, (title, category_slug, slug, reading_time) in enumerate(article_specs):
            if ArticleBlogModel.objects.filter(slug=slug).exists():
                continue

            author = instructors[index % len(instructors)]
            category = categories[category_slug]
            image_path = _copy_demo_image(f"articles_blog/demo-{slug}.png")
            article = ArticleBlogModel(
                title=title,
                language_kinds=category,
                image=image_path,
                author=author,
                reading_time=reading_time,
                article_excerpt=f"خلاصه مقاله: {title}",
                article_description=(
                    f"<p>در این مقاله درباره «{title}» صحبت می‌کنیم.</p>"
                    "<p>این محتوا برای پر کردن سایت در محیط توسعه ایجاد شده است.</p>"
                ),
                slug=slug,
            )
            _save_model(article)
            self.stdout.write(f"  + article #{article.pk}")

    def _create_cms_content(self) -> None:
        home_page, _ = HomePage.objects.get_or_create(
            slug="home",
            defaults={
                "title": "صفحه اصلی",
                "hero_eyebrow": "پلتفرم آموزش تناسب اندام",
                "hero_title": "مسیر سلامتی خود را با EgoFit شروع کنید",
                "hero_description": "دوره‌های تخصصی بدنسازی، تغذیه و آمادگی جسمانی با مدرسین حرفه‌ای.",
                "hero_primary_label": "مشاهده دوره‌ها",
                "hero_primary_url": "/series/",
                "hero_secondary_label": "مقالات آموزشی",
                "hero_secondary_url": "/blog/",
                "stats_eyebrow": "آمار پلتفرم",
                "stats_title": "اعتماد هزاران ورزشکار",
                "stats_description": "دوره‌ها و مقالات به‌روز برای همه سطوح.",
                "featured_courses_eyebrow": "دوره‌های ویژه",
                "featured_courses_title": "جدیدترین دوره‌های آموزشی",
                "featured_courses_description": "از مبتدی تا حرفه‌ای، دوره مناسب خود را پیدا کنید.",
                "featured_courses_button_label": "همه دوره‌ها",
                "featured_courses_button_url": "/series/",
                "article_eyebrow": "وبلاگ",
                "article_title": "آخرین مقالات",
                "article_description": "نکات تمرینی، تغذیه و سبک زندگی سالم.",
                "article_button_label": "مشاهده وبلاگ",
                "article_button_url": "/blog/",
            },
        )

        if not home_page.hero_image:
            HomePage.objects.filter(pk=home_page.pk).update(
                hero_image=_copy_demo_image("home_images/hero-demo.png"),
            )

        metrics = [
            (1, "۱۲۰۰+", "کاربر فعال", "ورزشکاران ثبت‌نام‌شده"),
            (2, "۵۰+", "دوره آموزشی", "محتوای تخصصی"),
            (3, "۸+", "مدرس تخصصی", "دسته‌بندی متنوع"),
            (4, "۲۴/۷", "پشتیبانی", "همراهی مدرسین"),
        ]
        for sort_order, value, title, description in metrics:
            HomePageMetric.objects.get_or_create(
                home_page=home_page,
                sort_order=sort_order,
                defaults={"value": value, "title": title, "description": description},
            )

        trust_items = [
            (1, "پرداخت امن"),
            (2, "ضمانت کیفیت"),
            (3, "مدرسین مجرب"),
        ]
        for sort_order, title in trust_items:
            HomePageTrustItem.objects.get_or_create(
                home_page=home_page,
                sort_order=sort_order,
                defaults={"title": title},
            )

        features = [
            (1, "محتوای ویدیویی باکیفیت", HomePageFeaturePoint.IconChoices.BOOK),
            (2, "دسترسی مادام‌العمر", HomePageFeaturePoint.IconChoices.SHIELD),
            (3, "برنامه تمرینی شخصی", HomePageFeaturePoint.IconChoices.LIGHTNING),
            (4, "پشتیبانی آنلاین", HomePageFeaturePoint.IconChoices.SUPPORT),
        ]
        for sort_order, title, icon in features:
            HomePageFeaturePoint.objects.get_or_create(
                home_page=home_page,
                sort_order=sort_order,
                defaults={"title": title, "icon": icon},
            )

        highlights = [
            (HomePageHighlightCard.PositionChoices.TOP, "شروع رایگان", "چند دوره رایگان برای شروع مسیر ورزشی."),
            (HomePageHighlightCard.PositionChoices.BOTTOM, "تخفیف ویژه", "کد DEMO20 برای ۲۰٪ تخفیف اولین خرید."),
        ]
        for position, title, description in highlights:
            HomePageHighlightCard.objects.get_or_create(
                home_page=home_page,
                position=position,
                defaults={"title": title, "description": description},
            )

        Footer.objects.get_or_create(
            about_us="EgoFit پلتفرم آموزش تناسب اندام و سبک زندگی سالم.",
            defaults={
                "phone_number": "021-12345678",
                "working_hours": "شنبه تا پنجشنبه ۹ تا ۱۸",
                "address": "تهران، خیابان ولیعصر",
                "email": "info@egofit.ir",
                "copyright_year": 2026,
                "social_media": {
                    "instagram": "https://instagram.com/egofit",
                    "telegram": "https://t.me/egofit",
                },
            },
        )

        if not Counseling.objects.exists():
            counseling = Counseling(
                title="مشاوره رایگان",
                subtitle="با مربیان ما صحبت کنید",
                description="برای انتخاب بهترین برنامه تمرینی، یک جلسه مشاوره رایگان رزرو کنید.",
                button_content="درخواست مشاوره",
                image=_copy_demo_image("counseling_images/demo-counseling.png"),
            )
            _save_model(counseling)

        if not Advantage.objects.exists():
            advantage = Advantage(
                title="یادگیری عملی",
                description="تمرین همراه با ویدیو و برنامه هفتگی",
                image=_copy_demo_image("images/demo-advantage.png"),
            )
            _save_model(advantage)

        down_cards = [
            ("تمرین در خانه", "بدون نیاز به باشگاه، با تجهیزات ساده."),
            ("تغذیه علمی", "برنامه غذایی متناسب با هدف شما."),
            ("پیگیری پیشرفت", "ابزارهای اندازه‌گیری و گزارش."),
        ]
        for title, description in down_cards:
            DownContent.objects.get_or_create(title=title, defaults={"description": description})

        if not AboutPage.objects.exists():
            about = AboutPage(
                title="درباره EgoFit",
                description="ما با هدف democratize کردن آموزش ورزشی، دوره‌های باکیفیت در اختیار همه قرار می‌دهیم.",
                image=_copy_demo_image("about_images/demo-about.png"),
            )
            _save_model(about)

        activity_specs = [
            ("کارگاه بدنسازی", "کارگاه حضوری ماهانه"),
            ("چالش ۳۰ روزه", "چالش آمادگی جسمانی"),
        ]
        for title, description in activity_specs:
            if Activity.objects.filter(title=title).exists():
                continue
            activity = Activity(
                title=title,
                description=description,
                image=_copy_demo_image(f"activity_images/demo-{slugify(title)}.png"),
            )
            _save_model(activity)

        community_specs = [
            ("انجمن ورزشکاران", "گفت‌وگو و تبادل تجربه"),
            ("گروه تلگرامی", "پشتیبانی و اطلاع‌رسانی"),
        ]
        for title, description in community_specs:
            if Community.objects.filter(title=title).exists():
                continue
            community = Community(
                title=title,
                description=description,
                image=_copy_demo_image(f"community_images/demo-{slugify(title)}.png"),
            )
            _save_model(community)

    def _create_discount_codes(self) -> None:
        DiscountCode.objects.get_or_create(
            name="DEMO20",
            defaults={"percentage": 20, "quantity": 100, "is_active": True},
        )

import os

from django.db import models
from moviepy.video.io.VideoFileClip import VideoFileClip

from account.models import User



class Comment(models.Model):
    class PublicationStatus(models.TextChoices):
        PENDING = "pending", "در انتظار بررسی"
        APPROVED = "approved", "تایید شده"
        REJECTED = "rejected", "رد شده"

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="contact_comments")
    comment = models.TextField()
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=False, verbose_name="منتشر شود")
    admin_response = models.TextField(blank=True, verbose_name="پاسخ مدیر")
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان پاسخ")
    publication_status = models.CharField(max_length=16, choices=PublicationStatus.choices, default=PublicationStatus.PENDING, db_index=True)


    class Meta:
        verbose_name_plural= "نظرات"

    def __str__(self):
        return self.name




class Category(models.Model):
    title = models.CharField(max_length=100, null=True, blank=True, verbose_name='عنوان دسته بندی', help_text='عنوان دسته بندی را وارد کنید')
    slug = models.SlugField(null=True, db_index=True, verbose_name='اسلاگ', help_text='اسلاگ دسته بندی را وارد کنید')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'دسته بندی'
        verbose_name_plural = 'دسته بندی ها'
        indexes = [
            models.Index(fields=['slug']),
        ]






class SeriesModel(models.Model):
    title = models.CharField(max_length=50, verbose_name='عنوان', db_index=True)
    image = models.ImageField(upload_to='series_courses', verbose_name='تصویر')
    is_compeleted = models.BooleanField(default=True, verbose_name='تکمیل شده', db_index=True)
    language_kinds = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE,
                                       related_name='categories', verbose_name="زبان")
    seseaons = models.IntegerField(verbose_name='تعداد فصل', null=True, blank=True)
    hours = models.IntegerField(verbose_name='تعداد ساعت', null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='author', verbose_name='مولف')
    main_price = models.CharField(max_length=20, verbose_name='قیمت اصلی', null=True, blank=True)
    discount_price = models.CharField(max_length=20, null=True, blank=True, verbose_name='قیمت تخفیف')
    description = models.TextField(null=True, blank=True, verbose_name='توضیحات')
    introdution_course = models.TextField(null=True, blank=True, verbose_name='معرفی دوره')
    course_extra_des1 = models.TextField(blank=True, null=True, verbose_name='توضیحات اضافی 1')
    course_extra_des2 = models.TextField(blank=True, null=True, verbose_name='توضیحات اضافی 2')
    built_in = models.TextField(blank=True, null=True, verbose_name='ساختار')
    author_description = models.TextField(blank=True, null=True, verbose_name='توضیحات مولف')
    free = models.BooleanField(default=True, verbose_name='رایگان')
    author_image = models.ImageField(upload_to="images", blank=True, null=True)

    def save(self, *args, **kwargs):
        previous_state = None
        if self.pk:
            previous_state = SeriesModel.objects.only("id", "title", "is_compeleted").get(pk=self.pk)

        super().save(*args, **kwargs)

        from home.services.series_service import SeriesService

        SeriesService().create_series_notifications_on_commit(series=self, previous_state=previous_state)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "دوره"
        verbose_name_plural = 'دوره ها'
        indexes = [
            models.Index(fields=['author', 'id']),
            models.Index(fields=['language_kinds', 'id']),
            models.Index(fields=['free', 'id']),
            models.Index(fields=['is_compeleted', 'id']),
        ]



class Advantage(models.Model):
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    image = models.ImageField(upload_to='images', null=True, blank=True)
    

    def __str__(self):
        return self.title




class UserCourse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_courses')
    series = models.ForeignKey('SeriesModel', on_delete=models.CASCADE, related_name='series_users')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'series')
        indexes = [
            models.Index(fields=['user', 'series']),
            models.Index(fields=['series', 'added_at']),
        ]














class Season(models.Model):
    class Meta:
        verbose_name = "فصل"
        verbose_name_plural= "فصل ها"
        ordering = ['number', 'id']
        indexes = [
            models.Index(fields=['series', 'number']),
        ]

    series = models.ForeignKey(SeriesModel, on_delete=models.CASCADE, related_name='seasons', null=True, blank=True,
                               verbose_name='دوره ها')
    number = models.IntegerField(null=True, blank=True, verbose_name='شماره فصل')
    title = models.CharField(max_length=50, null=True, blank=True, verbose_name='عنوان فصل')



    def __str__(self):
        return self.title

    def total_duration_seconds(self):
        total_duration = 0
        for episode in self.episodes.all():
            total_duration += episode.get_duration_in_seconds()
        return total_duration

    def number_of_episodes(self):
        return self.episodes.count()



from django.core.files.temp import NamedTemporaryFile

class Episode(models.Model):
    season = models.ForeignKey('Season', on_delete=models.CASCADE, related_name='episodes', null=True, blank=True, verbose_name='فصل')
    episode_number = models.IntegerField(null=True, blank=True, verbose_name='شماره اپیزود')
    title = models.CharField(max_length=255, null=True, blank=True, verbose_name='عنوان')
    duration = models.CharField(max_length=20, null=True, blank=True, verbose_name='مدت زمان')
    duration_seconds = models.PositiveIntegerField(default=0, editable=False)
    video_file = models.FileField(upload_to='videos/', null=True, blank=True, verbose_name='فایل ویدئو')

    class Meta:
        verbose_name = 'اپیزود'
        verbose_name_plural = 'اپیزودها'
        ordering = ['episode_number', 'id']
        indexes = [
            models.Index(fields=['season', 'episode_number']),
        ]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        video_has_changed = self._video_file_has_changed()
        super().save(*args, **kwargs)

        if not self.video_file:
            if self.duration or self.duration_seconds:
                self.duration = None
                self.duration_seconds = 0
                super().save(update_fields=['duration', 'duration_seconds'])
            return

        if not video_has_changed and update_fields is not None and 'video_file' not in update_fields:
            return

        if not video_has_changed and self.duration_seconds:
            return

        duration_seconds = self._extract_duration_seconds()
        formatted_duration = self._format_duration(duration_seconds)

        if self.duration != formatted_duration or self.duration_seconds != duration_seconds:
            self.duration = formatted_duration
            self.duration_seconds = duration_seconds
            super().save(update_fields=['duration', 'duration_seconds'])

    def get_duration_in_seconds(self):
        if self.duration_seconds:
            return self.duration_seconds
        if self.duration:
            parts = self.duration.split(':')
            if len(parts) == 2:  # format is mm:ss
                return int(parts[0]) * 60 + int(parts[1])
            if len(parts) == 3:
                return (int(parts[0]) * 3600) + (int(parts[1]) * 60) + int(parts[2])
        return 0  # Default to 0 if duration is not set

    def _video_file_has_changed(self):
        if not self.pk:
            return bool(self.video_file)

        previous_video_name = (
            Episode.objects.filter(pk=self.pk)
            .values_list('video_file', flat=True)
            .first()
        )
        current_video_name = self.video_file.name if self.video_file else ''
        return previous_video_name != current_video_name

    def _extract_duration_seconds(self):
        self.video_file.open('rb')
        try:
            with NamedTemporaryFile() as temp_video:
                for chunk in self.video_file.chunks():
                    temp_video.write(chunk)
                temp_video.flush()

                clip = VideoFileClip(temp_video.name)
                try:
                    return int(clip.duration or 0)
                finally:
                    clip.close()
        finally:
            self.video_file.close()

    @staticmethod
    def _format_duration(total_seconds):
        minutes, seconds = divmod(int(total_seconds or 0), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def __str__(self):
        return f"{self.title} (Episode {self.episode_number})"




class CategoryBlog(models.Model):
    title = models.CharField(max_length=100, null=True, blank=True, verbose_name='عنوان دسته بندی', help_text='عنوان دسته بندی را وارد کنید')
    slug = models.SlugField(null=True, verbose_name='اسلاگ', help_text='اسلاگ دسته بندی را وارد کنید')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'دسته بندی'
        verbose_name_plural = 'دسته بندی بلاگ ها'




class ArticleBlogModel(models.Model):
    title = models.CharField(max_length=100)
    language_kinds = models.ForeignKey(CategoryBlog, null=True, blank=True, on_delete=models.CASCADE,
                                       related_name='article_categories', verbose_name="زبان")
    image = models.ImageField(upload_to='articles_blog')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='article')
    reading_time = models.IntegerField()
    article_excerpt = models.TextField(blank=True, null=True)
    article_description = models.TextField(blank=True, null=True)
    built_in = models.TextField(blank=True, null=True)
    article_extra_des1 = models.TextField(blank=True, null=True)
    article_extra_des2 = models.TextField(blank=True, null=True)
    author_description = models.TextField(blank=True, null=True)
    author_image = models.ImageField(upload_to='images',blank=True, null=True)
    slug = models.SlugField(unique=True, blank=True, null=True, db_index=True)




    class Meta:
        verbose_name = 'وبلاگ'
        verbose_name_plural ='وبلاگ ها'
        indexes = [
            models.Index(fields=['author', 'id']),
            models.Index(fields=['language_kinds', 'id']),
        ]



    def __str__(self):
        return self.title








class ArticleBlogImage(models.Model):
    article = models.ForeignKey(
        ArticleBlogModel,
        on_delete=models.CASCADE,
        related_name="gallery_images",
        verbose_name="مقاله",
    )
    image = models.ImageField(upload_to="articles_blog/gallery", verbose_name="تصویر")
    alt_text = models.CharField(max_length=255, blank=True, verbose_name="متن جایگزین")
    caption = models.CharField(max_length=255, blank=True, verbose_name="عنوان تصویر")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "تصویر مقاله"
        verbose_name_plural = "تصاویر مقاله"

    def __str__(self):
        return self.caption or self.alt_text or f"تصویر مقاله {self.article_id}"


class ArticleBlogLink(models.Model):
    article = models.ForeignKey(
        ArticleBlogModel,
        on_delete=models.CASCADE,
        related_name="article_links",
        verbose_name="مقاله",
    )
    label = models.CharField(max_length=255, verbose_name="متن لینک")
    url = models.CharField(max_length=500, verbose_name="آدرس لینک")
    open_in_new_tab = models.BooleanField(
        default=True,
        verbose_name="باز شدن در زبانه جدید",
    )
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "لینک مقاله"
        verbose_name_plural = "لینک‌های مقاله"

    def clean(self):
        from home.rich_text import validate_article_url

        self.url = validate_article_url(self.url)

    def __str__(self):
        return self.label


class CommentSectionModel(models.Model):
    class PublicationStatus(models.TextChoices):
        PENDING = "pending", "در انتظار بررسی"
        APPROVED = "approved", "تایید شده"
        REJECTED = "rejected", "رد شده"

    series = models.ForeignKey(SeriesModel, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    is_active = models.BooleanField(default=False)
    publication_status = models.CharField(max_length=16, choices=PublicationStatus.choices, default=PublicationStatus.PENDING, db_index=True)

    class Meta:
        verbose_name = "کامنت"
        verbose_name_plural = "کامنت ها"
        indexes = [
            models.Index(fields=['series', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['is_active', 'created_at']),
        ]

    def __str__(self):
        if self.user:
            return f"Comment by {self.user.fullname} on {self.series.title}"
        else:
            return f"Comment by Anonymous on {self.series.title}"


class Reply(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.ForeignKey(CommentSectionModel, on_delete=models.CASCADE, related_name='reply_set')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        verbose_name = "ریپلای"
        verbose_name_plural = "ریپلای ها"
        indexes = [
            models.Index(fields=['comment', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['is_active', 'created_at']),
        ]

    def __str__(self):
        return f"Reply by {self.user.fullname} on {self.comment.series.title}"




class Footer(models.Model):
    about_us = models.TextField(verbose_name='درباره ما')
    phone_number = models.CharField(max_length=20, verbose_name='شماره تلفن', blank=True, null=True)
    working_hours = models.CharField(max_length=50, verbose_name='ساعات کاری',blank=True, null=True)
    address = models.TextField(verbose_name='آدرس', blank=True)
    email = models.EmailField(verbose_name='ایمیل', blank=True)
    copyright_year = models.IntegerField(verbose_name=  'سال کپی رایت',blank=True, null=True)
    show_social_media = models.BooleanField(verbose_name='نمایش شبکه های اجتماعی', default=True,blank=True, null=True)
    social_media = models.JSONField(verbose_name='شبکه های اجتماعی', blank=True, null=True)
    about_eyebrow = models.CharField(max_length=120, blank=True, null=True, verbose_name="متن بالای بخش درباره")
    about_title = models.CharField(max_length=255, blank=True, null=True, verbose_name="عنوان بخش درباره")
    links_section_title = models.CharField(max_length=120, blank=True, null=True, verbose_name="عنوان بخش لینک‌های مفید")
    social_section_title = models.CharField(max_length=120, blank=True, null=True, verbose_name="عنوان بخش شبکه‌های اجتماعی")
    trust_text = models.TextField(blank=True, null=True, verbose_name="متن نماد اعتماد")

    class Meta:
        verbose_name = 'فوتر'
        verbose_name_plural = 'فوتر'

    def __str__(self):
        return 'پاورقی'











class SiteSettings(models.Model):
    slug = models.SlugField(default="default", unique=True, editable=False, db_index=True)
    brand_eyebrow = models.CharField(max_length=60, blank=True, null=True, verbose_name="متن کوچک برند")
    brand_name = models.CharField(max_length=60, blank=True, null=True, verbose_name="نام برند")
    logo = models.ImageField(upload_to="site/", null=True, blank=True, verbose_name="لوگو")
    tagline = models.CharField(max_length=255, blank=True, null=True, verbose_name="شعار سایت")
    header_search_placeholder = models.CharField(max_length=120, blank=True, null=True, verbose_name="متن جای‌خالی جستجو")
    default_meta_title = models.CharField(max_length=120, blank=True, null=True, verbose_name="عنوان پیش‌فرض صفحات")

    class Meta:
        verbose_name = "تنظیمات سایت"
        verbose_name_plural = "تنظیمات سایت"

    def __str__(self):
        return self.brand_name or "تنظیمات سایت"


class NavigationLink(models.Model):
    label = models.CharField(max_length=60, verbose_name="عنوان")
    url = models.CharField(max_length=255, verbose_name="لینک")
    sort_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "لینک ناوبری"
        verbose_name_plural = "لینک‌های ناوبری"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.label


class AboutPage(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='about_images')

class Activity(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='activity_images')

class Community(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='community_images')


class Counseling(models.Model):
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='counseling_images/')
    button_content = models.CharField(max_length=100,blank=True, null=True)

    class Meta:
        verbose_name_plural = "بدنه"

    def __str__(self):
        return self.title




class DownContent(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()


    class Meta :
        verbose_name_plural = "بخش پایین سایت"




    def __str__(self):
        return self.title


class HomePage(models.Model):
    slug = models.SlugField(default="home", unique=True, editable=False, db_index=True)
    title = models.CharField(max_length=120, blank=True, null=True, verbose_name="عنوان صفحه")

    hero_eyebrow = models.CharField(max_length=120, blank=True, null=True, verbose_name="متن بالای هدر")
    hero_title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="عنوان هدر",
    )
    hero_description = models.TextField(
        blank=True,
        null=True,
        verbose_name="توضیحات هدر",
    )
    hero_primary_label = models.CharField(max_length=80, blank=True, null=True, verbose_name="متن دکمه اصلی")
    hero_primary_url = models.CharField(max_length=255, blank=True, null=True, verbose_name="لینک دکمه اصلی")
    hero_secondary_label = models.CharField(max_length=80, blank=True, null=True, verbose_name="متن دکمه دوم")
    hero_secondary_url = models.CharField(max_length=255, blank=True, null=True, verbose_name="لینک دکمه دوم")
    hero_image = models.ImageField(upload_to="home_images", null=True, blank=True, verbose_name="تصویر هدر")
    hero_image_alt = models.CharField(max_length=255, blank=True, null=True, verbose_name="متن جایگزین تصویر")

    stats_eyebrow = models.CharField(max_length=120, blank=True, null=True, verbose_name="متن بخش آمار")
    stats_title = models.CharField(max_length=200, blank=True, null=True, verbose_name="عنوان بخش آمار")
    stats_description = models.TextField(
        blank=True,
        null=True,
        verbose_name="توضیحات بخش آمار",
    )
    stat_total_courses_label = models.CharField(max_length=120, blank=True, null=True, verbose_name="برچسب دوره فعال")
    stat_free_courses_label = models.CharField(max_length=120, blank=True, null=True, verbose_name="برچسب دوره رایگان")
    stat_completed_courses_label = models.CharField(max_length=120, blank=True, null=True, verbose_name="برچسب دوره تکمیل‌شده")
    stat_articles_label = models.CharField(max_length=120, blank=True, null=True, verbose_name="برچسب مقالات")

    featured_courses_eyebrow = models.CharField(max_length=120, blank=True, null=True, verbose_name="متن بخش دوره‌ها")
    featured_courses_title = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="عنوان بخش دوره‌ها",
    )
    featured_courses_description = models.TextField(
        blank=True,
        null=True,
        verbose_name="توضیحات بخش دوره‌ها",
    )
    featured_courses_button_label = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        verbose_name="متن دکمه بخش دوره‌ها",
    )
    featured_courses_button_url = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="لینک دکمه بخش دوره‌ها",
    )

    article_eyebrow = models.CharField(max_length=120, blank=True, null=True, verbose_name="متن بخش وبلاگ")
    article_title = models.CharField(max_length=200, blank=True, null=True, verbose_name="عنوان بخش وبلاگ")
    article_description = models.TextField(
        blank=True,
        null=True,
        verbose_name="توضیحات بخش وبلاگ",
    )
    article_button_label = models.CharField(max_length=80, blank=True, null=True, verbose_name="متن دکمه بخش وبلاگ")
    article_button_url = models.CharField(max_length=255, blank=True, null=True, verbose_name="لینک دکمه بخش وبلاگ")

    class Meta:
        verbose_name = "صفحه اصلی"
        verbose_name_plural = "صفحه اصلی"

    def __str__(self):
        return self.title or "صفحه اصلی"


class HomePageMetric(models.Model):
    home_page = models.ForeignKey(HomePage, on_delete=models.CASCADE, related_name="metrics", verbose_name="صفحه اصلی")
    value = models.CharField(max_length=50, verbose_name="مقدار")
    title = models.CharField(max_length=120, verbose_name="عنوان")
    description = models.CharField(max_length=255, blank=True, default="", verbose_name="توضیحات")
    sort_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "شاخص هدر"
        verbose_name_plural = "شاخص‌های هدر"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["home_page", "sort_order"], name="unique_home_page_metric_order"),
        ]

    def __str__(self):
        return f"{self.home_page.title} - {self.title}"


class HomePageTrustItem(models.Model):
    home_page = models.ForeignKey(HomePage, on_delete=models.CASCADE, related_name="trust_items", verbose_name="صفحه اصلی")
    title = models.CharField(max_length=120, verbose_name="عنوان")
    sort_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "نشان اعتماد"
        verbose_name_plural = "نشان‌های اعتماد"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["home_page", "sort_order"], name="unique_home_page_trust_order"),
        ]

    def __str__(self):
        return f"{self.home_page.title} - {self.title}"


class HomePageFeaturePoint(models.Model):
    class IconChoices(models.TextChoices):
        BOOK = "book", "کتاب"
        SHIELD = "shield", "امنیت"
        LIGHTNING = "lightning", "سرعت"
        SUPPORT = "support", "پشتیبانی"

    home_page = models.ForeignKey(HomePage, on_delete=models.CASCADE, related_name="feature_points", verbose_name="صفحه اصلی")
    title = models.CharField(max_length=160, verbose_name="عنوان")
    icon = models.CharField(max_length=20, choices=IconChoices.choices, default=IconChoices.BOOK, verbose_name="آیکن")
    sort_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "نکته کلیدی"
        verbose_name_plural = "نکات کلیدی"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["home_page", "sort_order"], name="unique_home_page_feature_order"),
        ]

    def __str__(self):
        return f"{self.home_page.title} - {self.title}"


class HomePageHighlightCard(models.Model):
    class PositionChoices(models.TextChoices):
        TOP = "top", "بالا"
        BOTTOM = "bottom", "پایین"

    home_page = models.ForeignKey(
        HomePage,
        on_delete=models.CASCADE,
        related_name="highlight_cards",
        verbose_name="صفحه اصلی",
    )
    position = models.CharField(max_length=20, choices=PositionChoices.choices, verbose_name="موقعیت")
    title = models.CharField(max_length=160, verbose_name="عنوان")
    description = models.TextField(verbose_name="توضیحات")

    class Meta:
        verbose_name = "کارت شناور"
        verbose_name_plural = "کارت‌های شناور"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["home_page", "position"], name="unique_home_page_highlight_position"),
        ]

    def __str__(self):
        return f"{self.home_page.title} - {self.get_position_display()}"


class ContactPage(models.Model):
    slug = models.SlugField(default="contact", unique=True, editable=False, db_index=True)
    hero_eyebrow = models.CharField(max_length=120, blank=True, null=True, verbose_name="متن بالای هدر")
    hero_title = models.CharField(max_length=255, blank=True, null=True, verbose_name="عنوان هدر")
    hero_description = models.TextField(blank=True, null=True, verbose_name="توضیحات هدر")
    status_title = models.CharField(max_length=120, blank=True, null=True, verbose_name="عنوان کادر وضعیت")
    status_description = models.CharField(max_length=255, blank=True, null=True, verbose_name="توضیح کادر وضعیت")

    class Meta:
        verbose_name = "صفحه تماس با ما"
        verbose_name_plural = "صفحه تماس با ما"

    def __str__(self):
        return self.hero_title or "صفحه تماس با ما"


class ContactPageSignal(models.Model):
    contact_page = models.ForeignKey(ContactPage, on_delete=models.CASCADE, related_name="signals", verbose_name="صفحه تماس")
    text = models.CharField(max_length=120, verbose_name="متن")
    sort_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "نکته صفحه تماس"
        verbose_name_plural = "نکات صفحه تماس"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.text


class SeriesListingPage(models.Model):
    slug = models.SlugField(default="series-listing", unique=True, editable=False, db_index=True)
    hero_eyebrow = models.CharField(max_length=120, blank=True, null=True, verbose_name="متن بالای هدر")
    hero_title = models.CharField(max_length=255, blank=True, null=True, verbose_name="عنوان هدر")
    hero_description = models.TextField(blank=True, null=True, verbose_name="توضیحات هدر")

    class Meta:
        verbose_name = "صفحه آرشیو دوره‌ها"
        verbose_name_plural = "صفحه آرشیو دوره‌ها"

    def __str__(self):
        return self.hero_title or "صفحه آرشیو دوره‌ها"


class SeriesListingSignal(models.Model):
    series_listing_page = models.ForeignKey(SeriesListingPage, on_delete=models.CASCADE, related_name="signals", verbose_name="صفحه آرشیو")
    text = models.CharField(max_length=160, verbose_name="متن")
    sort_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "نکته آرشیو دوره‌ها"
        verbose_name_plural = "نکات آرشیو دوره‌ها"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.text


class BlogListingPage(models.Model):
    slug = models.SlugField(default="blog-listing", unique=True, editable=False, db_index=True)
    hero_eyebrow = models.CharField(max_length=120, blank=True, null=True, verbose_name="متن بالای هدر")
    hero_title = models.CharField(max_length=255, blank=True, null=True, verbose_name="عنوان هدر")
    hero_description = models.TextField(blank=True, null=True, verbose_name="توضیحات هدر")

    class Meta:
        verbose_name = "صفحه آرشیو بلاگ"
        verbose_name_plural = "صفحه آرشیو بلاگ"

    def __str__(self):
        return self.hero_title or "صفحه آرشیو بلاگ"









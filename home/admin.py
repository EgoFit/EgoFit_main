from __future__ import annotations

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from home.models import (
    AboutPage,
    Activity,
    Advantage,
    ArticleBlogImage,
    ArticleBlogLink,
    ArticleBlogModel,
    BlogListingPage,
    Category,
    CategoryBlog,
    Comment,
    CommentSectionModel,
    Community,
    ContactPage,
    ContactPageSignal,
    Counseling,
    DownContent,
    Episode,
    Footer,
    HomePage,
    HomePageFeaturePoint,
    HomePageHighlightCard,
    HomePageMetric,
    HomePageTrustItem,
    NavigationLink,
    Reply,
    Season,
    SeriesListingPage,
    SeriesListingSignal,
    SeriesModel,
    SiteSettings,
)
from home.rich_text import sanitize_rich_text


def _image_preview(file_field, *, height=60):
    if not file_field:
        return "—"
    return format_html('<img src="{}" style="height:{}px;border-radius:8px;" />', file_field.url, height)


class RichTextWidget(forms.Textarea):
    class Media:
        css = {"all": ("css/article-editor.css",)}
        js = ("js/article-editor.js",)

    def __init__(self, attrs=None):
        default_attrs = {"class": "rich-text-source", "rows": 12}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class ArticleBlogAdminForm(forms.ModelForm):
    class Meta:
        model = ArticleBlogModel
        fields = "__all__"
        widgets = {
            "article_description": RichTextWidget(),
            "built_in": RichTextWidget(),
            "article_extra_des1": RichTextWidget(),
            "article_extra_des2": RichTextWidget(),
        }

    def clean_article_description(self):
        return sanitize_rich_text(self.cleaned_data.get("article_description"))

    def clean_built_in(self):
        return sanitize_rich_text(self.cleaned_data.get("built_in"))

    def clean_article_extra_des1(self):
        return sanitize_rich_text(self.cleaned_data.get("article_extra_des1"))

    def clean_article_extra_des2(self):
        return sanitize_rich_text(self.cleaned_data.get("article_extra_des2"))


class ArticleBlogImageInline(admin.TabularInline):
    model = ArticleBlogImage
    extra = 1
    fields = ("image", "alt_text", "caption", "sort_order")
    ordering = ("sort_order", "id")


class ArticleBlogLinkInline(admin.TabularInline):
    model = ArticleBlogLink
    extra = 1
    fields = ("label", "url", "open_in_new_tab", "sort_order")
    ordering = ("sort_order", "id")


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ("title", "episode_number", "season")
    search_fields = ("title",)
    list_filter = ("season",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "email", "phone", "publication_status")
    list_select_related = ("user",)
    search_fields = (
        "name",
        "email",
        "phone",
        "user__fullname",
        "user__display_name",
        "user__phone",
        "user__email",
    )
    search_help_text = "جستجو بر اساس نام نظر‌دهنده، کاربر، شماره تماس یا ایمیل"
    list_filter = ("publication_status",)
    autocomplete_fields = ("user",)


@admin.register(SeriesModel)
class SeriesModelAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_compeleted", "free")
    search_fields = ("title", "author__fullname")
    list_filter = ("is_compeleted", "free")


@admin.register(ArticleBlogModel)
class ArticleBlogModelAdmin(admin.ModelAdmin):
    form = ArticleBlogAdminForm
    list_display = ("title", "author", "reading_time")
    search_fields = ("title", "author__fullname")
    list_filter = ("reading_time",)
    prepopulated_fields = {"slug": ("title",)}
    inlines = (ArticleBlogImageInline, ArticleBlogLinkInline)
    fieldsets = (
        (
            "اطلاعات اصلی",
            {
                "fields": (
                    "title",
                    "slug",
                    "language_kinds",
                    "image",
                    "author",
                    "reading_time",
                    "article_excerpt",
                    "author_image",
                    "author_description",
                ),
            },
        ),
        (
            "محتوای مقاله",
            {
                "description": "برای قالب‌بندی متن از نوار ابزار استفاده کنید. لینک‌های قابل مشاهده مقاله را از بخش «لینک‌های مقاله» پایین فرم اضافه کنید.",
                "fields": (
                    "article_description",
                    "built_in",
                    "article_extra_des1",
                    "article_extra_des2",
                ),
                "classes": ("wide",),
            },
        ),
    )


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("title", "series", "number")
    search_fields = ("title", "series__title")
    list_filter = ("series",)


@admin.register(Category)
class CategoryAdmin(TranslationAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Footer)
class FooterAdmin(TranslationAdmin):
    list_display = ("about_us", "phone_number", "email", "working_hours", "address")
    fieldsets = (
        (
            "About Us",
            {
                "fields": ("about_eyebrow", "about_title", "about_us"),
                "classes": ("wide",),
            },
        ),
        (
            "Contact Information",
            {
                "fields": ("phone_number", "email", "address", "working_hours"),
                "classes": ("wide",),
            },
        ),
        (
            "Links & Social",
            {
                "fields": ("links_section_title", "social_section_title", "show_social_media", "social_media"),
                "classes": ("wide",),
            },
        ),
        (
            "Trust badge & Copyright",
            {
                "fields": ("trust_text", "copyright_year"),
                "classes": ("wide",),
            },
        ),
    )

    def has_add_permission(self, request):
        return not Footer.objects.exists()


class HomePageMetricInline(TranslationTabularInline):
    model = HomePageMetric
    extra = 0
    min_num = 0


class HomePageTrustItemInline(TranslationTabularInline):
    model = HomePageTrustItem
    extra = 0
    min_num = 0


class HomePageFeaturePointInline(TranslationTabularInline):
    model = HomePageFeaturePoint
    extra = 0
    min_num = 0


class HomePageHighlightCardInline(TranslationTabularInline):
    model = HomePageHighlightCard
    extra = 0
    min_num = 0


@admin.register(HomePage)
class HomePageAdmin(TranslationAdmin):
    list_display = ("title", "slug")
    readonly_fields = ("slug",)
    inlines = [
        HomePageMetricInline,
        HomePageTrustItemInline,
        HomePageFeaturePointInline,
        HomePageHighlightCardInline,
    ]
    fieldsets = (
        (
            None,
            {
                "fields": ("title", "slug"),
            },
        ),
        (
            "هدر اصلی",
            {
                "fields": (
                    "hero_eyebrow",
                    "hero_title",
                    "hero_description",
                    "hero_primary_label",
                    "hero_primary_url",
                    "hero_secondary_label",
                    "hero_secondary_url",
                    "hero_image",
                    "hero_image_alt",
                )
            },
        ),
        (
            "بخش آمار",
            {
                "fields": (
                    "stats_eyebrow",
                    "stats_title",
                    "stats_description",
                    "stat_total_courses_label",
                    "stat_free_courses_label",
                    "stat_completed_courses_label",
                    "stat_articles_label",
                )
            },
        ),
        (
            "بخش دوره‌ها",
            {
                "fields": (
                    "featured_courses_eyebrow",
                    "featured_courses_title",
                    "featured_courses_description",
                    "featured_courses_button_label",
                    "featured_courses_button_url",
                )
            },
        ),
        (
            "بخش وبلاگ",
            {
                "fields": (
                    "article_eyebrow",
                    "article_title",
                    "article_description",
                    "article_button_label",
                    "article_button_url",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return not HomePage.objects.exists()


class ReplyInline(admin.TabularInline):
    model = Reply
    extra = 1


@admin.register(CommentSectionModel)
class CommentSectionModelAdmin(admin.ModelAdmin):
    list_display = ("__str__", "user", "created_at", "publication_status")
    inlines = [ReplyInline]
    autocomplete_fields = ("user", "series", "parent")
    search_fields = ("text", "user__fullname", "series__title")
    list_filter = ("created_at", "publication_status", "user")


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ("__str__", "created_at")
    search_fields = ("text", "user__fullname")
    list_filter = ("created_at",)


@admin.register(Counseling)
class CounselingAdmin(TranslationAdmin):
    list_display = ("title", "subtitle")
    search_fields = ("title", "subtitle")


@admin.register(AboutPage)
class AboutPageAdmin(TranslationAdmin):
    list_display = ("title", "description")
    search_fields = ("title", "description")


@admin.register(Activity)
class ActivityAdmin(TranslationAdmin):
    list_display = ("title", "description")
    search_fields = ("title", "description")


@admin.register(Community)
class CommunityAdmin(TranslationAdmin):
    list_display = ("title", "description")
    search_fields = ("title", "description")


admin.site.register(Advantage, TranslationAdmin)
admin.site.register(DownContent, TranslationAdmin)
admin.site.register(CategoryBlog, TranslationAdmin)


@admin.register(SiteSettings)
class SiteSettingsAdmin(TranslationAdmin):
    list_display = ("brand_name", "tagline", "logo_preview")
    readonly_fields = ("slug", "logo_preview")
    fieldsets = (
        (
            None,
            {
                "fields": ("brand_eyebrow", "brand_name", "logo", "logo_preview", "tagline", "header_search_placeholder", "default_meta_title"),
            },
        ),
    )

    @admin.display(description="پیش‌نمایش لوگو")
    def logo_preview(self, obj):
        return _image_preview(obj.logo)

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()


@admin.register(NavigationLink)
class NavigationLinkAdmin(TranslationAdmin):
    list_display = ("label", "url", "sort_order")
    list_editable = ("sort_order",)
    ordering = ("sort_order", "id")


class ContactPageSignalInline(TranslationTabularInline):
    model = ContactPageSignal
    extra = 0
    min_num = 0


@admin.register(ContactPage)
class ContactPageAdmin(TranslationAdmin):
    readonly_fields = ("slug",)
    inlines = [ContactPageSignalInline]
    fieldsets = (
        (
            "هدر",
            {
                "fields": ("slug", "hero_eyebrow", "hero_title", "hero_description"),
            },
        ),
        (
            "کادر وضعیت",
            {
                "fields": ("status_title", "status_description"),
            },
        ),
    )

    def has_add_permission(self, request):
        return not ContactPage.objects.exists()


class SeriesListingSignalInline(TranslationTabularInline):
    model = SeriesListingSignal
    extra = 0
    min_num = 0


@admin.register(SeriesListingPage)
class SeriesListingPageAdmin(TranslationAdmin):
    readonly_fields = ("slug",)
    inlines = [SeriesListingSignalInline]
    fieldsets = (
        (
            "هدر",
            {
                "fields": ("slug", "hero_eyebrow", "hero_title", "hero_description"),
            },
        ),
    )

    def has_add_permission(self, request):
        return not SeriesListingPage.objects.exists()


@admin.register(BlogListingPage)
class BlogListingPageAdmin(TranslationAdmin):
    readonly_fields = ("slug",)
    fieldsets = (
        (
            "هدر",
            {
                "fields": ("slug", "hero_eyebrow", "hero_title", "hero_description"),
            },
        ),
    )

    def has_add_permission(self, request):
        return not BlogListingPage.objects.exists()

from modeltranslation.translator import TranslationOptions, translator

from home.models import (
    AboutPage,
    Activity,
    Advantage,
    BlogListingPage,
    Category,
    CategoryBlog,
    Community,
    ContactPage,
    ContactPageSignal,
    Counseling,
    DownContent,
    Footer,
    HomePage,
    HomePageFeaturePoint,
    HomePageHighlightCard,
    HomePageMetric,
    HomePageTrustItem,
    NavigationLink,
    SeriesListingPage,
    SeriesListingSignal,
    SiteSettings,
)


class CategoryTranslationOptions(TranslationOptions):
    fields = ("title",)


class CategoryBlogTranslationOptions(TranslationOptions):
    fields = ("title",)


class AdvantageTranslationOptions(TranslationOptions):
    fields = ("title", "description")


class FooterTranslationOptions(TranslationOptions):
    fields = (
        "about_us",
        "working_hours",
        "address",
        "about_eyebrow",
        "about_title",
        "links_section_title",
        "social_section_title",
        "trust_text",
    )


class SiteSettingsTranslationOptions(TranslationOptions):
    fields = (
        "brand_eyebrow",
        "brand_name",
        "tagline",
        "header_search_placeholder",
        "default_meta_title",
    )


class NavigationLinkTranslationOptions(TranslationOptions):
    fields = ("label",)


class AboutPageTranslationOptions(TranslationOptions):
    fields = ("title", "description")


class ActivityTranslationOptions(TranslationOptions):
    fields = ("title", "description")


class CommunityTranslationOptions(TranslationOptions):
    fields = ("title", "description")


class CounselingTranslationOptions(TranslationOptions):
    fields = ("title", "subtitle", "description", "button_content")


class DownContentTranslationOptions(TranslationOptions):
    fields = ("title", "description")


class HomePageTranslationOptions(TranslationOptions):
    fields = (
        "title",
        "hero_eyebrow",
        "hero_title",
        "hero_description",
        "hero_primary_label",
        "hero_secondary_label",
        "hero_image_alt",
        "stats_eyebrow",
        "stats_title",
        "stats_description",
        "stat_total_courses_label",
        "stat_free_courses_label",
        "stat_completed_courses_label",
        "stat_articles_label",
        "featured_courses_eyebrow",
        "featured_courses_title",
        "featured_courses_description",
        "featured_courses_button_label",
        "article_eyebrow",
        "article_title",
        "article_description",
        "article_button_label",
    )


class HomePageMetricTranslationOptions(TranslationOptions):
    fields = ("value", "title", "description")


class HomePageTrustItemTranslationOptions(TranslationOptions):
    fields = ("title",)


class HomePageFeaturePointTranslationOptions(TranslationOptions):
    fields = ("title",)


class HomePageHighlightCardTranslationOptions(TranslationOptions):
    fields = ("title", "description")


class ContactPageTranslationOptions(TranslationOptions):
    fields = ("hero_eyebrow", "hero_title", "hero_description", "status_title", "status_description")


class ContactPageSignalTranslationOptions(TranslationOptions):
    fields = ("text",)


class SeriesListingPageTranslationOptions(TranslationOptions):
    fields = ("hero_eyebrow", "hero_title", "hero_description")


class SeriesListingSignalTranslationOptions(TranslationOptions):
    fields = ("text",)


class BlogListingPageTranslationOptions(TranslationOptions):
    fields = ("hero_eyebrow", "hero_title", "hero_description")


translator.register(Category, CategoryTranslationOptions)
translator.register(CategoryBlog, CategoryBlogTranslationOptions)
translator.register(Advantage, AdvantageTranslationOptions)
translator.register(Footer, FooterTranslationOptions)
translator.register(SiteSettings, SiteSettingsTranslationOptions)
translator.register(NavigationLink, NavigationLinkTranslationOptions)
translator.register(AboutPage, AboutPageTranslationOptions)
translator.register(Activity, ActivityTranslationOptions)
translator.register(Community, CommunityTranslationOptions)
translator.register(Counseling, CounselingTranslationOptions)
translator.register(DownContent, DownContentTranslationOptions)
translator.register(HomePage, HomePageTranslationOptions)
translator.register(HomePageMetric, HomePageMetricTranslationOptions)
translator.register(HomePageTrustItem, HomePageTrustItemTranslationOptions)
translator.register(HomePageFeaturePoint, HomePageFeaturePointTranslationOptions)
translator.register(HomePageHighlightCard, HomePageHighlightCardTranslationOptions)
translator.register(ContactPage, ContactPageTranslationOptions)
translator.register(ContactPageSignal, ContactPageSignalTranslationOptions)
translator.register(SeriesListingPage, SeriesListingPageTranslationOptions)
translator.register(SeriesListingSignal, SeriesListingSignalTranslationOptions)
translator.register(BlogListingPage, BlogListingPageTranslationOptions)

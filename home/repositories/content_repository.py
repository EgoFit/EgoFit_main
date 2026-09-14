from __future__ import annotations

from home.models import (
    AboutPage,
    Activity,
    Advantage,
    ArticleBlogModel,
    BlogListingPage,
    Category,
    CategoryBlog,
    Community,
    ContactPage,
    Counseling,
    DownContent,
    Footer,
    HomePage,
    SeriesListingPage,
)


class ContentRepository:
    def get_home_page(self):
        home_page, _ = HomePage.objects.get_or_create(slug="home")

        return HomePage.objects.prefetch_related(
            "metrics",
            "trust_items",
            "feature_points",
            "highlight_cards",
        ).get(pk=home_page.pk)

    def get_footer(self):
        return Footer.objects.first()

    def get_counseling(self):
        return Counseling.objects.first()

    def get_about_page(self):
        return AboutPage.objects.first()

    def get_activities(self):
        return Activity.objects.all()

    def get_communities(self):
        return Community.objects.all()

    def get_advantages(self):
        return Advantage.objects.all()

    def get_down_content(self):
        return DownContent.objects.all()

    def get_home_categories(self, limit: int = 12):
        return Category.objects.all()[:limit]

    def get_blog_categories(self, limit: int = 12):
        return CategoryBlog.objects.all()[:limit]

    def get_latest_articles_count(self):
        return ArticleBlogModel.objects.count()

    def get_contact_page(self):
        contact_page, _ = ContactPage.objects.get_or_create(slug="contact")
        return ContactPage.objects.prefetch_related("signals").get(pk=contact_page.pk)

    def get_series_listing_page(self):
        page, _ = SeriesListingPage.objects.get_or_create(slug="series-listing")
        return SeriesListingPage.objects.prefetch_related("signals").get(pk=page.pk)

    def get_blog_listing_page(self):
        page, _ = BlogListingPage.objects.get_or_create(slug="blog-listing")
        return page

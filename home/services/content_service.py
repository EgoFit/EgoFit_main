from __future__ import annotations

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _

from home.constants import HOME_CATEGORY_LIMIT, HOME_FEATURED_COURSE_LIMIT, HOME_LATEST_BLOG_LIMIT, HOME_PAGE_CACHE_PREFIX, HOME_PAGE_CACHE_TIMEOUT
from home.selectors.article_selector import ArticleSelector
from home.selectors.content_selector import ContentSelector
from home.selectors.course_selector import CourseSelector


class ContentService:
    @staticmethod
    def _cache_key(name: str) -> str:
        return f"{HOME_PAGE_CACHE_PREFIX}:{name}:v1"

    @staticmethod
    def get_home_context() -> dict:
        cache_key = ContentService._cache_key("home")
        cached_context = cache.get(cache_key)
        if cached_context is not None:
            return cached_context

        home_page = ContentSelector.get_home_page()
        featured_courses = list(CourseSelector.get_featured_courses(limit=HOME_FEATURED_COURSE_LIMIT))
        latest_blogs = list(ArticleSelector.get_latest_blogs(limit=HOME_LATEST_BLOG_LIMIT))
        advantages = list(ContentSelector.get_advantages())[:1]
        course_counts = CourseSelector.get_series_queryset().aggregate(
            total=Count("id"),
            free=Count("id", filter=Q(free=True)),
            completed=Count("id", filter=Q(is_compeleted=True)),
        )
        context = {
            "items": featured_courses,
            "course": featured_courses,
            "home_page": home_page,
            "categories": list(ContentSelector.get_home_categories(limit=HOME_CATEGORY_LIMIT)),
            "footer": ContentSelector.get_footer(),
            "counseling_content": ContentSelector.get_counseling(),
            "advantages": advantages,
            "featured_advantage": advantages[0] if advantages else None,
            "down_content": list(ContentSelector.get_down_content()),
            "blogs": latest_blogs,
            "blog": latest_blogs,
            "article": list(ContentSelector.get_blog_categories(limit=HOME_CATEGORY_LIMIT)),
            "home_stats": {
                "total_courses": course_counts.get("total") or 0,
                "free_courses": course_counts.get("free") or 0,
                "completed_courses": course_counts.get("completed") or 0,
                "latest_articles": ContentSelector.get_latest_articles_count(),
            },
        }
        cache.set(cache_key, context, timeout=HOME_PAGE_CACHE_TIMEOUT)
        return context

    @staticmethod
    def get_about_context() -> dict:
        cache_key = ContentService._cache_key("about")
        cached_context = cache.get(cache_key)
        if cached_context is not None:
            return cached_context

        context = {
            "about_page": ContentSelector.get_about_page(),
            "activities": list(ContentSelector.get_activities()),
            "communities": list(ContentSelector.get_communities()),
        }
        cache.set(cache_key, context, timeout=HOME_PAGE_CACHE_TIMEOUT)
        return context

    @staticmethod
    def get_series_list_context(*, free: str | None = None, category: str | None = None) -> dict:
        queryset = CourseSelector.get_series_filtered_queryset(free=free, category=category)
        course_list = list(queryset)
        free_courses_count, not_free_courses_count = CourseSelector.get_series_counts()
        warning_message = None
        if not course_list:
            warning_message = _("نتیجه‌ای برای فیلترهای انتخاب شده پیدا نشد، لطفاً گزینه‌های دیگری امتحان کنید.")
        context = {
            "course": course_list,
            "free_courses_count": free_courses_count,
            "not_free_courses_count": not_free_courses_count,
            "categories": CourseSelector.get_series_categories(),
            "warning_message": warning_message,
        }
        context.update(ContentService.get_series_listing_page_context())
        return context

    @staticmethod
    def get_series_listing_page_context() -> dict:
        cache_key = ContentService._cache_key("series_listing_page")
        cached_context = cache.get(cache_key)
        if cached_context is not None:
            return cached_context

        context = {"series_listing_page": ContentSelector.get_series_listing_page()}
        cache.set(cache_key, context, timeout=HOME_PAGE_CACHE_TIMEOUT)
        return context

    @staticmethod
    def get_blog_list_context(*, category: str | None = None) -> dict:
        queryset = ArticleSelector.get_blog_queryset(category=category)
        blog_list = list(queryset)
        warning_message = None
        if not blog_list:
            warning_message = _("هیچ مقاله‌ای برای فیلترهای انتخاب شده پیدا نشد، لطفاً گزینه‌های دیگری را امتحان کنید.")
        context = {
            "blog": blog_list,
            "categories": ArticleSelector.get_blog_categories(),
            "warning_message": warning_message,
        }
        context.update(ContentService.get_blog_listing_page_context())
        return context

    @staticmethod
    def get_blog_listing_page_context() -> dict:
        cache_key = ContentService._cache_key("blog_listing_page")
        cached_context = cache.get(cache_key)
        if cached_context is not None:
            return cached_context

        context = {"blog_listing_page": ContentSelector.get_blog_listing_page()}
        cache.set(cache_key, context, timeout=HOME_PAGE_CACHE_TIMEOUT)
        return context

    @staticmethod
    def get_contact_page_context() -> dict:
        cache_key = ContentService._cache_key("contact_page")
        cached_context = cache.get(cache_key)
        if cached_context is not None:
            return cached_context

        context = {"contact_page": ContentSelector.get_contact_page()}
        cache.set(cache_key, context, timeout=HOME_PAGE_CACHE_TIMEOUT)
        return context

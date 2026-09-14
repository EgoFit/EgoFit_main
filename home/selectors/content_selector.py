from __future__ import annotations

from home.repositories.content_repository import ContentRepository


class ContentSelector:
    repository = ContentRepository()

    @staticmethod
    def get_footer():
        return ContentSelector.repository.get_footer()

    @staticmethod
    def get_home_page():
        return ContentSelector.repository.get_home_page()

    @staticmethod
    def get_counseling():
        return ContentSelector.repository.get_counseling()

    @staticmethod
    def get_about_page():
        return ContentSelector.repository.get_about_page()

    @staticmethod
    def get_activities():
        return ContentSelector.repository.get_activities()

    @staticmethod
    def get_communities():
        return ContentSelector.repository.get_communities()

    @staticmethod
    def get_advantages():
        return ContentSelector.repository.get_advantages()

    @staticmethod
    def get_down_content():
        return ContentSelector.repository.get_down_content()

    @staticmethod
    def get_home_categories(limit: int = 12):
        return ContentSelector.repository.get_home_categories(limit=limit)

    @staticmethod
    def get_blog_categories(limit: int = 12):
        return ContentSelector.repository.get_blog_categories(limit=limit)

    @staticmethod
    def get_latest_articles_count():
        return ContentSelector.repository.get_latest_articles_count()

    @staticmethod
    def get_contact_page():
        return ContentSelector.repository.get_contact_page()

    @staticmethod
    def get_series_listing_page():
        return ContentSelector.repository.get_series_listing_page()

    @staticmethod
    def get_blog_listing_page():
        return ContentSelector.repository.get_blog_listing_page()

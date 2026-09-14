from __future__ import annotations

from home.constants import HOME_SEARCH_MAX_LENGTH
from home.exceptions import SearchValidationException
from home.selectors.search_selector import SearchSelector
from home.utils import normalize_search_query


class SearchService:
    @staticmethod
    def _validate_search_query(raw_query: str, *, empty_message: str) -> str:
        search = normalize_search_query(raw_query)
        if not search:
            raise SearchValidationException(empty_message)
        if len(search) > HOME_SEARCH_MAX_LENGTH:
            raise SearchValidationException("خطای دیگری در جستجو رخ داد.")
        if not any(char.isalnum() for char in search):
            raise SearchValidationException("خطای دیگری در جستجو رخ داد.")
        return search

    @staticmethod
    def normalize_search_query(raw_query: str) -> str:
        return normalize_search_query(raw_query)

    @staticmethod
    def search_courses(raw_query: str):
        search = SearchService._validate_search_query(
            raw_query,
            empty_message="لطفا دوره ای که به دنبال آن هستید را جست و جو کنید.",
        )
        return SearchSelector.search_courses(search)

    @staticmethod
    def search_blogs(raw_query: str):
        search = SearchService._validate_search_query(
            raw_query,
            empty_message="لطفا مقاله ای که به دنبال آن هستید را جست و جو کنید.",
        )
        return SearchSelector.search_blogs(search)

    @staticmethod
    def list_blog_categories():
        return SearchSelector.list_blog_categories()

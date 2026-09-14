from __future__ import annotations

from django.db.models import Q, QuerySet
from django.db.models.functions import Coalesce

from home.constants import HOME_SEARCH_LIMIT
from home.models import ArticleBlogModel, CategoryBlog, SeriesModel
from home.utils import build_score_expression, tokenize_search_query


class SearchSelector:
    @staticmethod
    def search_courses(raw_query: str) -> QuerySet:
        tokens = tokenize_search_query(raw_query)
        queryset = SeriesModel.objects.select_related("author", "language_kinds").prefetch_related("seasons__episodes")
        if not tokens:
            return queryset.none()

        for token in tokens:
            token_filter = Q()
            for field_name in ["title", "description", "introdution_course", "author__fullname", "language_kinds__title"]:
                token_filter |= Q(**{f"{field_name}__icontains": token})
            queryset = queryset.filter(token_filter)

        score = build_score_expression(
            tokens,
            [
                ("title", 10),
                ("description", 4),
                ("introdution_course", 5),
                ("author__fullname", 3),
                ("language_kinds__title", 2),
            ],
        )
        return queryset.annotate(search_rank=Coalesce(score, 0)).distinct().order_by("-search_rank", "-id")[:HOME_SEARCH_LIMIT]

    @staticmethod
    def search_blogs(raw_query: str) -> QuerySet:
        tokens = tokenize_search_query(raw_query)
        queryset = ArticleBlogModel.objects.select_related("author", "language_kinds")
        if not tokens:
            return queryset.none()

        for token in tokens:
            token_filter = Q()
            for field_name in ["title", "article_excerpt", "article_description", "author__fullname", "language_kinds__title"]:
                token_filter |= Q(**{f"{field_name}__icontains": token})
            queryset = queryset.filter(token_filter)

        score = build_score_expression(
            tokens,
            [
                ("title", 10),
                ("article_excerpt", 5),
                ("article_description", 4),
                ("author__fullname", 3),
                ("language_kinds__title", 2),
            ],
        )
        return queryset.annotate(search_rank=Coalesce(score, 0)).distinct().order_by("-search_rank", "-id")[:HOME_SEARCH_LIMIT]

    @staticmethod
    def list_blog_categories():
        return CategoryBlog.objects.order_by("id")
